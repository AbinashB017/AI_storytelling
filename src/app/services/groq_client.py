"""
groq_client.py  (v3)
────────────────────
- Supports N Groq API keys: GROQ_API_KEY_1, GROQ_API_KEY_2, ... (auto-detected)
- Round-robin distribution via itertools.cycle + asyncio.Lock
- Key-switching failover on every retry (max 3 attempts)
- Falls back to legacy GROQ_API_KEY if no numbered keys found
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
PLACEHOLDER_IMG = "https://placehold.co/1024x576/1a1a2e/ffffff?text=Scene+Unavailable"


# ── Key Pool ─────────────────────────────────────────────────────────────────

class GroqKeyPool:
    """Thread-safe round-robin Groq API key pool. Supports any number of keys."""

    def __init__(self) -> None:
        self._keys: List[Tuple[str, str]] = []
        self._cycle: Optional[Iterator] = None
        self._clients: dict[str, AsyncGroq] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    def _load_keys(self) -> None:
        keys: List[Tuple[str, str]] = []

        # Auto-detect GROQ_API_KEY_1, _2, _3 ... _N
        for i in range(1, 20):
            val = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
            if val:
                keys.append((f"key_{i}", val))

        # Legacy fallback: single GROQ_API_KEY
        if not keys:
            single = os.getenv("GROQ_API_KEY", "").strip()
            if single:
                keys.append(("key_1", single))

        if not keys:
            raise EnvironmentError(
                "No Groq API keys found. Set GROQ_API_KEY_1 (and optionally _2, _3 ...) in .env"
            )

        self._keys = keys
        self._cycle = itertools.cycle(keys)
        self._clients = {label: AsyncGroq(api_key=key) for label, key in keys}
        self._initialized = True
        logger.info(
            "[GROQ] Key pool ready: %d key(s) → %s",
            len(keys),
            [k[0] for k in keys],
        )

    async def next_client(self) -> Tuple[str, AsyncGroq]:
        """Return next (label, client) in round-robin order. Async-safe."""
        async with self._lock:
            if not self._initialized:
                self._load_keys()
            label, _ = next(self._cycle)
            return label, self._clients[label]

    def failover_client(self, current_label: str) -> Tuple[str, AsyncGroq]:
        """Return the next key after current_label (for failover). No lock needed."""
        labels = [k[0] for k in self._keys]
        if not labels:
            raise RuntimeError("Key pool is empty.")
        idx = labels.index(current_label) if current_label in labels else -1
        next_label = labels[(idx + 1) % len(labels)]
        return next_label, self._clients[next_label]


_pool = GroqKeyPool()


# ── Core LLM Call ─────────────────────────────────────────────────────────────

async def call_llm(
    prompt: str,
    system: str = "You are a helpful AI assistant.",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    Call Groq with round-robin key selection and retry-with-key-failover.
    Max MAX_RETRIES attempts; switches key on each retry.
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
                        {"role": "user",   "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            logger.debug("[GROQ] raw response received (attempt %d)", attempt)
            content = response.choices[0].message.content.strip()
            logger.debug("[GROQ] raw content: %s", content[:500])
            logger.info("[GROQ] Request successful | %s | response_len=%d", label, len(content))
            return content

        except (APIConnectionError, APIStatusError, asyncio.TimeoutError) as exc:
            last_exc = exc
            logger.warning("[GROQ] %s failed on attempt %d: %s", label, attempt, exc)
            if attempt < MAX_RETRIES:
                label, client = _pool.failover_client(label)
                logger.info("[GROQ] Retry with %s", label)
                await asyncio.sleep(2 ** (attempt - 1))

    logger.error("[GROQ] All %d attempts failed. Last error: %s", MAX_RETRIES, last_exc)
    raise last_exc  # caller decides how to handle


# ── JSON Helper ───────────────────────────────────────────────────────────────

async def call_llm_json(
    prompt: str,
    system: str = "You are a helpful AI assistant. Always respond with valid JSON only.",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """Call Groq and parse response as JSON. Strips markdown fences automatically."""
    logger.debug("[GROQ] call_llm_json initiated. prompt_len=%d", len(prompt))
    raw = await call_llm(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(cleaned)
        logger.debug("[GROQ] JSON successfully parsed: %s", str(parsed)[:300])
        return parsed
    except json.JSONDecodeError as exc:
        logger.error("[GROQ] JSON parse error: %s | raw=%s", exc, raw[:300])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc
