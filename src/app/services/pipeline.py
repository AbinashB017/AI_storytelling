"""
pipeline.py  (v2 — truly parallel, robust, always ≥ 3 panels)
──────────────────────────────────────────────────────────────
9-step storyboard pipeline orchestrator.

Stage layout (all parallel stages use asyncio.gather):
  Stage 1 [Parallel]:   Global context + Scene segmentation (concurrent LLM calls)
  Stage 2 [Sync]:       Feature extraction (lightweight, no I/O)
  Stage 3 [Parallel]:   Scene enrichment via LLM  (asyncio.gather)
  Stage 4 [Sync]:       Prompt engineering (CPU only)
  Stage 5 [Parallel]:   Image generation via MiniMax (asyncio.gather)
  Stage 6 [Parallel]:   Cloudinary upload if base64 (asyncio.gather)
  Stage 7 [Sync]:       Validate + assemble panels
"""

import asyncio
import logging
import time
from typing import List

from app.models.schemas import (
    GlobalContext,
    Scene,
    SceneFeatures,
    EnrichedScene,
    Panel,
    StoryboardResponse,
)
from app.services.scene_generator import extract_global_context, segment_scenes
from app.services.feature_extractor import extract_all_features
from app.services.prompt_builder import build_all_enriched_scenes
from app.services.image_generator import generate_all_images
from app.services.cloudinary_service import resolve_image_url
from app.utils.validator import validate_panels

logger = logging.getLogger("pipeline")

PLACEHOLDER_URL = "https://placehold.co/1024x576/0f1620/e8a43c?text=Scene+Unavailable"


async def run(text: str, style: str = "cinematic") -> StoryboardResponse:
    """
    Execute the full 9-step storyboard pipeline.
    Guaranteed to return ≥ 3 panels (using placeholder images where needed).
    """
    start = time.perf_counter()
    logger.info("[PIPELINE] ══ Starting ══ style=%s | text_len=%d", style, len(text))

    # ── Stage 1: Global Context + Scene Segmentation (PARALLEL) ──────────────
    logger.info("[PIPELINE] Stage 1 → Parallel: global context + scene segmentation")
    global_context, scenes = await asyncio.gather(
        extract_global_context(text, style),
        segment_scenes(text),
    )
    logger.info("[SCENES] %d scenes segmented: %s", len(scenes), [s.narrative_role for s in scenes])

    # ── Stage 2: Feature Extraction (sync, no I/O) ────────────────────────────
    logger.info("[PIPELINE] Stage 2 → Feature extraction")
    features_list: List[SceneFeatures] = extract_all_features(scenes, global_context)

    # ── Stage 3: Scene Enrichment (PARALLEL LLM calls) ────────────────────────
    logger.info("[PIPELINE] Stage 3 → Parallel scene enrichment (%d scenes)", len(scenes))
    enriched_scenes: List[EnrichedScene] = await build_all_enriched_scenes(
        scenes, features_list, global_context, style
    )
    logger.info("[PROMPTS] %d enriched prompts built", len(enriched_scenes))

    # ── Stage 5: Image Generation (PARALLEL, never fails) ────────────────────
    logger.info("[PIPELINE] Stage 5 → Parallel image generation (%d scenes)", len(enriched_scenes))
    prompt_pairs = [(es.scene_id, es.final_prompt) for es in enriched_scenes]
    image_results = await generate_all_images(prompt_pairs)
    logger.info("[IMAGES] %d image results received", len(image_results))

    # ── Stage 6: Cloudinary Upload (PARALLEL, conditional) ───────────────────
    logger.info("[PIPELINE] Stage 6 → Parallel Cloudinary upload (conditional)")
    url_tasks = [
        resolve_image_url(scene_id, image_data, is_base64)
        for scene_id, image_data, is_base64 in image_results
    ]
    resolved_urls = await asyncio.gather(*url_tasks)

    # ── Stage 7: Assemble + Validate Panels ──────────────────────────────────
    logger.info("[PIPELINE] Stage 7 → Assembling panels")

    scene_lookup = {es.scene_id: es for es in enriched_scenes}
    url_lookup   = {
        scene_id: (url or PLACEHOLDER_URL)
        for (scene_id, _, _), url in zip(image_results, resolved_urls)
    }

    raw_panels: List[Panel] = []
    for scene_id, url in url_lookup.items():
        es = scene_lookup.get(scene_id)
        if es is None:
            continue
        raw_panels.append(Panel(
            scene_id       = scene_id,
            image_url      = url if url else PLACEHOLDER_URL,
            caption        = es.scene_text,
            narrative_role = es.narrative_role,
        ))

    # Sort panels in narrative order
    raw_panels.sort(key=lambda p: p.scene_id)
    logger.info("[PIPELINE] %d raw panels assembled before validation", len(raw_panels))

    # Validate (raises HTTP 422 only if < 3 valid panels)
    validated = validate_panels(raw_panels)

    elapsed = time.perf_counter() - start
    logger.info(
        "[PIPELINE] ══ Complete ══ %d panels | %.2fs elapsed",
        len(validated), elapsed,
    )

    return StoryboardResponse(
        panels      = validated,
        total_scenes= len(validated),
    )
