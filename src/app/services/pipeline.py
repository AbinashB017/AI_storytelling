"""
pipeline.py
───────────
Full 9-step storyboard generation pipeline orchestrator.

Stage layout:
  Stage 1 [Sequential]:      Global context extraction + Scene segmentation
  Stage 2 [Sequential]:      Feature extraction (lightweight, no I/O)
  Stage 3 [Parallel]:        Scene enrichment + prompt engineering (asyncio.gather)
  Stage 4 [Parallel]:        Image generation via MiniMax (asyncio.gather)
  Stage 5 [Parallel/Cond]:   Cloudinary upload if base64 (asyncio.gather)
  Stage 6 [Sequential]:      Validate + assemble panels
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


async def run(text: str, style: str = "cinematic") -> StoryboardResponse:
    """
    Execute the full 9-step storyboard generation pipeline.

    Args:
        text:  User narrative paragraph (3–5 sentences)
        style: Visual style (default: cinematic)

    Returns:
        StoryboardResponse with validated panels
    """
    start = time.perf_counter()
    logger.info("[PIPELINE] ══ Starting pipeline ══ style=%s | text_len=%d", style, len(text))

    # ── Stage 1: Global Context + Scene Segmentation (Sequential) ───────────
    logger.info("[PIPELINE] Stage 1 → Global context extraction + scene segmentation")
    global_context, scenes = await asyncio.gather(
        extract_global_context(text, style),
        segment_scenes(text),
    )
    logger.info(
        "[PIPELINE] Stage 1 complete → %d scenes | character: %s",
        len(scenes),
        global_context.character_identity,
    )

    # ── Stage 2: Feature Extraction (Synchronous, no I/O) ───────────────────
    logger.info("[PIPELINE] Stage 2 → Feature extraction")
    features_list: List[SceneFeatures] = extract_all_features(scenes, global_context)
    logger.info("[PIPELINE] Stage 2 complete → features extracted for %d scenes", len(features_list))

    # ── Stage 3: Parallel Scene Enrichment + Prompt Engineering ─────────────
    logger.info("[PIPELINE] Stage 3 → Parallel scene enrichment (LLM)")
    enriched_scenes: List[EnrichedScene] = await build_all_enriched_scenes(
        scenes, features_list, global_context, style
    )
    logger.info("[PIPELINE] Stage 3 complete → %d scenes enriched", len(enriched_scenes))

    # ── Stage 4: Parallel Image Generation (MiniMax) ────────────────────────
    logger.info("[PIPELINE] Stage 4 → Parallel image generation")
    prompt_pairs = [(es.scene_id, es.final_prompt) for es in enriched_scenes]
    image_results = await generate_all_images(prompt_pairs)
    # image_results: list of (scene_id, image_data | None, is_base64)
    logger.info("[PIPELINE] Stage 4 complete → %d images generated", len(image_results))

    # ── Stage 5: Parallel Cloudinary Upload (Conditional) ───────────────────
    logger.info("[PIPELINE] Stage 5 → Parallel Cloudinary upload (conditional)")
    url_tasks = [
        resolve_image_url(scene_id, image_data, is_base64)
        for scene_id, image_data, is_base64 in image_results
    ]
    image_urls = await asyncio.gather(*url_tasks)
    logger.info("[PIPELINE] Stage 5 complete → URLs resolved")

    # ── Stage 6: Assemble + Validate Panels ─────────────────────────────────
    logger.info("[PIPELINE] Stage 6 → Assembling and validating panels")

    # Build lookup: scene_id → enriched_scene
    scene_lookup = {es.scene_id: es for es in enriched_scenes}
    # Build lookup: scene_id → url
    url_lookup = {
        scene_id: url
        for (scene_id, _, _), url in zip(image_results, image_urls)
    }

    raw_panels: List[Panel] = []
    for scene_id, url in url_lookup.items():
        es = scene_lookup.get(scene_id)
        if es is None:
            continue
        raw_panels.append(
            Panel(
                scene_id=scene_id,
                image_url=url or "",
                caption=es.scene_text,
                narrative_role=es.narrative_role,
            )
        )

    # Sort by scene_id for correct narrative order
    raw_panels.sort(key=lambda p: p.scene_id)

    # Validate (raises HTTP 422 if < 3 valid panels)
    validated_panels = validate_panels(raw_panels)

    elapsed = time.perf_counter() - start
    logger.info(
        "[PIPELINE] ══ Complete ══ %d panels | %.2fs elapsed",
        len(validated_panels),
        elapsed,
    )

    return StoryboardResponse(
        panels=validated_panels,
        total_scenes=len(validated_panels),
    )
