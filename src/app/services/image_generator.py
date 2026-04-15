"""
image_generator.py  (v3 — OpenRouter / gemini-2.5-flash-image)
───────────────────────────────────────────────────────────────
Replaces MiniMax with OpenRouter image generation.

- Model: google/gemini-2.5-flash-image
- Keys: OPENROUTER_KEY1, OPENROUTER_KEY2, OPENROUTER_KEY3 (round-robin)
- Thread-safe key rotation via itertools.cycle + asyncio.Lock
- Retries up to 3 times with key-switching on failure
- Returns placeholder URL on all failures — never returns empty
- All scenes generated in parallel via asyncio.gather

Response format from OpenRouter:
  choices[0].message.images[0].image_url.url  → "data:image/png;base64,..."
"""

import asyncio
import base64
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("image_generator")

OPENROUTER_URL  = "https://openrouter.ai/api/v1/chat/completions"
PLACEHOLDER_URL = "https://placehold.co/1024x576/0f1620/e8a43c?text=Scene+Unavailable"

# Model fallback list — cheapest/most reliable first
MODELS_TO_TRY = [
    "black-forest-labs/flux.2-klein-4b",
    "google/gemini-2.5-flash-image",
    "google/gemini-3.1-flash-image-preview",
    "google/gemini-3-pro-image-preview",
]

# Resolve static dir the same way main.py does so files are served at /static/<file>
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
logger_boot = logging.getLogger("image_generator")
logger_boot.info("[IMAGE] Static cache dir: %s", _STATIC_DIR)


# ── Key Pool ──────────────────────────────────────────────────────────────────

class OpenRouterKeyPool:
    """Thread-safe round-robin pool for OpenRouter API keys.
    Always reads fresh from .env so new keys are picked up without restart.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def _load_keys(self) -> List[Tuple[str, str]]:
        """Read all openrouter_keyN vars fresh from environment each time."""
        _env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        load_dotenv(_env_path, override=True)   # force re-read .env on every load
        keys: List[Tuple[str, str]] = []
        for i in range(1, 10):
            val = os.getenv(f"openrouter_key{i}", "").strip()
            if val:
                keys.append((f"or_key_{i}", val))
        if not keys:
            raise EnvironmentError(
                "No OpenRouter keys found. Set openrouter_key1, openrouter_key2, ... in .env"
            )
        logger.info(
            "[IMAGE] Key pool loaded: %d key(s) %s",
            len(keys), [k[0] for k in keys],
        )
        return keys

    async def get_all(self) -> List[Tuple[str, str]]:
        """Return all (label, key) pairs, freshly loaded."""
        async with self._lock:
            return self._load_keys()


_pool = OpenRouterKeyPool()


# ── Core API Call ─────────────────────────────────────────────────────────────

def _make_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "http://localhost:8000",
        "X-Title":       "AI Storyboard Generator",
    }


def _build_payload(prompt: str, model: str) -> dict:
    # Removed max_tokens: 250 because it was truncating high-res base64 image data.
    return {
        "model":      model,
        "messages":   [{"role": "user", "content": prompt}],
        "modalities": ["image"],
    }


def _extract_image(data: dict, scene_id: int) -> str:
    """
    Extract the base64 data URI or URL from OpenRouter response.
    Supports:
    - choices[0].message.images[0].image_url.url (Gemini/standard)
    - choices[0].message.content (Flux/some models)
    """
    try:
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"No choices in response: {list(data.keys())}")

        message  = choices[0].get("message", {})
        images   = message.get("images", [])
        content  = message.get("content", "")

        # 1. Check message.images[] (Standard AI image field)
        if images and isinstance(images, list):
            item = images[0]
            if isinstance(item, dict):
                url = item.get("image_url", {}).get("url", "")
                if url:
                    return url

        # 2. Check content (Flux / some models return data URI here)
        if isinstance(content, str) and (content.startswith("data:image") or content.startswith("http")):
            return content

        # 3. Check content if it's a list (multimodal response)
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url:
                        return url

        raise ValueError(f"No image URL found in message. keys: {list(message.keys())}")

    except Exception as exc:
        logger.debug("[IMAGE] _extract_image failed: %s", exc)
        raise ValueError(f"Scene {scene_id}: extraction failed — {exc}") from exc


# ── Per-Scene Generator ───────────────────────────────────────────────────────

async def _generate_one(scene_id: int, prompt: str) -> Tuple[str, bool]:
    """
    Generate one image with model fallback + key failover.
    Iteration: For each model, try all keys.
    Returns (static_url, False) on success, (PLACEHOLDER_URL, False) on all failures.
    """
    all_keys = await _pool.get_all()
    last_exc: Optional[Exception] = None

    for model in MODELS_TO_TRY:
        logger.info("[IMAGE] Scene %d | Trying model: %s", scene_id, model)
        
        for attempt, (label, api_key) in enumerate(all_keys, start=1):
            try:
                logger.debug("[IMAGE] Scene %d | %s | %s | attempt %d/%d",
                             scene_id, model, label, attempt, len(all_keys))

                # --- DEBUG INSTRUMENTATION ---
                payload = _build_payload(prompt, model)
                logger.debug("[IMAGE] Debug Payload for Scene %d: %s", scene_id, payload)

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        OPENROUTER_URL,
                        headers=_make_headers(api_key),
                        json=payload,
                        timeout=90.0,
                    )

                logger.info("[IMAGE] Scene %d | %s | %s | HTTP %d", 
                            scene_id, model, label, response.status_code)

                if response.status_code != 200:
                    logger.error("[DEBUG] Non-200 Response for Scene %d | Body: %s", scene_id, response.text)
                    if response.status_code == 402:
                        continue
                    if response.status_code == 429:
                        await asyncio.sleep(2)
                        continue
                    response.raise_for_status()

                # --- NEW: HEADER ANALYSIS ---
                logger.debug("[DEBUG] Headers for Scene %d: %s", scene_id, dict(response.headers))

                data = response.json()
                try:
                    data_uri = _extract_image(data, scene_id)
                    # --- NEW: DATA INTEGRITY CHECK ---
                    total_len = len(data_uri)
                    snippet_start = data_uri[:60]
                    snippet_end   = data_uri[-20:]
                    logger.info("[IMAGE] Scene %d | ✅ data_len=%d | starts=%s | ends=%s",
                                 scene_id, total_len, snippet_start, snippet_end)
                    
                    if total_len < 1000:
                        logger.warning("[DEBUG] Scene %d image data unusually short! Possible corruption.", scene_id)

                except ValueError as ve:
                    logger.error("[DEBUG] Extraction failed for Scene %d. Full JSON: %s", scene_id, data)
                    raise ve

                return data_uri, True

            except Exception as exc:
                last_exc = exc
                logger.warning("[IMAGE] Scene %d | %s | %s | attempt %d failed: %s",
                               scene_id, model, label, attempt, exc)
                # Brief sleep for transient errors
                if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code not in (401, 402, 403):
                    await asyncio.sleep(1)

    logger.error("[IMAGE] Scene %d | All models and keys failed. Last error: %s",
                 scene_id, last_exc)
    return PLACEHOLDER_URL, False


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_all_images(
    prompts: list[Tuple[int, str]],
) -> list[Tuple[int, str | bytes, bool]]:
    """
    Parallel image generation for all scenes.

    Args:
        prompts: list of (scene_id, prompt) tuples

    Returns:
        list of (scene_id, image_data, is_base64)
        - is_base64=True  → image_data is raw bytes → Cloudinary will upload
        - is_base64=False → image_data is placeholder URL string → pass-through
    """
    logger.info("[IMAGES] Generating %d images in parallel via OpenRouter...", len(prompts))

    tasks = [_generate_one(sid, prompt) for sid, prompt in prompts]
    raw   = await asyncio.gather(*tasks)   # never raises — each task catches its own errors

    results = []
    for (scene_id, _), (image_data, is_base64) in zip(prompts, raw):
        results.append((scene_id, image_data, is_base64))
        if isinstance(image_data, str) and image_data.startswith("/static/"):
            logger.info("[IMAGES] Scene %d -> %s", scene_id, image_data)
        else:
            logger.info("[IMAGES] Scene %d -> placeholder", scene_id)

    logger.info("[IMAGES] All %d images resolved.", len(results))
    return results
