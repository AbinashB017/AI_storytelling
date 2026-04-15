from pydantic import BaseModel, Field
from typing import List, Optional


class StoryboardRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="A short narrative paragraph (3–5 sentences) to convert into a storyboard.",
        example=(
            "A young engineer discovers a hidden talent for painting after losing his job. "
            "He struggles through rejection but keeps creating. One day, his art captures the "
            "attention of a famous gallery owner. His life transforms completely."
        ),
    )
    style: str = Field(
        default="cinematic",
        description="Visual style for generated images.",
        example="cinematic",
    )


class Panel(BaseModel):
    scene_id: int = Field(..., description="1-indexed scene number.")
    image_url: str = Field(..., description="Hosted URL of the generated scene image.")
    headline: Optional[str] = Field(None, description="Short catchy headline for this panel.")
    caption: str = Field(..., description="Original scene text for this panel.")
    narrative_role: Optional[str] = Field(
        None, description="Narrative beat (e.g., problem, discovery, resolution)."
    )


class StoryboardResponse(BaseModel):
    panels: List[Panel] = Field(..., description="Ordered list of storyboard panels.")
    total_scenes: int = Field(..., description="Total number of panels generated.")


# ─── Internal models used across services ──────────────────────────────────


class GlobalContext(BaseModel):
    main_character: str
    character_appearance: str
    character_clothing: str
    character_identity: str
    environment: str
    tone: str
    visual_style: str = "cinematic"


class Scene(BaseModel):
    scene_id: int
    scene_text: str
    narrative_role: str


class SceneFeatures(BaseModel):
    scene_id: int
    emotion: str
    tone: str
    environment: str


class EnrichedScene(BaseModel):
    scene_id: int
    scene_text: str
    narrative_role: str
    enriched_description: str
    final_prompt: str
    headline: str = ""
