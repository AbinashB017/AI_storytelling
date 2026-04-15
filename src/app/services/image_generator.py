"""
image_generator.py  (v2 — never returns empty URL)
────────────────────────────────────────────────────
Step 7: Async image generation via MiniMax API.
- Retries up to 3 times on failure
- Returns placeholder URL on all failures (NEVER returns None or empty string)
- Detects URL vs base64 response automatically
- All scenes generated in parallel via asyncio.gather
"""

import asyncio
import base64
import logging
import os
from typing import Tuple

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("image_generator")

MINIMAX_API_URL = "https://api.minimaxi.chat/v1/image_generation"
PLACEHOLDER_URL = "https://dummyimage.com/1024x576/161f2e/8a9bb0.png&text=Scene+Unavailable"


def _get_headers() -> dict:
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("MINIMAX_API_KEY is not set in environment.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


@retry(
    retry=retry_if_exception_type((
        httpx.HTTPStatusError,
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.RemoteProtocolError,
    )),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_minimax(client: httpx.AsyncClient, prompt: str) -> dict:
    """Single async call to MiniMax image API with retry decoration."""
    payload = {
        "model": "image-01",
        "prompt": prompt,
        "width": 1024,
        "height": 576,
        "n": 1,
    }
    logger.debug("[IMAGE] Calling MiniMax with payload: %s", payload)
    response = await client.post(
        MINIMAX_API_URL,
        headers=_get_headers(),
        json=payload,
        timeout=60.0,
    )
    logger.debug("[IMAGE] MiniMax HTTP status: %s", response.status_code)
    response.raise_for_status()
    raw_json = response.json()
    logger.debug("[IMAGE] MiniMax raw response headers: %s", response.headers)
    return raw_json


def _parse_response(data: dict, scene_id: int) -> Tuple[str, bool]:
    """
    Parse MiniMax response → (image_data, is_base64).
    Tries multiple known response shapes.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Scene {scene_id}: Expected response dict, got {type(data)}")

    import json
    
    _data = data.get("data")
    
    if isinstance(_data, dict):
        # Shape 0: Current MiniMax API response structure
        image_urls = _data.get("image_urls", [])
        if isinstance(image_urls, list) and len(image_urls) > 0 and isinstance(image_urls[0], str):
            logger.info("[IMAGE] type: url")
            logger.info("[IMAGE] length of data: %d", len(image_urls[0]))
            return image_urls[0], False

        # Shape 1
        images = _data.get("images", [])
        if isinstance(images, list) and len(images) > 0 and isinstance(images[0], dict):
            img = images[0]
            if img.get("url"):
                logger.info("[IMAGE] type: url")
                logger.info("[IMAGE] length of data: %d", len(img["url"]))
                return img["url"], False
            if img.get("b64_json"):
                logger.info("[IMAGE] type: base64")
                logger.info("[IMAGE] length of data: %d", len(img["b64_json"]))
                return img["b64_json"], True
    
    elif isinstance(_data, list) and len(_data) > 0 and isinstance(_data[0], dict):
        # Shape 3: data is a list directly
        item = _data[0]
        if item.get("url"):
            logger.info("[IMAGE] type: url")
            logger.info("[IMAGE] length of data: %d", len(item["url"]))
            return item["url"], False
        if item.get("b64_json"):
            logger.info("[IMAGE] type: base64")
            logger.info("[IMAGE] length of data: %d", len(item["b64_json"]))
            return item["b64_json"], True
            
    # Shape 2: top-level url / b64_json
    if data.get("image_url"):
        logger.info("[IMAGE] type: url")
        logger.info("[IMAGE] length of data: %d", len(data["image_url"]))
        return data["image_url"], False
    if data.get("b64_json"):
        logger.info("[IMAGE] type: base64")
        logger.info("[IMAGE] length of data: %d", len(data["b64_json"]))
        return data["b64_json"], True

    logger.error("[IMAGE] Unrecognized shape for Scene %d. Data: %s", scene_id, json.dumps(data))
    raise ValueError(f"Scene {scene_id}: Unrecognised MiniMax response shape.")


async def generate_image(
    scene_id: int,
    prompt: str,
    client: httpx.AsyncClient,
) -> Tuple[str, bool]:
    """
    Mocked image generation to save MiniMax API calls.
    """
    logger.info("[IMAGE] Scene %d → sending prompt (len=%d) to MiniMax...", scene_id, len(prompt))
    try:
        data = await _call_minimax(client, prompt)
        result = _parse_response(data, scene_id)
        logger.info("[IMAGE] Scene %d → success", scene_id)
        return result
    except Exception as exc:
        logger.error("[IMAGE] Scene %d → all retries failed: %s — using placeholder", scene_id, exc)
        return PLACEHOLDER_URL, False   # ← NEVER returns empty


async def generate_all_images(
    prompts: list[Tuple[int, str]],
) -> list[Tuple[int, str, bool]]:
    """
    Parallel image generation for all scenes.
    Args: list of (scene_id, prompt)
    Returns: list of (scene_id, image_data, is_base64)
    Guarantees: every entry has a non-None image_data (placeholder on error).
    """
    logger.info("[IMAGES] Generating %d images in parallel...", len(prompts))
    async with httpx.AsyncClient() as client:
        tasks = [generate_image(sid, prompt, client) for sid, prompt in prompts]
        raw_results = await asyncio.gather(*tasks)   # never raises — each task handles its own errors

    results = []
    for (scene_id, _), (image_data, is_base64) in zip(prompts, raw_results):
        results.append((scene_id, image_data, is_base64))
        logger.info(
            "[IMAGES] Scene %d → %s",
            scene_id,
            "base64" if is_base64 else (str(image_data)[:60] if image_data else "placeholder"),
        )

    logger.info("[IMAGES] All %d images resolved.", len(results))
    return results
