"""
validator.py
────────────
Step 9 (part): Validate assembled storyboard panels.
- Minimum 3 panels required
- Each panel must have a valid image_url (starts with http)
- Each panel must have a non-empty caption
"""

import logging
from typing import List
from fastapi import HTTPException
from app.models.schemas import Panel

logger = logging.getLogger("validator")


def validate_panels(panels: List[Panel]) -> List[Panel]:
    """
    Validate storyboard panels and raise HTTPException on failure.
    Filters out panels with missing image URLs and rechecks count.
    """
    # Filter panels that have valid image_url
    valid = [
        p for p in panels
        if p.image_url
        and p.image_url.startswith("http")
        and p.caption
        and p.caption.strip()
    ]

    invalid_count = len(panels) - len(valid)
    if invalid_count:
        logger.warning("[VALIDATE] Dropped %d invalid panels (missing URL or caption).", invalid_count)

    if len(valid) < 3:
        logger.error(
            "[VALIDATE] Validation FAILED: only %d valid panels (minimum 3 required).", len(valid)
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Storyboard generation produced only {len(valid)} valid panel(s). "
                "At least 3 are required. Please try again with a more detailed narrative."
            ),
        )

    logger.info("[VALIDATE] %d panels passed validation.", len(valid))
    return valid
