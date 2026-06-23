"""L1 — table grid detection for scanned pages (OpenCV).
Given a page image, deskew it and detect the table's cell grid by finding
horizontal/vertical ruling lines via morphology, then return cell bounding
boxes for per-cell OCR.
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

    # Detect line fragments with a SMALL kernel, then bridge gaps with a LARGER
    # dilation so broken/faint scanned lines reconnect into continuous rulings.
    h_detect = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 100, 1), 1))
    h_bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 20, 1), 1))
    horiz = cv2.erode(bw, h_detect)
    horiz = cv2.dilate(horiz, h_bridge)

    v_detect = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 100, 1)))
    v_bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 20, 1)))
    vert = cv2.erode(bw, v_detect)
    vert = cv2.dilate(vert, v_bridge)

    # Threshold set from measured data: real rulings should now span much more.
    ys = _line_positions(horiz, axis=1, full_extent=w, min_frac=0.30)
    xs = _line_positions(vert, axis=0, full_extent=h, min_frac=0.30)

    boxes: list[CellBox] = []
    if len(ys) < 2 or len(xs) < 2:
        return boxes

    # Drop rows far taller than the median -> prose/footer text, not table rows.
    row_heights = sorted(ys[i + 1] - ys[i] for i in range(len(ys) - 1))
    median_h = row_heights[len(row_heights) // 2]
    max_h = median_h * 3 if median_h else float("inf")

    for r in range(len(ys) - 1):
        if ys[r + 1] - ys[r] > max_h:
            continue
        for c in range(len(xs) - 1):
            boxes.append(
                CellBox(row=r, col=c, x0=xs[c], y0=ys[r], x1=xs[c + 1], y1=ys[r + 1])
            )
    return boxes


def _line_positions(
    mask, axis: int, full_extent: int, min_frac: float = 0.5, min_gap: int = 15
) -> list[int]:
    """Collapse a ruling-line mask into a sorted list of grid-line coordinates.

    A position only counts as a gridline if its projected ink covers at least
    `min_frac` of `full_extent` (the table's width for horizontal lines, height
    for vertical). This rejects text strokes / artifacts that previously
    inflated the cell count by ~10x.
    """
    projection = mask.sum(axis=axis)
    # mask is 0/255; convert each row/col's summed ink into a covered-pixel count.
    covered = projection / 255.0
    threshold = full_extent * min_frac

    positions = [int(i) for i, v in enumerate(covered) if v >= threshold]

    # merge adjacent positions (a thick line spans several pixels) into one
    merged: list[int] = []
    for p in positions:
        if not merged or p - merged[-1] > min_gap:
            merged.append(p)
    return merged