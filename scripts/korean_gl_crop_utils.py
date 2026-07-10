"""한국인 녹내장 합본 이미지 크롭 경계 감지 (modified + origin 공통)."""
from __future__ import annotations

import numpy as np


def find_sub_boundaries(region: np.ndarray) -> tuple[int, int]:
    """
    하단 OD 또는 OS 영역 내에서 두 이미지의 경계를 자동 감지.
    가장 어두운 열(검은 구분선)을 찾아 반환.

    반환: (split_col, total_width) — split_col은 region 기준 좌측 오프셋
    """
    _h, w = region.shape[:2]
    if w < 8:
        return w // 2, w
    col_means = region.mean(axis=(0, 2))
    cs, ce = int(w * 0.25), int(w * 0.75)
    if ce <= cs:
        return w // 2, w
    split = cs + int(col_means[cs:ce].argmin())
    return split, w


def build_bottom_color_boxes(
    img_bgr: np.ndarray,
    split_row: int,
) -> tuple[dict[str, tuple[int, int, int, int]], dict[str, int]]:
    """
    하단 컬러 영역에서 OD②·OS① 크롭 박스 계산.

    OD②: od_split ~ od_os_boundary (우측 컷, 더 선명한 경우가 많음)
    OS①: od_os_boundary ~ od_os_boundary+os_split (좌측 컷)
    """
    h, w = img_bgr.shape[:2]
    bottom = img_bgr[split_row:, :, :]
    _bh, bw = bottom.shape[:2]

    col_means_b = bottom.mean(axis=(0, 2))
    cs_b, ce_b = int(bw * 0.3), int(bw * 0.7)
    if ce_b <= cs_b:
        od_os_boundary = bw // 2
    else:
        od_os_boundary = cs_b + int(col_means_b[cs_b:ce_b].argmin())

    od_region = bottom[:, :od_os_boundary, :]
    od_split, _od_w = find_sub_boundaries(od_region)

    os_region = bottom[:, od_os_boundary:, :]
    os_split, _os_w = find_sub_boundaries(os_region)

    # OS① 끝이 이미지 폭을 넘지 않도록
    os_end = min(od_os_boundary + os_split, w)
    od_end = min(od_os_boundary, w)
    od_start = min(max(od_split, 0), od_end - 1) if od_end > 0 else 0

    boxes = {
        "color_R": (split_row, od_start, h, od_end),
        "color_L": (split_row, od_os_boundary, h, os_end),
    }
    info = {
        "od_os_boundary": od_os_boundary,
        "od_split": od_split,
        "os_split": os_split,
    }
    return boxes, info
