"""
core/cleanup.py
---------------
Text cleanup for raw OCR output.

Handles the most common artefacts found when digitising old books:
  - Unicode ligatures (ﬁ → fi, ﬂ → fl, etc.)
  - End-of-line hyphenation ("exam-\nexample" → "example")
  - Stray control characters and excessive whitespace
  - Windows / mixed line endings
  - Optional conservative spell correction (off by default)

Design principles:
  - Conservative: only fix things we're confident about.
  - Idempotent: running clean_text twice gives the same result.
  - No external API calls — this module is entirely offline.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_LIGATURE_MAP: dict[str, str] = {
    "\ufb00": "ff",   # ﬀ
    "\ufb01": "fi",   # ﬁ
    "\ufb02": "fl",   # ﬂ
    "\ufb03": "ffi",  # ﬃ
    "\ufb04": "ffl",  # ﬄ
    "\ufb05": "st",   # ﬅ
    "\ufb06": "st",   # ﬆ
    "\u00e6": "ae",   # æ
    "\u0153": "oe",   # œ
}

_HYPHEN_EOL_RE = re.compile(r"(\w+)-\n(\w+)")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_spell_checker = None


def clean_text(raw_text: str, fix_spelling: bool = False) -> str:
    """
    Clean raw OCR text and return a normalised string.

    Args:
        raw_text:     Text as returned by pytesseract or Claude.
        fix_spelling: If True, apply conservative spell correction using
                      pyspellchecker. Disabled by default because it can
                      corrupt technical terms, proper nouns, and archaic
                      spellings common in old books.
    """
    if not raw_text:
        return ""

    text = raw_text

    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHAR_RE.sub("", text)
    text = _HYPHEN_EOL_RE.sub(_rejoin_hyphen, text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    if fix_spelling:
        text = _spell_fix(text)

    return text.strip()


def _rejoin_hyphen(match: re.Match) -> str:  # type: ignore[type-arg]
    word1, word2 = match.group(1), match.group(2)
    compound = word1 + word2
    try:
        checker = _get_spell_checker()
        if compound.lower() in checker:
            return compound
        return word1 + "-" + word2
    except Exception:
        return word1 + "-" + word2


def _spell_fix(text: str) -> str:
    try:
        checker = _get_spell_checker()
    except Exception:
        logger.warning("pyspellchecker not available; spell correction skipped.")
        return text

    tokens = text.split()
    result: list[str] = []

    for token in tokens:
        stripped = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", token)

        if (
            not stripped
            or len(stripped) < 4
            or stripped[0].isupper()
            or stripped.lower() in checker
        ):
            result.append(token)
            continue

        suggestion = checker.correction(stripped)
        if suggestion and suggestion != stripped:
            corrected = token.replace(stripped, suggestion, 1)
            logger.debug("Spell fix: %r → %r", stripped, suggestion)
            result.append(corrected)
        else:
            result.append(token)

    return " ".join(result)


def _get_spell_checker():
    global _spell_checker
    if _spell_checker is None:
        from spellchecker import SpellChecker  # type: ignore[import]
        _spell_checker = SpellChecker()
    return _spell_checker
