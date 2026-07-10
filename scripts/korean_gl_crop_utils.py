"""한국인 녹내장 합본 이미지 크롭·레이아웃 분석 (gradient 기반, modified + origin 공통)."""
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


def detect_boundaries_by_gradient(
    bottom: np.ndarray,
    ratio_threshold: float = 2.5,
    min_distance: int = 100,
) -> list[int]:
    """
    하단 컬러 영역에서 이미지 경계 위치 감지.
    가로 픽셀 간 차이값(|diff|)을 세로로 누적 → 국소 최대값(피크)만 선택.
    """
    _bh, bw = bottom.shape[:2]
    if bw < 20:
        return []

    diff = np.abs(np.diff(bottom.astype(np.float64), axis=1))
    grad_sum = diff.mean(axis=2).sum(axis=0)

    margin = int(bw * 0.10)
    inner = grad_sum[margin : max(margin + 1, bw - margin)]
    mean_val = float(inner.mean()) if inner.size else float(grad_sum.mean())
    if mean_val <= 0:
        return []
    threshold = mean_val * ratio_threshold

    peaks: list[tuple[float, int]] = []
    for i in range(1, len(inner) - 1):
        val = float(inner[i])
        if val > threshold and val >= inner[i - 1] and val >= inner[i + 1]:
            peaks.append((val, i + margin))

    peaks.sort(key=lambda x: -x[0])
    selected: list[int] = []
    for _val, idx in peaks:
        if all(abs(idx - s) >= min_distance for s in selected):
            selected.append(idx)

    selected.sort()

    # 피크 과다 시 상위 3개만 (4분할 최대 경계 수)
    if len(selected) > 3:
        scored = sorted(((float(grad_sum[i]), i) for i in selected), reverse=True)
        selected = sorted(i for _, i in scored[:3])

    return selected


def _gradient_sum(bottom: np.ndarray) -> np.ndarray:
    diff = np.abs(np.diff(bottom.astype(np.float64), axis=1))
    return diff.mean(axis=2).sum(axis=0)


def _score_boundaries(bottom: np.ndarray, boundaries: list[int]) -> list[tuple[float, int]]:
    gs = _gradient_sum(bottom)
    return sorted(
        ((float(gs[b]), b) for b in boundaries if 0 <= b < len(gs)),
        reverse=True,
    )


def _merge_close_boundaries(
    bottom: np.ndarray,
    boundaries: list[int],
    merge_dist: int = 120,
) -> list[int]:
    """인접 피크 병합 — 더 강한 피크만 유지."""
    if len(boundaries) <= 1:
        return boundaries
    gs = _gradient_sum(bottom)
    scored = sorted(((float(gs[b]), b) for b in boundaries), key=lambda x: x[1])
    merged: list[tuple[float, int]] = [scored[0]]
    for val, b in scored[1:]:
        prev_val, prev_b = merged[-1]
        if b - prev_b <= merge_dist:
            if val >= prev_val * 0.65 and prev_val >= val * 0.65:
                merged.append((val, b))
            elif val > prev_val:
                merged[-1] = (val, b)
        else:
            merged.append((val, b))
    return [b for _, b in merged]


def _refine_boundaries_for_layout(
    bottom: np.ndarray,
    boundaries: list[int],
) -> tuple[list[int], str | None]:
    """피크 강도·간격·중심 위치로 2/3/4분할 후보를 정제."""
    boundaries = _merge_close_boundaries(bottom, boundaries)
    if not boundaries:
        return [], None

    bw = bottom.shape[1]
    gs = _gradient_sum(bottom)
    mean_val = max(float(gs.mean()), 1e-6)

    if len(boundaries) == 1:
        return boundaries, "2split"

    scored = _score_boundaries(bottom, boundaries)
    top_val, top_idx = scored[0]
    second_val = scored[1][0] if len(scored) > 1 else 0.0

    if top_val >= mean_val * 6.0:
        return [top_idx], "2split"
    if second_val > 0 and top_val >= second_val * 2.0:
        return [top_idx], "2split"

    if len(boundaries) == 2:
        scored = _score_boundaries(bottom, boundaries)
        top_val, top_idx = scored[0]
        second_val = scored[1][0]
        if top_val >= mean_val * 6.0 or top_val >= second_val * 2.0:
            return [top_idx], "2split"
        return sorted(b for _, b in scored), "3split"

    sorted_x = sorted(boundaries)
    if len(sorted_x) >= 3:
        gaps = [sorted_x[i + 1] - sorted_x[i] for i in range(len(sorted_x) - 1)]
        min_gap = min(gaps)
        max_ratio = max(float(gs[b]) for b in sorted_x) / mean_val
        if min_gap < 120 and max_ratio < 6.0:
            return sorted_x[:3], "4split"
        center = bw * 0.5
        candidate = min(sorted_x, key=lambda b: abs(b - center))
        if float(gs[candidate]) >= mean_val * 3.5:
            return [candidate], "2split"

    if len(scored) >= 3:
        vals = [v for v, _ in scored[:3]]
        lo = max(min(vals), 1e-6)
        if max(vals) / lo < 2.5:
            return sorted(b for _, b in scored[:3]), "4split"
        return sorted(b for _, b in scored[:3]), "4split"

    return sorted(b for _, b in scored), "3split"


def analyze_bottom_layout_v2(
    img: np.ndarray,
    split_row: int,
    *,
    ratio_threshold: float = 2.5,
    min_distance: int = 100,
) -> dict:
    """
    gradient 기반 레이아웃 분석.
    반환: layout, crop_possible, boundaries, od_box, os_box (튜플)
    """
    h, w = img.shape[:2]
    bottom = img[split_row:, :, :]
    _bh, bw = bottom.shape[:2]

    boundaries_raw = detect_boundaries_by_gradient(
        bottom,
        ratio_threshold=ratio_threshold,
        min_distance=min_distance,
    )
    boundaries, forced = _refine_boundaries_for_layout(bottom, boundaries_raw)
    n = len(boundaries)

    if forced == "2split" or n == 1:
        b = boundaries[0]
        return {
            "layout": "2split",
            "crop_possible": True,
            "boundaries": boundaries,
            "od_box": (split_row, 0, h, b),
            "os_box": (split_row, b, h, bw),
        }

    if forced == "4split" or n == 3:
        b0, b1, b2 = boundaries
        return {
            "layout": "4split",
            "crop_possible": True,
            "boundaries": boundaries,
            "od_box": (split_row, b0, h, b1),
            "os_box": (split_row, b1, h, b2),
        }

    if forced == "3split" or n == 2:
        b0, b1 = boundaries
        return {
            "layout": "3split",
            "crop_possible": True,
            "boundaries": boundaries,
            "od_box": (split_row, 0, h, b0),
            "os_box": (split_row, b1, h, bw),
        }

    return {
        "layout": "unknown",
        "crop_possible": False,
        "boundaries": boundaries,
        "reason": f"boundary_count={n} (expected 1, 2, or 3)",
    }


def _box_to_list(box: tuple[int, int, int, int]) -> list[int]:
    return [int(box[0]), int(box[1]), int(box[2]), int(box[3])]


def analyze_bottom_layout(
    img_bgr: np.ndarray,
    *,
    split_row: int | None = None,
    split_col: int | None = None,
    ratio_threshold: float = 2.5,
    min_distance: int = 100,
    **_kwargs: object,
) -> dict:
    """전처리·분석 공통 API — gradient v2 + 메타데이터."""
    h, w = img_bgr.shape[:2]
    if split_row is None or split_col is None:
        split_row, split_col = detect_boundaries(img_bgr)

    raw = analyze_bottom_layout_v2(
        img_bgr,
        split_row,
        ratio_threshold=ratio_threshold,
        min_distance=min_distance,
    )

    result: dict = {
        "size": [int(w), int(h)],
        "split_row": int(split_row),
        "split_col": int(split_col),
        "bottom_splits": [int(b) for b in raw.get("boundaries", [])],
        "layout": raw.get("layout", "unknown"),
        "crop_possible": bool(raw.get("crop_possible")),
        "od_box": None,
        "os_box": None,
        "detector": "gradient_v2",
        "ratio_threshold": ratio_threshold,
    }

    if raw.get("reason"):
        result["reason"] = raw["reason"]

    if raw.get("od_box"):
        result["od_box"] = _box_to_list(raw["od_box"])
    if raw.get("os_box"):
        result["os_box"] = _box_to_list(raw["os_box"])

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
