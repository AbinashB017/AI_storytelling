"""
groq_client.py
──────────────
Async Groq LLM wrapper with:
- Multi-key round-robin load balancing (GROQ_API_KEY_1, GROQ_API_KEY_2)
- Thread-safe key selection via asyncio.Lock + itertools.cycle
- Retry with key failover (max 3 retries, switches key on each retry)
- Structured logging per call

Exposes:
  call_llm(prompt, system, temperature, max_tokens) -> str
  call_llm_json(prompt, system, temperature, max_tokens) -> dict
"""

import asyncio
import itertools
import json
import logging
import os
from typing import Iterator, List, Optional, Tuple

from groq import AsyncGroq, APIStatusError, APIConnectionError

logger = logging.getLogger("groq_client")

MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30.0

# ─── Key Pool ──────────────────────────────────────────────────────────────

class GroqKeyPool:
    """Thread-safe round-robin Groq API key pool."""

    def __init__(self) -> None:
        self._keys: List[Tuple[str, str]] = []   # list of (label, api_key)
        self._cycle: Optional[Iterator] = None
        self._clients: dict[str, AsyncGroq] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    def _load_keys(self) -> None:
        """Load keys from environment variables."""
        keys = []
        for i in range(1, 10):  # Support up to 9 keys
            val = os.getenv(f"GROQ_API_KEY_{i}")
            if val:
                keys.append((f"key_{i}", val))

        # Fallback: legacy single-key support
        if not keys:
            single = os.getenv("GROQ_API_KEY")
            if single:
                keys.append(("key_1", single))

        if not keys:
            raise EnvironmentError(
                "No Groq API keys found. Set GROQ_API_KEY_1 and/or GROQ_API_KEY_2 in .env"
            )

        self._keys = keys
        self._cycle = itertools.cycle(keys)
        for label, key in keys:
            self._clients[label] = AsyncGroq(api_key=key)

        logger.info("[GROQ] Key pool initialised with %d key(s): %s", len(keys), [k[0] for k in keys])
        self._initialized = True

    async def next_client(self) -> Tuple[str, AsyncGroq]:
        """Return the next (label, AsyncGroq client) in round-robin order. Thread-safe."""
        async with self._lock:
            if not self._initialized:
                self._load_keys()
            label, _ = next(self._cycle)
            return label, self._clients[label]

    def client_for_next_key(self, current_label: str) -> Tuple[str, AsyncGroq]:
        """Return the next key after the given one (for failover). Not lock-guarded (retry context)."""
        labels = [k[0] for k in self._keys]
        idx = labels.index(current_label) if current_label in labels else -1
        next_idx = (idx + 1) % len(labels)
        next_label = labels[next_idx]
        return next_label, self._clients[next_label]


# Singleton pool
_pool = GroqKeyPool()


# ─── Core LLM Call ────────────────────────────────────────────────────────

async def call_llm(
    prompt: str,
    system: str = "You are a helpful AI assistant.",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    Send a prompt to Groq with round-robin key selection and retry-with-failover.

    - Tries up to MAX_RETRIES times
    - Switches to next key on each retry
    - Logs key used, retries, and failures
    """
    label, client = await _pool.next_client()
    last_exc: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("[GROQ] Using %s | attempt=%d | prompt_len=%d", label, attempt, len(prompt))

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
                timeout=TIMEOUT_SECONDS,
            )

            content = response.choices[0].message.content.strip()
            logger.info("[GROQ] Request successful | %s | response_len=%d", label, len(content))
            return content

        except (APIConnectionError, APIStatusError, asyncio.TimeoutError) as exc:
            last_exc = exc
            logger.warning("[GROQ] %s failed on attempt %d: %s", label, attempt, exc)

            if attempt < MAX_RETRIES:
                # Switch to next key for failover
                label, client = _pool.client_for_next_key(label)
                logger.info("[GROQ] Retry with %s", label)
                await asyncio.sleep(2 ** (attempt - 1))  # backoff: 1s, 2s

    logger.error("[GROQ] All %d attempts failed. Last error: %s", MAX_RETRIES, last_exc)
    raise last_exc


# ─── JSON Helper ──────────────────────────────────────────────────────────

async def call_llm_json(
    prompt: str,
    system: str = "You are a helpful AI assistant. Always respond with valid JSON only.",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """
    Call Groq and parse the response as JSON.
    Strips markdown fences (```json ... ```) if present.
    Raises ValueError if response cannot be parsed.
    """
    raw = await call_llm(prompt, system=system, temperature=temperature, max_tokens=max_tokens)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("[GROQ] JSON parse error: %s | raw=%s", exc, raw[:300])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc
