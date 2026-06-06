from __future__ import annotations

from typing import Any

_TIKTOKEN_ENCODING: Any = None


def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken cl100k_base, fall back to word-count heuristic."""
    if not text:
        return 0
    global _TIKTOKEN_ENCODING  # noqa: PLW0603
    try:
        if _TIKTOKEN_ENCODING is None:
            import tiktoken  # noqa: PLC0415

            _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")  # noqa: PLC0415
        return len(_TIKTOKEN_ENCODING.encode(text))
    except ImportError:
        return max(1, len(text.split()) * 13 // 10)
