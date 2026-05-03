"""
core/merger.py
--------------
Merge a sequence of per-page OCR results into a single, structured
Markdown document.

Chapter / heading detection cascade:
    # (H1)  — "CHAPTER I", "Chapter 1", "PART TWO", bare Roman numerals
    ## (H2) — Short ALL-CAPS lines, numbered sub-sections ("1.2 Title")
    ### (H3) — Short title-cased lines with no sentence-ending punctuation

Pages are separated by HTML comments (<!-- page N -->) invisible in EPUB.
Output is valid Markdown that Calibre can process directly.
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

from core.cleanup import clean_text

logger = logging.getLogger(__name__)

_H1_PATTERNS: list[re.Pattern] = [  # type: ignore[type-arg]
    re.compile(r"^(CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\b", re.IGNORECASE),
    re.compile(r"^(PART|Book|Section)\s+([IVXLCDM]+|\d+)\b", re.IGNORECASE),
    re.compile(r"^[IVXLCDM]+\.$"),
    re.compile(r"^\d{1,2}\.$"),
]

_H2_PATTERNS: list[re.Pattern] = [  # type: ignore[type-arg]
    re.compile(r"^\d{1,2}\.\d{1,2}\s+[A-Z]"),
    re.compile(r"^[A-Z][A-Z\s\-]{4,60}$"),
]

_H3_PATTERNS: list[re.Pattern] = [  # type: ignore[type-arg]
    re.compile(r"^([A-Z][a-z]+ ){2,6}[A-Z][a-z]+$"),
]

_PAGE_NUMBER_RE = re.compile(r"^\s*[\[\(]?\d{1,4}[\]\)]?\s*$")
_ARTEFACT_RE = re.compile(r"^\s*.{0,2}\s*$")


class PageData(TypedDict):
    page: int
    text: str
    method: str       # "tesseract" | "claude" | "error"
    confidence: float
    source: str       # original file path


def merge_pages(pages: list[PageData], fix_spelling: bool = False) -> str:
    """Merge OCR page results into a single Markdown string."""
    sections: list[str] = []

    for page_data in pages:
        page_num = page_data["page"]
        raw_text = page_data.get("text", "")

        if not raw_text.strip():
            logger.warning("Page %d produced no text — skipping.", page_num)
            continue

        cleaned = clean_text(raw_text, fix_spelling=fix_spelling)
        sections.append(f"<!-- page {page_num} -->")
        sections.append(_structure_page(cleaned, page_num))
        sections.append("")

    document = "\n".join(sections)
    document = re.sub(r"\n{3,}", "\n\n", document)
    return document.strip()


def _structure_page(text: str, page_num: int) -> str:
    output_lines: list[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()

        if _PAGE_NUMBER_RE.match(line):
            logger.debug("Page %d: stripped page-number line %r", page_num, line)
            continue

        stripped = line.strip()

        if not stripped:
            output_lines.append("")
            continue

        if any(p.match(stripped) for p in _H1_PATTERNS):
            output_lines.append(f"\n# {stripped}\n")
            continue

        if len(stripped) <= 80 and any(p.match(stripped) for p in _H2_PATTERNS):
            output_lines.append(f"\n## {stripped}\n")
            continue

        if (
            len(stripped) <= 60
            and not stripped[-1] in ".!?,:;"
            and any(p.match(stripped) for p in _H3_PATTERNS)
        ):
            output_lines.append(f"\n### {stripped}\n")
            continue

        output_lines.append(line)

    return "\n".join(output_lines)
