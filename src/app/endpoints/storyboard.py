"""
storyboard.py
─────────────
POST /api/v1/generate-storyboard
Converts a narrative paragraph into a visual storyboard.
"""

import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import StoryboardRequest, StoryboardResponse
from app.services import pipeline

logger = logging.getLogger("endpoint.storyboard")

router = APIRouter()


@router.post(
    "/generate-storyboard",
    response_model=StoryboardResponse,
    summary="Generate a visual storyboard from a narrative paragraph",
    description=(
        "Accepts a short narrative paragraph (3–5 sentences) and an optional visual style. "
        "Returns a coherent multi-panel storyboard with AI-generated images and captions. "
        "Uses LLM-based scene understanding and context-aware prompt engineering to ensure "
        "narrative continuity and character consistency across all panels."
    ),
    responses={
        200: {"description": "Storyboard generated successfully."},
        422: {"description": "Could not generate enough valid panels. Provide a richer narrative."},
        503: {"description": "Upstream AI service unavailable. Retry later."},
    },
)
async def generate_storyboard(request: StoryboardRequest) -> StoryboardResponse:
    """
    Main endpoint: orchestrates the full 9-step pipeline.
    """
    logger.info(
        "[ENDPOINT] Received request | style=%s | text_len=%d",
        request.style,
        len(request.text),
    )

    try:
        result = await pipeline.run(text=request.text, style=request.style)
        logger.info("[ENDPOINT] Response ready | panels=%d", result.total_scenes)
        return result

    except HTTPException:
        # Re-raise validation errors from pipeline (e.g. 422)
        raise

    except ValueError as exc:
        logger.error("[ENDPOINT] Pipeline value error: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception("[ENDPOINT] Unexpected error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Storyboard generation failed due to an upstream service error. Please try again.",
        )
