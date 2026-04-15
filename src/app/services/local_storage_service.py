"""
local_storage_service.py
──────────────────────────────
Downloads images or saves base64 locally to serve them statically.
"""

import os
import uuid
import logging
import base64
import httpx

logger = logging.getLogger("local_storage_service")

# Note we use the "static" dir relative to cwd
STATIC_DIR = "static"

import urllib.parse

async def save_image_locally(scene_id: int, image_data: str | bytes, is_base64: bool, request_host: str = "http://localhost:8000") -> str:
    """
    Saves the image data to local disk and returns the static URI.
    """
    os.makedirs(STATIC_DIR, exist_ok=True)
    extension = "png"
    if not is_base64 and isinstance(image_data, str) and ("jpeg" in image_data.lower() or "jpg" in image_data.lower()):
        extension = "jpeg"
        
    filename = f"scene_{scene_id}_{uuid.uuid4().hex[:8]}.{extension}"
    filepath = os.path.join(STATIC_DIR, filename)

    if is_base64:
        logger.info("[LOCAL] Saving base64 image locally for scene %d", scene_id)
        if isinstance(image_data, str):
            image_data = base64.b64decode(image_data)
        with open(filepath, "wb") as f:
            f.write(image_data)
    else:
        logger.info("[LOCAL] Downloading image URL locally for scene %d from %s", scene_id, image_data[:50])
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_data, timeout=30.0)
                resp.raise_for_status()
                with open(filepath, "wb") as f:
                    f.write(resp.content)
        except Exception as e:
            logger.error("[LOCAL] Failed to download image for scene %d: %s", scene_id, e)
            return image_data # fallback to original URL (minimax OSS link)
    
    local_url = f"{request_host}/static/{filename}"
    logger.info("[LOCAL] Saved scene %d to %s", scene_id, local_url)
    return local_url
