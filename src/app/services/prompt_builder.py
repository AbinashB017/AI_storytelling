"""
prompt_builder.py
─────────────────
Step 5: Context-aware scene enrichment (LLM)
Step 6: Final prompt engineering with character consistency footer
"""

import logging
from app.services.groq_client import call_llm
from app.models.schemas import Scene, SceneFeatures, GlobalContext, EnrichedScene

logger = logging.getLogger("prompt_builder")

ENRICHMENT_SYSTEM = (
    "You are a cinematic director and visual storyteller. "
    "Your task is to write a rich, detailed scene description for an image generation model. "
    "Preserve the exact character identity, clothing, and appearance provided — do NOT change them."
)

ENRICHMENT_PROMPT_TEMPLATE = """
You are writing a visual scene description for a storyboard panel.

STORY CONTEXT:
- Character identity: {character_identity}
- Character appearance: {character_appearance}
- Character clothing: {character_clothing} (MUST remain exactly the same)
- Environment: {environment}
- Visual style: {visual_style}
- Overall story tone: {story_tone}

THIS SCENE:
- Narrative role: {narrative_role}
- Scene text: "{scene_text}"
- Scene emotion: {emotion}
- Scene tone: {scene_tone}

Write a rich, cinematic scene description (3–5 sentences) for this storyboard panel.

CRITICAL RULES:
1. The character MUST be: {character_identity}
2. The character MUST wear exactly: {character_clothing}
3. The character appearance MUST be: {character_appearance}
4. The setting MUST be: {environment}
5. Maintain {visual_style} visual style throughout
6. Capture the {emotion} emotion visually through body language, lighting, and composition
7. DO NOT change clothing, appearance, or identity from what is specified above

Respond with ONLY the scene description — no labels, no preamble.
"""

# ─── Consistency Footer (appended to EVERY final prompt) ───────────────────
CONSISTENCY_FOOTER_TEMPLATE = (
    "Character: {character_identity}. "
    "Wearing: {character_clothing}. "
    "Appearance: {character_appearance}. "
    "DO NOT change clothing or physical appearance. "
    "Same environment: {environment}. "
    "{visual_style} cinematography, volumetric lighting, "
    "ultra-detailed textures, photorealistic rendering, "
    "consistent art style across all panels, 8K resolution."
)


async def enrich_scene(
    scene: Scene,
    features: SceneFeatures,
    global_context: GlobalContext,
) -> str:
    """
    Step 5: Generate a rich cinematic scene description using Groq LLM,
    with hard-locked character and environment consistency.
    """
    logger.info("[ENRICH] Scene %d (%s) — calling LLM for enrichment...", scene.scene_id, scene.narrative_role)

    prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
        character_identity=global_context.character_identity,
        character_appearance=global_context.character_appearance,
        character_clothing=global_context.character_clothing,
        environment=global_context.environment,
        visual_style=global_context.visual_style,
        story_tone=global_context.tone,
        narrative_role=scene.narrative_role,
        scene_text=scene.scene_text,
        emotion=features.emotion,
        scene_tone=features.tone,
    )

    enriched = await call_llm(prompt=prompt, system=ENRICHMENT_SYSTEM, temperature=0.7, max_tokens=512)
    logger.info("[ENRICH] Scene %d enriched (%d chars)", scene.scene_id, len(enriched))
    return enriched.strip()


def build_final_prompt(enriched_description: str, global_context: GlobalContext) -> str:
    """
    Step 6: Append the non-negotiable character consistency footer to the enriched description.
    This is always appended regardless of the enriched content.
    """
    footer = CONSISTENCY_FOOTER_TEMPLATE.format(
        character_identity=global_context.character_identity,
        character_clothing=global_context.character_clothing,
        character_appearance=global_context.character_appearance,
        environment=global_context.environment,
        visual_style=global_context.visual_style,
    )
    return f"{enriched_description}\n\n{footer}"


async def build_all_enriched_scenes(
    scenes: list[Scene],
    features_list: list[SceneFeatures],
    global_context: GlobalContext,
    style: str,
) -> list[EnrichedScene]:
    """
    Enrich all scenes and build final prompts.
    Enrichment LLM calls are collected here for parallel execution in pipeline.py.
    Returns list of EnrichedScene objects ready for image generation.
    """
    import asyncio

    async def process_one(scene: Scene, features: SceneFeatures) -> EnrichedScene:
        enriched_desc = await enrich_scene(scene, features, global_context)
        final_prompt = build_final_prompt(enriched_desc, global_context)
        return EnrichedScene(
            scene_id=scene.scene_id,
            scene_text=scene.scene_text,
            narrative_role=scene.narrative_role,
            enriched_description=enriched_desc,
            final_prompt=final_prompt,
        )

    tasks = [process_one(scene, feat) for scene, feat in zip(scenes, features_list)]
    results = await asyncio.gather(*tasks)
    return list(results)
