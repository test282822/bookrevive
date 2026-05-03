"""
utils/image_prep.py
-------------------
Image preprocessing pipeline optimised for old-book scans.

Steps applied before OCR:
  1. Convert to grayscale
  2. Enhance contrast (Pillow, 1.5×)
  3. Denoise (OpenCV Non-local Means)
  4. CLAHE (improves faded/yellowed pages)
  5. Deskew via Hough line detection
  6. Adaptive binarisation (handles shadows, yellowing, gradients)

Also provides assess_image_quality() with actionable retake suggestions.
"""

from __future__ import annotations

import logging
from typing import TypedDict

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


class QualityReport(TypedDict):
    score: int          # 0-100
    warnings: list[str]
    suggestions: list[str]
    brightness: float
    contrast: float
    sharpness: float


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Apply full preprocessing stack. Each step fails gracefully.
    Returns a binarised, deskewed PIL Image ready for Tesseract.
    """
    img = image.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.5)
    arr: np.ndarray = np.array(img, dtype=np.uint8)

    try:
        arr = cv2.fastNlMeansDenoising(arr, None, h=10, templateWindowSize=7, searchWindowSize=21)
    except Exception as exc:
        logger.warning("Denoising skipped: %s", exc)

    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        arr = clahe.apply(arr)
    except Exception as exc:
        logger.warning("CLAHE skipped: %s", exc)

    try:
        arr = _deskew(arr)
    except Exception as exc:
        logger.warning("Deskew skipped: %s", exc)

    try:
        arr = cv2.adaptiveThreshold(
            arr, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10,
        )
    except Exception as exc:
        logger.warning("Binarisation skipped: %s", exc)

    return Image.fromarray(arr)


def assess_image_quality(image: Image.Image) -> QualityReport:
    """
    Return a quality score (0-100) and actionable warnings.

    Penalties:
      -20  too dark (mean brightness < 80)
      -10  overexposed (mean brightness > 220)
      -20  low contrast (std dev < 30) — faded ink
      -30  blurry (Laplacian variance < 50)
    """
    arr = np.array(image.convert("L"), dtype=np.uint8)

    warnings: list[str] = []
    suggestions: list[str] = []
    score = 100

    mean_brightness = float(arr.mean())
    std_contrast = float(arr.std())
    lap_var = float(cv2.Laplacian(arr, cv2.CV_64F).var())

    if mean_brightness < 80:
        warnings.append("Image is too dark")
        suggestions.append("Photograph near a window or under bright ambient light")
        score -= 20
    elif mean_brightness > 220:
        warnings.append("Image is overexposed / washed out")
        suggestions.append("Avoid direct flash; use soft diffused lighting")
        score -= 10

    if std_contrast < 30:
        warnings.append("Very low contrast — ink may be too faded")
        suggestions.append(
            "Try a photo-editing app to boost contrast before processing, "
            "or use the Claude vision fallback (set ANTHROPIC_API_KEY)"
        )
        score -= 20

    if lap_var < 50:
        warnings.append("Image appears blurry")
        suggestions.append(
            "Hold the camera steady, use tap-to-focus on the text, "
            "and ensure the page is flat and fully in frame"
        )
        score -= 30

    return QualityReport(
        score=max(0, score),
        warnings=warnings,
        suggestions=suggestions,
        brightness=mean_brightness,
        contrast=std_contrast,
        sharpness=lap_var,
    )


def _deskew(arr: np.ndarray) -> np.ndarray:
    """Estimate and correct skew using Hough line detection. Only corrects < 45°."""
    edges = cv2.Canny(arr, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, rho=1, theta=np.pi / 180, threshold=100)

    if lines is None:
        return arr

    angles: list[float] = []
    for line in lines[:30]:
        rho, theta = line[0]
        angle = float(np.degrees(theta)) - 90.0
        if abs(angle) < 45.0:
            angles.append(angle)

    if not angles:
        return arr

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return arr

    logger.debug("Correcting skew by %.2f°", median_angle)
    h, w = arr.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
    return cv2.warpAffine(
        arr, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
