"""
image_generator.py
──────────────────
Step 7: Async image generation via MiniMax API.
- Returns URL directly if available (skips Cloudinary)
- Returns base64 bytes if image is base64-encoded (Cloudinary needed)
- Retry: 3 attempts, 30s timeout
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


def _get_headers() -> dict:
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise EnvironmentError("MINIMAX_API_KEY is not set.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_minimax(client: httpx.AsyncClient, prompt: str) -> dict:
    """Make a single async call to MiniMax image generation API."""
    payload = {
        "model": "image-01",
        "prompt": prompt,
        "width": 1024,
        "height": 576,
        "n": 1,
    }
    response = await client.post(
        MINIMAX_API_URL,
        headers=_get_headers(),
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _parse_response(data: dict, scene_id: int) -> Tuple[str | bytes, bool]:
    """
    Parse MiniMax response.
    Returns: (image_data, is_base64)
      - If URL found: (str url, False)
      - If base64 found: (bytes, True)
    """
    # Try to get URL first
    try:
        images = data.get("data", {}).get("images", [])
        if images:
            img = images[0]
            if "url" in img and img["url"]:
                logger.info("[IMAGE] Scene %d → received URL", scene_id)
                return img["url"], False
            if "b64_json" in img and img["b64_json"]:
                logger.info("[IMAGE] Scene %d → received base64", scene_id)
                return base64.b64decode(img["b64_json"]), True
    except (KeyError, IndexError, TypeError):
        pass

    # Fallback: check top-level response structure
    if "image_url" in data:
        return data["image_url"], False
    if "b64_json" in data:
        return base64.b64decode(data["b64_json"]), True

    raise ValueError(f"Scene {scene_id}: Could not extract image from MiniMax response: {data}")


async def generate_image(
    scene_id: int,
    prompt: str,
    client: httpx.AsyncClient,
) -> Tuple[str | bytes, bool]:
    """
    Generate a single image for a scene.
    Returns (image_data, is_base64).
    """
    logger.info("[IMAGE] Scene %d → sending to MiniMax (prompt_len=%d)...", scene_id, len(prompt))
    try:
        data = await _call_minimax(client, prompt)
        result = _parse_response(data, scene_id)
        return result
    except Exception as exc:
        logger.error("[IMAGE] Scene %d → FAILED: %s", scene_id, exc)
        raise


async def generate_all_images(
    prompts: list[Tuple[int, str]]
) -> list[Tuple[int, str | bytes, bool]]:
    """
    Parallel image generation for all scenes.
    Args:
        prompts: list of (scene_id, prompt) tuples
    Returns:
        list of (scene_id, image_data, is_base64)
    """
    async with httpx.AsyncClient() as client:
        tasks = [generate_image(scene_id, prompt, client) for scene_id, prompt in prompts]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for i, (scene_id, prompt) in enumerate(prompts):
        res = results_raw[i]
        if isinstance(res, Exception):
            logger.error("[IMAGE] Scene %d failed permanently: %s", scene_id, res)
            results.append((scene_id, None, False))
        else:
            image_data, is_base64 = res
            results.append((scene_id, image_data, is_base64))

    return results
