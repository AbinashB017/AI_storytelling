"""
feature_extractor.py
────────────────────
Step 4: Lightweight per-scene feature extraction.
Extracts: emotion, tone, environment — no external NLP libraries.
"""

import logging
from app.models.schemas import Scene, SceneFeatures, GlobalContext

logger = logging.getLogger("feature_extractor")

# ─── Keyword Maps ──────────────────────────────────────────────────────────

EMOTION_KEYWORDS: dict[str, list[str]] = {
    "frustration":   ["struggle", "failed", "unable", "stuck", "frustrated", "exhausted", "desperate", "hopeless"],
    "determination": ["determined", "pushed", "kept", "refused", "persisted", "tried", "committed"],
    "hope":          ["hope", "opportunity", "chance", "possibility", "glimpse", "light", "potential"],
    "excitement":    ["excited", "thrilled", "discovered", "found", "realized", "breakthrough", "suddenly"],
    "triumph":       ["success", "achieved", "won", "celebrated", "accomplished", "finally", "transformed"],
    "sadness":       ["lost", "missed", "alone", "lonely", "grief", "sad", "tears", "broken"],
    "curiosity":     ["wondered", "explored", "searched", "curious", "questioned", "investigated"],
    "anxiety":       ["worried", "nervous", "scared", "afraid", "uncertain", "doubt"],
}

TONE_POSITIVE = ["success", "hope", "joy", "achieved", "celebrated", "triumph", "won", "finally", "transformed", "discovered"]
TONE_NEGATIVE = ["struggle", "failed", "lost", "desperate", "broken", "worried", "alone", "darkness", "unable"]


def _detect_emotion(text: str) -> str:
    text_lower = text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return emotion
    return "neutral"


def _detect_tone(text: str) -> str:
    text_lower = text.lower()
    pos_score = sum(1 for kw in TONE_POSITIVE if kw in text_lower)
    neg_score = sum(1 for kw in TONE_NEGATIVE if kw in text_lower)
    if pos_score > neg_score:
        return "positive"
    elif neg_score > pos_score:
        return "negative"
    return "neutral"


def extract_features(scene: Scene, global_context: GlobalContext) -> SceneFeatures:
    """
    Extract emotion, tone, and environment for a single scene.
    Inherits environment from global_context if not detectable from text.
    """
    emotion = _detect_emotion(scene.scene_text)
    tone = _detect_tone(scene.scene_text)
    environment = global_context.environment  # Always inherit for consistency

    features = SceneFeatures(
        scene_id=scene.scene_id,
        emotion=emotion,
        tone=tone,
        environment=environment,
    )

    logger.info(
        "[FEATURES] Scene %d (%s) → emotion=%s | tone=%s | env=%s",
        scene.scene_id,
        scene.narrative_role,
        emotion,
        tone,
        environment,
    )
    return features


def extract_all_features(scenes: list[Scene], global_context: GlobalContext) -> list[SceneFeatures]:
    """Extract features for all scenes (synchronous, no external calls)."""
    return [extract_features(s, global_context) for s in scenes]
