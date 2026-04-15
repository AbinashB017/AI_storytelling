"""
validator.py  (v2 — lenient, placeholder-aware)
────────────────────────────────────────────────
Validates assembled storyboard panels.
- Accepts placeholder URLs (placehold.co) — never aggressively drops these
- Only drops panels with genuinely empty image_url or caption
- Raises HTTP 422 only if < 3 panels remain after filtering
"""

import logging
from typing import List
from fastapi import HTTPException
from app.models.schemas import Panel

logger = logging.getLogger("validator")

MIN_PANELS = 3


def validate_panels(panels: List[Panel]) -> List[Panel]:
    """
    Filter and validate storyboard panels.
    A panel is VALID if:
      - image_url is non-empty (any URL accepted, including placeholders)
      - caption is non-empty
    Raises HTTP 422 only if < MIN_PANELS valid panels remain.
    """
    valid: List[Panel] = []
    dropped = 0

    for p in panels:
        url_ok     = bool(p.image_url and p.image_url.strip())
        caption_ok = bool(p.caption and p.caption.strip())

        if url_ok and caption_ok:
            valid.append(p)
        else:
            dropped += 1
            logger.warning(
                "[VALIDATE] Dropped panel %d — url_ok=%s caption_ok=%s",
                p.scene_id, url_ok, caption_ok,
            )

    if dropped:
        logger.warning("[VALIDATE] Dropped %d panel(s) with missing URL or caption.", dropped)

    logger.info("[PIPELINE] Final panel count: %d", len(valid))

    if len(valid) < MIN_PANELS:
        logger.error(
            "[VALIDATE] FAILED: only %d valid panel(s) (minimum %d required).",
            len(valid), MIN_PANELS,
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Storyboard generation produced only {len(valid)} valid panel(s). "
                f"At least {MIN_PANELS} are required. "
                "Please try again with a richer, more detailed narrative."
            ),
        )

    logger.info("[VALIDATE] %d panel(s) passed validation.", len(valid))
    return valid
