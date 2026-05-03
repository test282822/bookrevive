"""
core/ocr.py
-----------
OCR pipeline with two tiers:

  Tier 1 — pytesseract
    Fast, local, no API cost. Works well for clean scans.

  Tier 2 — Claude vision (via Anthropic SDK)
    Used automatically when Tesseract confidence falls below
    CONFIDENCE_THRESHOLD, or when Tesseract is not installed.
    Requires ANTHROPIC_API_KEY in the environment.

Returns a structured OCRResult so callers always receive consistent data
regardless of which tier was used.
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from PIL import Image

if TYPE_CHECKING:
    import anthropic  # type: ignore[import]

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD: float = 60.0
CLAUDE_VISION_MODEL = "claude-opus-4-6"


@dataclass
class OCRResult:
    text: str
    confidence: float           # 0–100; Claude results use 95.0 as placeholder
    method: str                 # "tesseract" | "claude" | "error"
    warnings: list[str] = field(default_factory=list)


def ocr_image(
    image: Image.Image,
    page_num: int = 1,
    use_claude: bool = True,
    anthropic_client: Optional["anthropic.Anthropic"] = None,
    lang: str = "eng",
) -> OCRResult:
    """
    Run OCR on a preprocessed PIL Image.

    Args:
        image:             Preprocessed PIL Image (grayscale/binarised recommended).
        page_num:          1-based page number for logging/warnings.
        use_claude:        Whether to attempt Claude vision on low-confidence pages.
        anthropic_client:  An initialised anthropic.Anthropic instance, or None.
        lang:              Tesseract language code (e.g. "eng", "fra", "deu").

    Returns:
        OCRResult with text, confidence, method, and any user-facing warnings.
    """
    warnings: list[str] = []

    try:
        import pytesseract

        data = pytesseract.image_to_data(
            image,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )

        confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
        avg_conf = float(sum(confs) / len(confs)) if confs else 0.0

        text = pytesseract.image_to_string(image, lang=lang)

        if avg_conf >= CONFIDENCE_THRESHOLD or not use_claude or anthropic_client is None:
            if avg_conf < CONFIDENCE_THRESHOLD:
                warnings.append(
                    f"Page {page_num}: Tesseract confidence is {avg_conf:.0f}% "
                    f"(threshold {CONFIDENCE_THRESHOLD:.0f}%). "
                    "Consider retaking the photo or setting ANTHROPIC_API_KEY for "
                    "the Claude vision fallback."
                )
            return OCRResult(
                text=text,
                confidence=avg_conf,
                method="tesseract",
                warnings=warnings,
            )

        logger.info(
            "Page %d: Tesseract confidence %.0f%% < %.0f%% — using Claude vision.",
            page_num, avg_conf, CONFIDENCE_THRESHOLD,
        )
        claude_text = _ocr_with_claude(image, page_num, anthropic_client)

        if claude_text:
            return OCRResult(
                text=claude_text,
                confidence=95.0,
                method="claude",
                warnings=warnings,
            )

        warnings.append(
            f"Page {page_num}: Both OCR tiers returned uncertain results. "
            "Manual review is recommended."
        )
        return OCRResult(
            text=text,
            confidence=avg_conf,
            method="tesseract",
            warnings=warnings,
        )

    except ImportError:
        logger.warning("pytesseract not available — trying Claude vision only.")

    except Exception as exc:
        if "tesseract is not installed" in str(exc).lower() or "not found" in str(exc).lower():
            logger.warning("Tesseract binary not found — trying Claude vision only.")
        else:
            logger.error("Tesseract error on page %d: %s", page_num, exc)

    if anthropic_client:
        claude_text = _ocr_with_claude(image, page_num, anthropic_client)
        if claude_text:
            return OCRResult(
                text=claude_text,
                confidence=95.0,
                method="claude",
                warnings=[],
            )

    raise RuntimeError(
        f"OCR failed for page {page_num}. "
        "Install Tesseract (https://github.com/tesseract-ocr/tesseract) "
        "or set ANTHROPIC_API_KEY to enable Claude vision."
    )


_CLAUDE_PROMPT = (
    "This is page {page_num} of an old printed book. "
    "Transcribe ALL text exactly as it appears on the page. "
    "Preserve paragraph breaks and the original line structure. "
    "Do NOT add commentary, markdown headings, or extra formatting — "
    "return only the plain transcribed text. "
    "Fix obvious scanning artifacts (stray specks acting as characters, "
    "broken letter strokes) but preserve the original spelling, "
    "capitalisation, and punctuation faithfully."
)


def _ocr_with_claude(
    image: Image.Image,
    page_num: int,
    client: "anthropic.Anthropic",
) -> Optional[str]:
    try:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64_data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

        response = client.messages.create(
            model=CLAUDE_VISION_MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": _CLAUDE_PROMPT.format(page_num=page_num),
                        },
                    ],
                }
            ],
        )
        return response.content[0].text

    except Exception as exc:
        logger.error("Claude vision failed for page %d: %s", page_num, exc)
        return None
