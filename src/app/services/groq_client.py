"""
groq_client.py
──────────────
Async Groq LLM wrapper with retry logic and structured logging.
Model: llama-3.3-70b-versatile
"""

import asyncio
import json
import logging
import os
from typing import Optional

from groq import AsyncGroq, APIStatusError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("groq_client")

_client: Optional[AsyncGroq] = None
MODEL = "llama-3.3-70b-versatile"


def get_client() -> AsyncGroq:
    """Lazy-initialise the shared AsyncGroq client."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set in environment variables.")
        _client = AsyncGroq(api_key=api_key)
        logger.info("[GROQ] Client initialised.")
    return _client


@retry(
    retry=retry_if_exception_type((APIConnectionError, APIStatusError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def call_llm(
    prompt: str,
    system: str = "You are a helpful AI assistant.",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    Send a prompt to Groq and return the response text.

    Retries up to 3 times with exponential backoff on connection/status errors.
    Raises the final exception if all retries are exhausted.
    """
    client = get_client()
    logger.info("[GROQ] Sending request | prompt_len=%d", len(prompt))

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        ),
        timeout=30.0,
    )

    content = response.choices[0].message.content.strip()
    logger.info("[GROQ] Response received | response_len=%d", len(content))
    return content


async def call_llm_json(
    prompt: str,
    system: str = "You are a helpful AI assistant. Always respond with valid JSON only.",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """
    Call Groq and parse the response as JSON.
    Strips markdown fences if present.
    Raises ValueError if response cannot be parsed.
    """
    raw = await call_llm(prompt, system=system, temperature=temperature, max_tokens=max_tokens)

    # Strip ```json ... ``` fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
        return parsed
    except json.JSONDecodeError as exc:
        logger.error("[GROQ] JSON parse error: %s | raw=%s", exc, raw[:300])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc
