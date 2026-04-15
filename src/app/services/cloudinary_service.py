"""
cloudinary_service.py
─────────────────────
Step 8: Conditional Cloudinary upload.
- Only called if MiniMax returns base64 (not a URL)
- Uploads image bytes, returns persistent CDN URL
- Retry: 2 attempts
"""

import io
import logging
import os
from typing import Optional

import cloudinary
import cloudinary.uploader
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger("cloudinary_service")

_configured = False


def _configure_cloudinary() -> None:
    global _configured
    if not _configured:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )
        _configured = True
        logger.info("[CLOUDINARY] Configured.")


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _upload_bytes(image_bytes: bytes, public_id: str) -> str:
    """Upload raw image bytes to Cloudinary and return the secure URL."""
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        public_id=public_id,
        folder="ai_storyboard",
        resource_type="image",
        timeout=15,
    )
    return result["secure_url"]


async def upload_to_cloudinary(scene_id: int, image_bytes: bytes) -> str:
    """
    Upload image bytes to Cloudinary (async-friendly via run_in_executor).
    Returns the hosted CDN URL.
    """
    import asyncio
    _configure_cloudinary()
    public_id = f"scene_{scene_id}_{int(asyncio.get_event_loop().time() * 1000)}"

    logger.info("[CLOUDINARY] Scene %d → uploading (%d bytes)...", scene_id, len(image_bytes))

    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, lambda: _upload_bytes(image_bytes, public_id))

    logger.info("[CLOUDINARY] Scene %d → uploaded to %s", scene_id, url)
    return url


async def resolve_image_url(scene_id: int, image_data: Optional[str | bytes], is_base64: bool) -> Optional[str]:
    """
    Resolve final image URL:
    - If is_base64 → upload to Cloudinary, return CDN URL
    - If URL        → return as-is (skip Cloudinary)
    - If None       → return None (panel will be skipped in validator)
    """
    if image_data is None:
        return None
    if not is_base64:
        # MiniMax returned a direct URL — use it
        return image_data
    # Base64 bytes — upload to Cloudinary
    try:
        return await upload_to_cloudinary(scene_id, image_data)
    except Exception as exc:
        logger.error("[CLOUDINARY] Scene %d upload failed: %s", scene_id, exc)
        return None
