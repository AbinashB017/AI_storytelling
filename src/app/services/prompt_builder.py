"""
prompt_builder.py  (v3 — cinematic, story-driven, few-shot)
─────────────────────────────────────────────────────────────
Step 5: Context-aware scene enrichment (LLM) with few-shot examples
Step 6: Structured final prompt with forced consistency, dynamic motion,
        cinematic lighting, and negative prompting keywords.
"""

import asyncio
import logging
from app.services.groq_client import call_llm
from app.models.schemas import Scene, SceneFeatures, GlobalContext, EnrichedScene

logger = logging.getLogger("prompt_builder")

# ─── Few-Shot System Prompt ────────────────────────────────────────────────
ENRICHMENT_SYSTEM = (
    "You are a cinematic director and AI image-prompt engineer. "
    "Your task is to write a rich, structured, visually detailed prompt for an image generation model. "
    "NEVER change character identity, clothing, or appearance from what is specified. "
    "Follow the structured format exactly. Keep output under 200 words."
)

# ─── Few-Shot Examples ────────────────────────────────────────────────────
FEW_SHOT_EXAMPLES = """
---EXAMPLES---

INPUT: "A man is stressed at his work desk"
CHARACTER: A 30-year-old male software engineer with dark hair
CLOTHING: White dress shirt, sleeves rolled up
ENVIRONMENT: Modern open-plan office with floor-to-ceiling windows
STYLE: cinematic realistic
SCENE: 1 of 4 | ROLE: problem

OUTPUT:
The same 30-year-old male software engineer (1 person) with dark hair wearing a white dress shirt with sleeves rolled up, in the same modern open-plan office with floor-to-ceiling windows, cinematic realistic style —
gripping the edge of a cluttered desk, leaning over a glowing monitor with a tense furrowed expression, stacks of papers and empty coffee cups scattered around, dim overhead lighting with harsh shadows, tight over-shoulder shot, atmosphere of mounting pressure and exhaustion.
Negative: no extra limbs, no distorted hands, no blurry face, no unrealistic anatomy.

---

INPUT: "He discovers a new solution and feels hopeful"
CHARACTER: A 30-year-old male software engineer with dark hair
CLOTHING: White dress shirt, sleeves rolled up
ENVIRONMENT: Modern open-plan office with floor-to-ceiling windows
STYLE: cinematic realistic
SCENE: 2 of 4 | ROLE: discovery

OUTPUT:
The same 30-year-old male software engineer (1 person) with dark hair wearing a white dress shirt with sleeves rolled up, in the same modern open-plan office with floor-to-ceiling windows, cinematic realistic style —
leaning forward with wide eyes as a breakthrough appears on his screen, one hand reaching toward the keyboard with sudden purpose, soft warm light breaking through the window illuminating his face, expression shifting from exhaustion to cautious excitement, medium close-up shot, hopeful and electric atmosphere.
Negative: no extra limbs, no distorted hands, no blurry face, no unrealistic anatomy.

---
"""

# ─── Scene Enrichment Template ────────────────────────────────────────────
ENRICHMENT_PROMPT_TEMPLATE = (
    FEW_SHOT_EXAMPLES
    + """
Now write a cinematic image prompt for this scene. Follow the EXACT output format from the examples above.

CHARACTER: {character_identity}, {character_appearance}
CLOTHING: {character_clothing} (DO NOT change)
ENVIRONMENT: {environment} (DO NOT change)
STYLE: {visual_style}
SCENE: {scene_index} of {total_scenes} | ROLE: {narrative_role}
STORY TONE: {story_tone}
EMOTION: {emotion}

THIS SCENE TEXT: "{scene_text}"

REQUIREMENTS:
- Start with: "The same [character] ([N] person/people) ... in the same [environment], [style] style —"
- Describe: action verb (not static), body language, object interaction
- Include: lighting description, camera angle (wide shot / close-up / medium), atmosphere
- End with: "Negative: no extra limbs, no distorted hands, no blurry face, no unrealistic anatomy."
- Max 180 words. No scene labels. No preamble.

Also on the last two lines, generate:
HEADLINE: [4-6 word catchy story-driven title for this scene]
CAPTION: [2-3 vivid, cinematic, emotionally resonant sentences describing what is happening in this scene and why it matters to the story. Write in present tense, as if narrating a film. Make it rich, poetic, and compelling — not just a summary.]
"""
)

# ─── Consistency Quality Suffix ───────────────────────────────────────────
QUALITY_SUFFIX = (
    "Cinematic 16:9 widescreen anamorphic aspect ratio, "
    "cinematic lighting, volumetric light rays, soft natural shadows, "
    "ultra-detailed photorealistic textures, 8K resolution, "
    "consistent character design, film grain, anamorphic lens, "
    "color graded, sharp focus on subject."
)

NEGATIVE_SUFFIX = (
    "Negative: no extra limbs, no distorted hands, no blurry face, "
    "no deformed anatomy, no duplicate people, no watermarks, no text overlays."
)

MINIMAX_CHAR_LIMIT = 1450


def _enforce_prompt_limit(description: str, suffix: str) -> str:
    """Truncate description to ensure total prompt stays under MiniMax limit."""
    full = f"{description}\n\n{suffix}"
    if len(full) <= MINIMAX_CHAR_LIMIT:
        return full
    max_desc = MINIMAX_CHAR_LIMIT - len(suffix) - 4  # 4 = '\n\n' + buffer
    return f"{description[:max_desc]}...\n\n{suffix}"


async def enrich_scene(
    scene: Scene,
    features: SceneFeatures,
    global_context: GlobalContext,
    scene_index: int,
    total_scenes: int,
) -> tuple[str, str]:
    """
    Step 5: Generate a rich cinematic scene description + headline using Groq LLM.
    Returns (enriched_description, headline, caption).
    """
    logger.info(
        "[ENRICH] Scene %d (%s) [%d/%d] — calling LLM for enrichment...",
        scene.scene_id, scene.narrative_role, scene_index, total_scenes,
    )

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
        scene_index=scene_index,
        total_scenes=total_scenes,
    )

    raw = await call_llm(prompt=prompt, system=ENRICHMENT_SYSTEM, temperature=0.75, max_tokens=600)
    raw = raw.strip()

    # Extract headline and caption if present
    headline = ""
    caption  = ""
    lines    = raw.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("HEADLINE:"):
            headline = stripped.split(":", 1)[-1].strip()
        elif stripped.upper().startswith("CAPTION:"):
            caption = stripped.split(":", 1)[-1].strip()
        else:
            cleaned_lines.append(line)

    enriched_description = "\n".join(cleaned_lines).strip()
    if not headline:
        headline = scene.narrative_role.replace("_", " ").title()
    if not caption:
        # Fallback: use scene_text if LLM didn't produce a caption
        caption = scene.scene_text

    logger.info(
        "[ENRICH] Scene %d enriched (%d chars) | headline: %s | caption_len: %d",
        scene.scene_id, len(enriched_description), headline, len(caption),
    )
    return enriched_description, headline, caption


def build_final_prompt(enriched_description: str) -> str:
    """
    Step 6: Append quality suffix to the enriched description.
    Enforces MiniMax character limit strictly.
    """
    return _enforce_prompt_limit(enriched_description, QUALITY_SUFFIX)


async def build_all_enriched_scenes(
    scenes: list[Scene],
    features_list: list[SceneFeatures],
    global_context: GlobalContext,
    style: str,
) -> list[EnrichedScene]:
    """
    Enrich all scenes and build final prompts in parallel.
    Returns list of EnrichedScene objects ready for image generation.
    """
    total = len(scenes)

    async def process_one(scene: Scene, features: SceneFeatures, idx: int) -> EnrichedScene:
        enriched_desc, headline, caption = await enrich_scene(
            scene, features, global_context,
            scene_index=idx,
            total_scenes=total,
        )
        final_prompt = build_final_prompt(enriched_desc)
        logger.debug("[PROMPT] Scene %d final prompt length: %d", scene.scene_id, len(final_prompt))
        return EnrichedScene(
            scene_id=scene.scene_id,
            scene_text=scene.scene_text,
            narrative_role=scene.narrative_role,
            enriched_description=enriched_desc,
            final_prompt=final_prompt,
            headline=headline,
            caption=caption,
        )

    tasks = [process_one(scene, feat, i + 1) for i, (scene, feat) in enumerate(zip(scenes, features_list))]
    results = await asyncio.gather(*tasks)
    return list(results)
