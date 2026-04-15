"""
scene_generator.py
──────────────────
Step 2: Global Context Extraction
Step 3: Scene Segmentation (LLM-enforced, no string splitting)
"""

import json
import logging
from typing import List

from app.services.groq_client import call_llm_json
from app.models.schemas import GlobalContext, Scene

logger = logging.getLogger("scene_generator")

MAX_SCENES = 4

# ─── Prompts ───────────────────────────────────────────────────────────────

CONTEXT_SYSTEM = (
    "You are a cinematic story analyst. Extract structured metadata from narrative text. "
    "Always respond with valid JSON only, no explanation."
)

CONTEXT_PROMPT_TEMPLATE = """
Analyze the following narrative paragraph and extract a global story context.

NARRATIVE:
\"\"\"{text}\"\"\"

Return a JSON object with exactly these fields:
{{
  "main_character": "Full name or role description of the protagonist",
  "character_appearance": "Detailed physical description: age, build, hair color and style, skin tone, eye color, facial features",
  "character_clothing": "Exact clothing: e.g. worn blue denim jacket, white shirt, grey jeans, brown leather boots — be specific and consistent",
  "character_identity": "One concise identity tag: e.g. 'a young South Asian male engineer in his mid-20s with short black hair'",
  "environment": "Primary setting and location of the story",
  "tone": "Overall emotional tone of the narrative (e.g. hopeful struggle, triumphant, melancholic)",
  "visual_style": "{style}"
}}
"""

SEGMENTATION_SYSTEM = (
    "You are a professional screenplay writer and story analyst. "
    "Your task is to segment a short narrative into meaningful scenes. "
    "Always respond with valid JSON only, no explanation or markdown."
)

SEGMENTATION_PROMPT_TEMPLATE = """
Segment the following narrative into exactly 3 to 4 meaningful story scenes.

IMPORTANT RULES:
- DO NOT split by sentences mechanically
- Each scene must represent a distinct narrative beat (e.g. problem, discovery, turning point, resolution)
- Each scene should cover a meaningful story moment, not just a single sentence
- Return between 3 and 4 scenes — no more, no less

NARRATIVE:
\"\"\"{text}\"\"\"

Return a JSON array of scene objects like this:
[
  {{
    "scene_id": 1,
    "scene_text": "The narrative content of this scene",
    "narrative_role": "problem"
  }},
  ...
]

Narrative roles to choose from: problem, struggle, discovery, turning_point, resolution, transformation
"""


async def extract_global_context(text: str, style: str = "cinematic") -> GlobalContext:
    """
    Step 2: Extract global story context from the full narrative using Groq LLM.
    Returns a validated GlobalContext object.
    """
    logger.info("[CONTEXT] Extracting global context from narrative (%d chars)...", len(text))
    prompt = CONTEXT_PROMPT_TEMPLATE.format(text=text, style=style)

    raw = await call_llm_json(prompt=prompt, system=CONTEXT_SYSTEM, temperature=0.3)

    # Normalise and validate
    context = GlobalContext(
        main_character=raw.get("main_character", "the protagonist"),
        character_appearance=raw.get("character_appearance", "a person with undefined appearance"),
        character_clothing=raw.get("character_clothing", "casual clothing"),
        character_identity=raw.get("character_identity", "the main character"),
        environment=raw.get("environment", "an unspecified location"),
        tone=raw.get("tone", "neutral"),
        visual_style=raw.get("visual_style", style),
    )

    logger.info(
        "[CONTEXT] Extracted → character: %s | env: %s | tone: %s | style: %s",
        context.main_character,
        context.environment,
        context.tone,
        context.visual_style,
    )
    return context


async def segment_scenes(text: str) -> List[Scene]:
    """
    Step 3: Segment the narrative into 3–4 meaningful scenes using Groq LLM.
    Hard-caps at MAX_SCENES=4 scenes.
    """
    logger.info("[SCENES] Segmenting narrative into scenes...")
    prompt = SEGMENTATION_PROMPT_TEMPLATE.format(text=text)

    raw = await call_llm_json(prompt=prompt, system=SEGMENTATION_SYSTEM, temperature=0.4)

    # LLM may return dict with a key, or a list directly
    if isinstance(raw, dict):
        raw = raw.get("scenes", raw.get("data", list(raw.values())[0]))
    if not isinstance(raw, list):
        raise ValueError(f"Scene segmentation returned unexpected structure: {type(raw)}")

    # Cap at MAX_SCENES
    raw = raw[:MAX_SCENES]

    scenes = []
    for i, item in enumerate(raw, start=1):
        scenes.append(
            Scene(
                scene_id=item.get("scene_id", i),
                scene_text=item.get("scene_text", "").strip(),
                narrative_role=item.get("narrative_role", f"scene_{i}"),
            )
        )

    logger.info("[SCENES] Segmented into %d scenes: %s", len(scenes), [s.narrative_role for s in scenes])
    return scenes
