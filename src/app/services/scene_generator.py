"""
scene_generator.py  (v2 — with sentence fallback)
──────────────────────────────────────────────────
Step 2: Global Context Extraction (LLM)
Step 3: Scene Segmentation (LLM → sentence fallback if LLM fails)
Guarantee: always returns ≥ 3 scenes
"""

import logging
import re
from typing import List

from app.services.groq_client import call_llm_json, call_llm
from app.models.schemas import GlobalContext, Scene

logger = logging.getLogger("scene_generator")

MIN_SCENES = 3
MAX_SCENES = 4

# ── Prompts ───────────────────────────────────────────────────────────────────

CONTEXT_SYSTEM = (
    "You are a cinematic story analyst. Extract structured metadata from narrative text. "
    "Always respond with valid JSON only, no explanation."
)

CONTEXT_PROMPT = """\
Analyze this narrative and extract a global story context.

NARRATIVE:
\"\"\"{text}\"\"\"

Return ONLY a JSON object with these exact fields:
{{
  "main_character": "protagonist name or role",
  "character_appearance": "detailed physical description: age, build, hair, skin tone, facial features",
  "character_clothing": "exact clothing (e.g. worn blue denim jacket, white shirt, grey jeans, brown boots)",
  "character_identity": "one concise identity tag (e.g. 'a young South Asian male engineer in his mid-20s')",
  "environment": "primary setting and location",
  "tone": "overall emotional tone (e.g. hopeful struggle, triumph, melancholic)",
  "visual_style": "{style}"
}}
"""

SEGMENTATION_SYSTEM = (
    "You are a professional screenplay writer. "
    "Segment short narratives into meaningful story beats. "
    "Respond with valid JSON only — no markdown, no explanation."
)

SEGMENTATION_PROMPT = """\
Break this paragraph into exactly 3 to 4 meaningful narrative SCENES.

RULES:
- Do NOT split mechanically by sentences
- Each scene = a distinct story beat (problem / struggle / discovery / resolution)
- Return between 3 and 4 scene objects — absolutely no fewer than 3

NARRATIVE:
\"\"\"{text}\"\"\"

Return a JSON array:
[
  {{"scene_id": 1, "scene_text": "...", "narrative_role": "problem"}},
  {{"scene_id": 2, "scene_text": "...", "narrative_role": "struggle"}},
  {{"scene_id": 3, "scene_text": "...", "narrative_role": "resolution"}}
]

narrative_role must be one of: problem, struggle, discovery, turning_point, resolution, transformation
"""


# ── Sentence-based fallback ───────────────────────────────────────────────────

ROLE_LABELS = ["problem", "struggle", "discovery", "turning_point", "resolution", "transformation"]

def _sentence_split_fallback(text: str) -> List[Scene]:
    """Split text into sentences and group into 3–4 scenes as a last resort."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]

    if len(sentences) < 3:
        # Pad with partial re-uses if fewer than 3 sentences
        while len(sentences) < 3:
            sentences.append(sentences[-1])

    # Group sentences into 3 buckets
    n = len(sentences)
    bucket_size = max(1, n // 3)
    buckets: List[str] = []
    for i in range(0, n, bucket_size):
        chunk = " ".join(sentences[i: i + bucket_size])
        if chunk:
            buckets.append(chunk)
        if len(buckets) == MAX_SCENES:
            break

    while len(buckets) < MIN_SCENES:
        buckets.append(buckets[-1])

    scenes = []
    for idx, text_chunk in enumerate(buckets[:MAX_SCENES], start=1):
        scenes.append(Scene(
            scene_id=idx,
            scene_text=text_chunk,
            narrative_role=ROLE_LABELS[min(idx - 1, len(ROLE_LABELS) - 1)],
        ))
    return scenes


# ── Public API ────────────────────────────────────────────────────────────────

async def extract_global_context(text: str, style: str = "cinematic") -> GlobalContext:
    """Step 2: Extract global story context from the full narrative via LLM."""
    logger.info("[CONTEXT] Extracting global context | text_len=%d", len(text))
    try:
        raw = await call_llm_json(
            prompt=CONTEXT_PROMPT.format(text=text, style=style),
            system=CONTEXT_SYSTEM,
            temperature=0.3,
        )
        logger.debug("[CONTEXT] Raw JSON from LLM: %s", raw)
    except Exception as exc:
        logger.warning("[CONTEXT] LLM failed (%s), using defaults.", exc)
        raw = {}

    context = GlobalContext(
        main_character      = raw.get("main_character", "the protagonist"),
        character_appearance= raw.get("character_appearance", "a determined person"),
        character_clothing  = raw.get("character_clothing", "casual everyday clothing"),
        character_identity  = raw.get("character_identity", "the main character"),
        environment         = raw.get("environment", "an unspecified location"),
        tone                = raw.get("tone", "neutral"),
        visual_style        = raw.get("visual_style", style),
    )
    logger.info(
        "[CONTEXT] Done → character=%s | env=%s | tone=%s",
        context.main_character, context.environment, context.tone,
    )
    return context


async def segment_scenes(text: str) -> List[Scene]:
    """
    Step 3: Segment the narrative into 3–4 scenes.
    Primary:  Groq LLM (narrative-aware beats)
    Fallback: Sentence split (guarantees ≥ 3 scenes)
    """
    logger.info("[SCENES] Segmenting narrative into scenes...")

    # ── Try LLM first ────────────────────────────────────────────────────────
    try:
        raw = await call_llm_json(
            prompt=SEGMENTATION_PROMPT.format(text=text),
            system=SEGMENTATION_SYSTEM,
            temperature=0.4,
        )
        logger.debug("[SCENES] Raw breakdown from LLM: %s", raw)

        # Normalise: LLM may return dict wrapper or list directly
        if isinstance(raw, dict):
            for key in ("scenes", "data", "result"):
                if key in raw and isinstance(raw[key], list):
                    raw = raw[key]
                    break
            else:
                raw = list(raw.values())[0] if raw else []

        if isinstance(raw, list) and len(raw) >= MIN_SCENES:
            scenes: List[Scene] = []
            for i, item in enumerate(raw[:MAX_SCENES], start=1):
                scene_text = (item.get("scene_text") or item.get("text") or "").strip()
                if not scene_text:
                    continue
                scenes.append(Scene(
                    scene_id      = item.get("scene_id", i),
                    scene_text    = scene_text,
                    narrative_role= item.get("narrative_role", f"scene_{i}"),
                ))

            if len(scenes) >= MIN_SCENES:
                logger.info(
                    "[SCENES] LLM produced %d scenes: %s",
                    len(scenes), [s.narrative_role for s in scenes],
                )
                return scenes

        logger.warning("[SCENES] LLM returned < %d usable scenes → using fallback.", MIN_SCENES)

    except Exception as exc:
        logger.warning("[SCENES] LLM segmentation failed (%s) → using sentence fallback.", exc)

    # ── Sentence-based fallback ───────────────────────────────────────────────
    scenes = _sentence_split_fallback(text)
    logger.info(
        "[SCENES] Fallback produced %d scenes: %s",
        len(scenes), [s.narrative_role for s in scenes],
    )
    return scenes
