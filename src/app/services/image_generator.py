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
PLACEHOLDER_URL = "https://placehold.co/1024x576/0f1620/e8a43c?text=Scene+Unavailable"


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
    response = await client.post(
        MINIMAX_API_URL,
        headers=_get_headers(),
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def _parse_response(data: dict, scene_id: int) -> Tuple[str | bytes, bool]:
    """
    Parse MiniMax response → (image_data, is_base64).
    Tries multiple known response shapes.
    """
    # Shape 1: data.images[0].url / b64_json
    try:
        images = data.get("data", {}).get("images", [])
        if images:
            img = images[0]
            if img.get("url"):
                logger.info("[IMAGE] Scene %d → URL received", scene_id)
                return img["url"], False
            if img.get("b64_json"):
                logger.info("[IMAGE] Scene %d → base64 received", scene_id)
                return base64.b64decode(img["b64_json"]), True
    except (KeyError, IndexError, TypeError):
        pass

    # Shape 2: top-level url / b64_json
    if data.get("image_url"):
        return data["image_url"], False
    if data.get("b64_json"):
        return base64.b64decode(data["b64_json"]), True

    # Shape 3: data is a list directly
    if isinstance(data.get("data"), list) and data["data"]:
        item = data["data"][0]
        if isinstance(item, dict):
            if item.get("url"):
                return item["url"], False
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"]), True

    raise ValueError(f"Scene {scene_id}: Unrecognised MiniMax response shape: {str(data)[:200]}")


async def generate_image(
    scene_id: int,
    prompt: str,
    client: httpx.AsyncClient,
) -> Tuple[str | bytes, bool]:
    """
    Generate one image. On any failure returns placeholder URL.
    Never raises; always returns a usable (image_data, is_base64) tuple.
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
) -> list[Tuple[int, str | bytes, bool]]:
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
