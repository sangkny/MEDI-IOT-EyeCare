#!/usr/bin/env python3
"""등급별 특징이 구분되는 합성 안저 이미지 생성 (DR 학습·검증용).

사용:
  python3 scripts/generate_synthetic_fundus.py --output data/synthetic --per-class 200

레이아웃:
  {output}/images/{train|val|test}/{grade}/*.jpg
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _base_retina(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    """원형 망막 + 시신경 · 혈관 골격."""
    import cv2

    y, x = np.ogrid[:h, :w]
    cy, cx = h // 2, w // 2
    r = min(h, w) // 2 - 8
    mask = ((x - cx) ** 2 + (y - cy) ** 2) <= r * r
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[mask] = (rng.integers(90, 130), rng.integers(25, 55), rng.integers(25, 55))

    # 시신경
    cv2.circle(img, (cx - r // 6, cy), r // 7, (40, 40, 40), -1)
    cv2.circle(img, (cx - r // 6, cy), r // 12, (20, 20, 20), -1)

    # 기본 혈관
    for _ in range(6):
        ang = rng.uniform(0, 2 * np.pi)
        x2 = int(cx + np.cos(ang) * r * 0.85)
        y2 = int(cy + np.sin(ang) * r * 0.85)
        cv2.line(img, (cx, cy), (x2, y2), (30, 10, 10), rng.integers(1, 3))
    noise = rng.integers(-12, 12, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img, mask


def _grade_features(img: np.ndarray, mask: np.ndarray, grade: int, rng: np.random.Generator) -> np.ndarray:
    import cv2

    h, w = img.shape[:2]
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img

    def scatter_dots(n: int, color: tuple[int, int, int], radius_rng: tuple[int, int]) -> None:
        for _ in range(n):
            i = rng.integers(0, len(xs))
            x, y = int(xs[i]), int(ys[i])
            cv2.circle(img, (x, y), rng.integers(*radius_rng), color, -1)

    if grade >= 1:
        scatter_dots(rng.integers(25, 55), (180, 30, 30), (1, 3))
    if grade >= 2:
        scatter_dots(rng.integers(15, 35), (220, 20, 20), (2, 5))
    if grade >= 3:
        for _ in range(rng.integers(8, 16)):
            i = rng.integers(0, len(xs))
            x, y = int(xs[i]), int(ys[i])
            cv2.ellipse(
                img,
                (x, y),
                (rng.integers(8, 18), rng.integers(6, 14)),
                rng.integers(0, 180),
                0,
                360,
                (200, 200, 200),
                -1,
            )
        for _ in range(3):
            ang = rng.uniform(0, 2 * np.pi)
            x2 = int(w // 2 + np.cos(ang) * (min(h, w) // 2 - 20))
            y2 = int(h // 2 + np.sin(ang) * (min(h, w) // 2 - 20))
            cv2.line(img, (w // 2, h // 2), (x2, y2), (50, 15, 15), rng.integers(4, 7))
    if grade >= 4:
        scatter_dots(rng.integers(40, 70), (255, 10, 10), (3, 8))
        for _ in range(rng.integers(5, 12)):
            i = rng.integers(0, len(xs))
            x, y = int(xs[i]), int(ys[i])
            cv2.line(
                img,
                (x, y),
                (x + rng.integers(-40, 40), y + rng.integers(-40, 40)),
                (255, 40, 40),
                rng.integers(2, 4),
            )
    return img


def render_fundus(grade: int, size: int = 512, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img, mask = _base_retina(size, size, rng)
    return _grade_features(img, mask, grade, rng)


def write_split(
    out_root: Path,
    split: str,
    per_class: int,
    *,
    size: int,
    base_seed: int,
) -> int:
    import cv2

    n = 0
    for grade in range(5):
        d = out_root / "images" / split / str(grade)
        d.mkdir(parents=True, exist_ok=True)
        for i in range(per_class):
            seed = base_seed + grade * 10_000 + i
            arr = render_fundus(grade, size=size, seed=seed)
            path = d / f"g{grade}_{i:04d}.jpg"
            cv2.imwrite(str(path), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
            n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="합성 DR 안저 데이터셋 생성")
    p.add_argument("--output", type=Path, default=ROOT / "data" / "synthetic")
    p.add_argument("--per-class", type=int, default=200, help="등급당 장수 (train/val/test 각각 아님 — 총량 기준)")
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    out: Path = args.output
    if not out.is_absolute():
        out = ROOT / out

    total = args.per_class * 5
    train_n = int(total * 0.8)
    val_n = int(total * 0.1)
    test_n = total - train_n - val_n
    per_train = train_n // 5
    per_val = max(val_n // 5, 1)
    per_test = max(test_n // 5, 1)

    counts = {}
    counts["train"] = write_split(out, "train", per_train, size=args.size, base_seed=args.seed)
    counts["val"] = write_split(out, "val", per_val, size=args.size, base_seed=args.seed + 1)
    counts["test"] = write_split(out, "test", per_test, size=args.size, base_seed=args.seed + 2)

    print(f"OK output={out}")
    for k, v in counts.items():
        print(f"  {k}: {v} images")
    print(f"  total: {sum(counts.values())} (target ~{total})")


if __name__ == "__main__":
    main()
