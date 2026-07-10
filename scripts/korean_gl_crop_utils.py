"""한국인 녹내장 합본 이미지 크롭·레이아웃 분석 (modified + origin 공통)."""
from __future__ import annotations

import numpy as np


def detect_boundaries(img: np.ndarray) -> tuple[int, int]:
    """상하(IR/컬러) 및 상단 IR 영역 좌우(OD/OS) 경계."""
    h, w = img.shape[:2]
    row_means = img.mean(axis=(1, 2))
    s, e = int(h * 0.30), int(h * 0.70)
    split_row = s + int(row_means[s:e].argmin())
    col_means = img[:split_row].mean(axis=(0, 2))
    cs, ce = int(w * 0.30), int(w * 0.70)
    split_col = cs + int(col_means[cs:ce].argmin())
    return split_row, split_col


def count_vertical_splits(
    region: np.ndarray,
    threshold_ratio: float = 0.3,
) -> list[int]:
    """
    하단 영역에서 검은 구분선 위치 반환.
    threshold_ratio: 평균 밝기의 몇 % 이하를 구분선으로 볼지.
  """
    _h, w = region.shape[:2]
    if w < 20:
        return []
    col_means = region.mean(axis=(0, 2))
    overall_mean = float(col_means.mean())
    if overall_mean <= 0:
        return []
    threshold = overall_mean * threshold_ratio

    dark_cols = np.where(col_means < threshold)[0]
    if len(dark_cols) == 0:
        return []

    groups: list[list[int]] = []
    group = [int(dark_cols[0])]
    for c in dark_cols[1:]:
        c = int(c)
        if c - group[-1] <= 5:
            group.append(c)
        else:
            groups.append(group)
            group = [c]
    groups.append(group)

    centers = [int(np.mean(g)) for g in groups]
    return [c for c in centers if w * 0.05 < c < w * 0.95]


def region_quality_score(region: np.ndarray) -> float:
    """밝기 표준편차 — 안저 원형 vs 검은 배경 대비."""
    if region.size == 0:
        return 0.0
    gray = region.mean(axis=2)
    return float(gray.std())


def _box_to_list(box: tuple[int, int, int, int]) -> list[int]:
    return [int(box[0]), int(box[1]), int(box[2]), int(box[3])]


def analyze_bottom_layout(
    img_bgr: np.ndarray,
    *,
    split_row: int | None = None,
    split_col: int | None = None,
    threshold_ratio: float = 0.3,
) -> dict:
    """
    하단 컬러 레이아웃 분석 → crop_possible / od_box / os_box.

    layout:
      - 2split: 구분선 1개 (OD | OS)
      - 4split: 구분선 3개 (OD①|OD②|OS①|OS②)
      - unknown: 그 외 → crop_possible=False
    """
    h, w = img_bgr.shape[:2]
    if split_row is None or split_col is None:
        split_row, split_col = detect_boundaries(img_bgr)

    bottom = img_bgr[split_row:, :, :]
    splits = count_vertical_splits(bottom, threshold_ratio=threshold_ratio)

    result: dict = {
        "size": [int(w), int(h)],
        "split_row": int(split_row),
        "split_col": int(split_col),
        "bottom_splits": [int(s) for s in splits],
        "layout": "unknown",
        "crop_possible": False,
        "od_box": None,
        "os_box": None,
    }

    if len(splits) == 1:
        s = splits[0]
        od_box = (split_row, 0, h, s)
        os_box = (split_row, s, h, w)
        result.update({
            "layout": "2split",
            "crop_possible": True,
            "od_box": _box_to_list(od_box),
            "os_box": _box_to_list(os_box),
        })
    elif len(splits) == 3:
        s0, s1, s2 = splits
        od1 = bottom[:, :s0, :]
        od2 = bottom[:, s0:s1, :]
        q1 = region_quality_score(od1)
        q2 = region_quality_score(od2)
        if q2 >= q1:
            od_box = (split_row, s0, h, s1)
            od_pick = "OD2"
        else:
            od_box = (split_row, 0, h, s0)
            od_pick = "OD1"
        os_box = (split_row, s1, h, s2)
        result.update({
            "layout": "4split",
            "crop_possible": True,
            "od_box": _box_to_list(od_box),
            "os_box": _box_to_list(os_box),
            "od_quality": {"OD1": round(q1, 4), "OD2": round(q2, 4)},
            "od_selected": od_pick,
        })
    else:
        result["layout"] = "unknown"
        result["reason"] = f"split_count={len(splits)} (expected 1 or 3)"

    return result


def layout_to_color_boxes(layout: dict) -> dict[str, tuple[int, int, int, int]] | None:
    """analyze_bottom_layout 결과 → color_R / color_L 박스."""
    if not layout.get("crop_possible"):
        return None
    od = layout.get("od_box")
    os_ = layout.get("os_box")
    if not od or not os_:
        return None
    return {
        "color_R": (od[0], od[1], od[2], od[3]),
        "color_L": (os_[0], os_[1], os_[2], os_[3]),
    }
