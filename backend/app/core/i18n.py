"""Bilingual translation framework for backend messages."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
_FALLBACK_LANG = "en"


@lru_cache(maxsize=4)
def _load_messages(lang: str) -> dict[str, str]:
    """Load the messages JSON file for the given language."""
    path = _LOCALES_DIR / lang / "messages.json"
    if not path.exists():
        logger.warning("Locale file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def translate(lang: str, key: str, **kwargs: str) -> str:
    """Return the translated string for *key* in *lang*.

    Falls back to English, then to the raw key if not found.
    Supports ``{placeholder}`` interpolation via *kwargs*.
    """
    messages = _load_messages(lang)
    text = messages.get(key)
    if text is None and lang != _FALLBACK_LANG:
        text = _load_messages(_FALLBACK_LANG).get(key)
    if text is None:
        return key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
