"""
utils/image_prep.py
-------------------
Image preprocessing pipeline optimised for old-book scans.
Memory-optimised version for 512MB hosting environments.
"""

from __future__ import annotations

import logging
from typing import TypedDict

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

# Max dimension before resizing — keeps memory under 512MB
MAX_DIMENSION = 2000


class QualityReport(TypedDict):
    score: int
    warnings: list[str]
    suggestions: list[str]
    brightness: float
    contrast: float
    sharpness: float


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Apply preprocessing stack with memory optimisation.
    Resizes large images first to stay within 512MB limit.
    """
    # Resize if too large before any processing
    image = _resize_if_needed(image)

    img = image.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.5)
    arr: np.ndarray = np.array(img, dtype=np.uint8)

    # Skip denoising on free tier — most memory hungry step
    # try:
    #     arr = cv2.fastNlMeansDenoising(arr, None, h=10, templateWindowSize=7, searchWindowSize=21)
    # except Exception as exc:
    #     logger.warning("Denoising skipped: %s", exc)

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


def _resize_if_needed(image: Image.Image) -> Image.Image:
    """Resize image if either dimension exceeds MAX_DIMENSION."""
    w, h = image.size
    if max(w, h) <= MAX_DIMENSION:
        return image
    if w > h:
        new_w = MAX_DIMENSION
        new_h = int(h * MAX_DIMENSION / w)
    else:
        new_h = MAX_DIMENSION
        new_w = int(w * MAX_DIMENSION / h)
    logger.info("Resizing image from %dx%d to %dx%d", w, h, new_w, new_h)
    return image.resize((new_w, new_h), Image.LANCZOS)


def assess_image_quality(image: Image.Image) -> QualityReport:
    """Return a quality score (0-100) and actionable warnings."""
    image = _resize_if_needed(image)
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
        suggestions.append("Try boosting contrast before processing")
        score -= 20

    if lap_var < 50:
        warnings.append("Image appears blurry")
        suggestions.append("Hold camera steady and tap to focus on the text")
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
    """Estimate and correct skew using Hough line detection."""
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

    h, w = arr.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
    return cv2.warpAffine(
        arr, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
