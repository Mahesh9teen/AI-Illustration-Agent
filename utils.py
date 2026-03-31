"""
AI Illustration Agent — Utilities
===================================
Shared helper functions used across the agent pipeline and API layer.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("illustration_agent.utils")


# ─────────────────────────────────────────
# Text Helpers
# ─────────────────────────────────────────

def sanitise_prompt(raw: str, max_length: int = 1000) -> str:
    """
    Strip leading/trailing whitespace, collapse internal runs of whitespace,
    and truncate to *max_length* characters.

    >>> sanitise_prompt("  hello   world  ")
    'hello world'
    """
    cleaned = re.sub(r"\s+", " ", raw.strip())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
        logger.debug("Prompt truncated to %d characters.", max_length)
    return cleaned


def slugify(text: str) -> str:
    """
    Convert a string to a URL-safe slug.

    >>> slugify("Digital Art / Concept")
    'digital-art-concept'
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text


def truncate_for_log(text: str, max_chars: int = 120) -> str:
    """Return a truncated string safe for logging."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


# ─────────────────────────────────────────
# JSON Helpers
# ─────────────────────────────────────────

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to extract a JSON object from a string that may contain
    markdown fences, explanatory text, or other surrounding content.

    Returns the parsed dict on success, or None on failure.
    """
    # Remove markdown fences
    clean = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()

    # Try parsing the whole thing first
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Fall back: find the first {...} block
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.warning("Could not extract JSON from text: %s", truncate_for_log(text))
    return None


# ─────────────────────────────────────────
# Hashing / Caching Utilities
# ─────────────────────────────────────────

def prompt_fingerprint(
    prompt: str,
    style: Optional[str] = None,
    aspect_ratio: str = "16:9",
) -> str:
    """
    Generate a deterministic SHA-256 fingerprint for a given prompt + params.
    Useful for caching / deduplication at the application level.
    """
    key = json.dumps(
        {"prompt": prompt.lower().strip(), "style": style, "ar": aspect_ratio},
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()


# ─────────────────────────────────────────
# Timing Utility
# ─────────────────────────────────────────

class Timer:
    """
    Simple context manager for measuring elapsed time.

    Usage::

        with Timer() as t:
            do_something()
        print(t.elapsed_ms)  # e.g. 342
    """

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((self._end - self._start) * 1000)


# ─────────────────────────────────────────
# Validation Helpers
# ─────────────────────────────────────────

SAFE_ASPECT_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}
SAFE_DETAIL_LEVELS = {"simple", "moderate", "detailed"}

SUPPORTED_STYLES = {
    "watercolor", "oil_painting", "pencil_sketch", "digital_art",
    "anime", "photorealistic", "impressionist", "minimalist",
    "concept_art", "comic_book", "pixel_art", "surrealism",
}


def validate_style(style: Optional[str]) -> Optional[str]:
    """
    Normalise and validate a style string.
    Returns the normalised style or None if the input is None.
    Raises ValueError for unrecognised styles.
    """
    if style is None:
        return None
    normalised = style.lower().replace(" ", "_").replace("-", "_")
    if normalised not in SUPPORTED_STYLES:
        raise ValueError(
            f"Unsupported style '{style}'. "
            f"Choose from: {', '.join(sorted(SUPPORTED_STYLES))}"
        )
    return normalised


def build_error_payload(errors: list[str]) -> Dict[str, Any]:
    """Format a list of error strings into a consistent API error payload."""
    return {
        "success": False,
        "errors": errors,
        "illustration_description": "",
    }
