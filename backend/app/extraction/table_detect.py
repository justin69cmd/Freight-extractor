"""L1 — table grid detection for scanned pages (OpenCV).

Given a page image, deskew it and detect the table's cell grid by finding
horizontal/vertical ruling lines via morphology, then return cell bounding
boxes for per-cell OCR. Per-cell OCR (vs whole-page) materially improves number
accuracy and yields per-cell confidence used for band routing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CellBox:
    row: int
    col: int
    x0: int
    y0: int
    x1: int
    y1: int


def deskew(image):
    """Rotate an image so text/lines are axis-aligned. Returns the corrected image."""
    import cv2  # lazy
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    (h, w) = image.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def detect_cell_grid(image) -> list[CellBox]:
    """Detect table cells by intersecting horizontal & vertical ruling lines."""
    import cv2  # lazy
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    bw = cv2.adaptiveThreshold(
        ~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2
    )

    h, w = bw.shape
    horiz = cv2.erode(bw, cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 40, 1), 1)))
    horiz = cv2.dilate(horiz, cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 40, 1), 1)))
    vert = cv2.erode(bw, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 40, 1))))
    vert = cv2.dilate(vert, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 40, 1))))

    ys = _line_positions(horiz, axis=0)
    xs = _line_positions(vert, axis=1)

    boxes: list[CellBox] = []
    for r in range(len(ys) - 1):
        for c in range(len(xs) - 1):
            boxes.append(
                CellBox(row=r, col=c, x0=xs[c], y0=ys[r], x1=xs[c + 1], y1=ys[r + 1])
            )
    return boxes


def _line_positions(mask, axis: int, min_gap: int = 10) -> list[int]:
    """Collapse a ruling-line mask into a sorted list of grid-line coordinates."""
    import numpy as np

    projection = mask.sum(axis=axis)
    threshold = projection.max() * 0.3 if projection.max() else 0
    positions = [int(i) for i, v in enumerate(projection) if v > threshold]
    # merge adjacent positions into single grid lines
    merged: list[int] = []
    for p in positions:
        if not merged or p - merged[-1] > min_gap:
            merged.append(p)
    return merged
