"""
파일명: services/osam_fundus.py
목적: OSAM-Fundus 방식 — DINOv2 feature matching + SAM point prompts
      참조 이미지(G1020 정답 마스크) → 타겟 이미지 disc/cup 세그멘테이션
근거: OSAM-Fundus (ScienceDirect 2024) — training-free one-shot 세그멘테이션
히스토리:
  2026-06-19 - 최초 작성 (SAM Phase 1 Dice=0.544 미달로 Phase 2 전환)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from scripts.sam_disc_cup_utils import (
    MASK_BG,
    MASK_CUP,
    MASK_DISC,
    combine_disc_cup_masks,
    cup_box_from_disc_box,
    mean_disc_cup_dice,
    resize_mask,
)

logger = logging.getLogger(__name__)

PATCH_SIZE = 14
MAX_DINO_SIDE = 1024
DISC_RADIUS_RATIO = 0.18
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass
class ReferenceSample:
    stem: str
    image_rgb: np.ndarray
    mask: np.ndarray


@dataclass
class ClassPrototypes:
    disc: torch.Tensor
    cup: torch.Tensor
    background: torch.Tensor


def load_dinov2(device: torch.device) -> torch.nn.Module:
    """dinov2_vits14 — torch.hub 우선, 실패 시 timm fallback."""
    try:
        model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", pretrained=True)
        logger.info("DINOv2 loaded via torch.hub (dinov2_vits14)")
    except Exception as exc:
        logger.warning("torch.hub DINOv2 failed (%s) — trying timm", exc)
        import timm

        model = timm.create_model("vit_small_patch14_dinov2.lvd142m", pretrained=True)
        logger.info("DINOv2 loaded via timm")
    model.eval().to(device)
    return model


def _resize_rgb_max_side(image_rgb: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    """긴 변을 max_side 이하로 축소. (image, scale) — scale<1 이면 축소됨."""
    h, w = image_rgb.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image_rgb, 1.0
    scale = max_side / float(longest)
    nh = max(int(round(h * scale)), PATCH_SIZE)
    nw = max(int(round(w * scale)), PATCH_SIZE)
    resized = cv2.resize(image_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    return resized, scale


def _preprocess_rgb(image_rgb: np.ndarray, device: torch.device) -> tuple[torch.Tensor, int, int]:
    """RGB(H,W,3) → DINO 입력 텐서. 높이/너비는 14 배수로 패딩."""
    h, w = image_rgb.shape[:2]
    pad_h = ((h + PATCH_SIZE - 1) // PATCH_SIZE) * PATCH_SIZE
    pad_w = ((w + PATCH_SIZE - 1) // PATCH_SIZE) * PATCH_SIZE
    padded = np.zeros((pad_h, pad_w, 3), dtype=np.uint8)
    padded[:h, :w] = image_rgb
    arr = padded.astype(np.float32) / 255.0
    for c in range(3):
        arr[:, :, c] = (arr[:, :, c] - IMAGENET_MEAN[c]) / IMAGENET_STD[c]
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
    return tensor, h, w


@torch.no_grad()
def extract_patch_features(
    dino: torch.nn.Module,
    image_rgb: np.ndarray,
    device: torch.device,
) -> tuple[torch.Tensor, int, int, int, int]:
    """패치 feature (N,C), grid_h, grid_w, orig_h, orig_w."""
    tensor, orig_h, orig_w = _preprocess_rgb(image_rgb, device)
    _, _, pad_h, pad_w = tensor.shape
    grid_h, grid_w = pad_h // PATCH_SIZE, pad_w // PATCH_SIZE

    if hasattr(dino, "forward_features"):
        out = dino.forward_features(tensor)
    else:
        out = dino(tensor)

    if isinstance(out, dict):
        tokens = out.get("x_norm_patchtokens")
        if tokens is None:
            tokens = out.get("x_prenorm")
        if tokens is None:
            tokens = out.get("x")
    else:
        tokens = out

    if isinstance(tokens, torch.Tensor) and tokens.ndim == 4:
        tokens = tokens[0].permute(1, 2, 0).reshape(-1, tokens.shape[1])
    elif isinstance(tokens, torch.Tensor) and tokens.ndim == 3:
        tokens = tokens[0]
        if tokens.shape[0] == grid_h * grid_w + 1:
            tokens = tokens[1:]

    if tokens.shape[0] != grid_h * grid_w:
        grid_h = int(max(round(tokens.shape[0] ** 0.5), 1))
        grid_w = max(tokens.shape[0] // grid_h, 1)

    return tokens, grid_h, grid_w, orig_h, orig_w


def _mask_to_grid(mask: np.ndarray, grid_h: int, grid_w: int) -> np.ndarray:
    small = cv2.resize(mask, (grid_w, grid_h), interpolation=cv2.INTER_NEAREST)
    return small.reshape(-1)


def _prototype_from_patches(tokens: torch.Tensor, grid_mask: np.ndarray, cls: int) -> torch.Tensor | None:
    idx = np.where(grid_mask == cls)[0]
    if len(idx) < 1:
        return None
    return tokens[idx].mean(dim=0)


def build_prototypes(
    dino: torch.nn.Module,
    references: list[ReferenceSample],
    device: torch.device,
) -> ClassPrototypes | None:
    disc_vecs: list[torch.Tensor] = []
    cup_vecs: list[torch.Tensor] = []
    bg_vecs: list[torch.Tensor] = []
    for ref in references:
        tokens, gh, gw, _, _ = extract_patch_features(dino, ref.image_rgb, device)
        grid = _mask_to_grid(ref.mask, gh, gw)
        d = _prototype_from_patches(tokens, grid, MASK_DISC)
        c = _prototype_from_patches(tokens, grid, MASK_CUP)
        b = _prototype_from_patches(tokens, grid, MASK_BG)
        if d is not None:
            disc_vecs.append(F.normalize(d, dim=0))
        if c is not None:
            cup_vecs.append(F.normalize(c, dim=0))
        if b is not None:
            bg_vecs.append(F.normalize(b, dim=0))
    if not disc_vecs or not cup_vecs:
        return None
    disc = F.normalize(torch.stack(disc_vecs).mean(dim=0), dim=0)
    cup = F.normalize(torch.stack(cup_vecs).mean(dim=0), dim=0)
    background = (
        F.normalize(torch.stack(bg_vecs).mean(dim=0), dim=0)
        if bg_vecs
        else F.normalize(torch.zeros_like(disc), dim=0)
    )
    return ClassPrototypes(disc=disc, cup=cup, background=background)


def _patch_centers(grid_h: int, grid_w: int, orig_h: int, orig_w: int) -> np.ndarray:
    ys = (np.arange(grid_h) + 0.5) * PATCH_SIZE
    xs = (np.arange(grid_w) + 0.5) * PATCH_SIZE
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    coords = np.stack([xx.reshape(-1), yy.reshape(-1)], axis=1)
    coords[:, 0] = np.clip(coords[:, 0], 0, orig_w - 1)
    coords[:, 1] = np.clip(coords[:, 1], 0, orig_h - 1)
    return coords.astype(np.float32)


def _top_point_indices(
    tokens: torch.Tensor,
    proto: torch.Tensor,
    *,
    k: int,
    exclude: set[int] | None = None,
) -> list[int]:
    sim = F.cosine_similarity(tokens, proto.unsqueeze(0), dim=1)
    order = torch.argsort(sim, descending=True).cpu().tolist()
    picked: list[int] = []
    for idx in order:
        if exclude and idx in exclude:
            continue
        picked.append(idx)
        if len(picked) >= k:
            break
    return picked


class OSAMFundus:
    indices: list[int],
    grid_h: int,
    grid_w: int,
    feat_h: int,
    feat_w: int,
    *,
    inv_scale: float = 1.0,
) -> tuple[float, float]:
    """DINO 패치 인덱스 → 원본 이미지 좌표 중심 (x, y)."""
    if not indices:
        return feat_w / 2.0 * inv_scale, feat_h / 2.0 * inv_scale
    centers = _patch_centers(grid_h, grid_w, feat_h, feat_w)
    pts = centers[indices]
    return float(pts[:, 0].mean() * inv_scale), float(pts[:, 1].mean() * inv_scale)


def _disc_box_from_center(cx: float, cy: float, oh: int, ow: int, *, radius_ratio: float = DISC_RADIUS_RATIO) -> np.ndarray:
    r = max(int(min(oh, ow) * radius_ratio), 12)
    x1 = max(int(cx - r), 0)
    y1 = max(int(cy - r), 0)
    x2 = min(int(cx + r), ow - 1)
    y2 = min(int(cy + r), oh - 1)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def _sam_predict_box(predictor, image_rgb: np.ndarray, box: np.ndarray) -> np.ndarray:
    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(
        box=box.astype(np.float32),
        multimask_output=True,
    )
    return masks[int(np.argmax(scores))]


class OSAMFundus:
    """DINOv2 prototype matching + SAM box prompts (고해상도 안저용)."""

    def __init__(
        self,
        sam_predictor,
        *,
        device: str | torch.device = "cuda",
        max_references: int = 80,
    ) -> None:
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.predictor = sam_predictor
        self.max_references = max_references
        self.dino = load_dinov2(self.device)
        self._proto_cache: dict[tuple[str, ...], ClassPrototypes] = {}

    def _prototypes_for(self, references: list[ReferenceSample]) -> ClassPrototypes | None:
        key = tuple(sorted(r.stem for r in references))
        if key not in self._proto_cache:
            protos = build_prototypes(self.dino, references, self.device)
            if protos is None:
                return None
            self._proto_cache[key] = protos
        return self._proto_cache[key]

    def _resolve_g1020_image(self, stem: str, dataset_root: Path) -> Path | None:
        img_dir = dataset_root / "Glaucoma_extra2/G1020/G1020/Images"
        for ext in (".jpg", ".jpeg", ".png", ".bmp"):
            p = img_dir / f"{stem}{ext}"
            if p.is_file():
                return p
        return None

    def load_reference_pool(
        self,
        dataset_root: Path,
        *,
        exclude_stems: set[str] | None = None,
    ) -> list[ReferenceSample]:
        gt_dir = dataset_root / "disc_cup_masks/G1020"
        if not gt_dir.is_dir():
            raise FileNotFoundError(f"G1020 GT masks not found: {gt_dir}")
        exclude = exclude_stems or set()
        candidates: list[tuple[float, ReferenceSample]] = []
        for mask_path in sorted(gt_dir.glob("*_mask.png")):
            stem = mask_path.stem.replace("_mask", "")
            if stem in exclude:
                continue
            img_path = self._resolve_g1020_image(stem, dataset_root)
            if img_path is None:
                continue
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if mask is None or bgr is None:
                continue
            if mask.shape[:2] != bgr.shape[:2]:
                mask = cv2.resize(mask, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST)
            disc_area = float(((mask == MASK_DISC) | (mask == MASK_CUP)).sum())
            total = float(mask.size)
            ratio = disc_area / max(total, 1.0)
            if ratio < 0.005 or ratio > 0.25:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            candidates.append((abs(ratio - 0.04), ReferenceSample(stem=stem, image_rgb=rgb, mask=mask)))
        candidates.sort(key=lambda x: x[0])
        refs = [r for _, r in candidates[: self.max_references]]
        logger.info("OSAM reference pool: %d (exclude=%d)", len(refs), len(exclude))
        return refs

    def segment_rgb(
        self,
        image_rgb: np.ndarray,
        references: list[ReferenceSample],
    ) -> np.ndarray | None:
        protos = self._prototypes_for(references)
        if protos is None:
            return None
        oh, ow = image_rgb.shape[:2]
        dino_rgb, scale = _resize_rgb_max_side(image_rgb, MAX_DINO_SIDE)
        inv_scale = 1.0 / scale
        tokens, gh, gw, feat_h, feat_w = extract_patch_features(self.dino, dino_rgb, self.device)
        disc_idx = _top_point_indices(tokens, protos.disc, k=8)
        cup_idx = _top_point_indices(tokens, protos.cup, k=4, exclude=set(disc_idx))
        disc_cx, disc_cy = _indices_centroid(disc_idx, gh, gw, feat_h, feat_w, inv_scale=inv_scale)
        cup_cx, cup_cy = _indices_centroid(cup_idx, gh, gw, feat_h, feat_w, inv_scale=inv_scale)
        disc_box = _disc_box_from_center(disc_cx, disc_cy, oh, ow)
        cup_box = cup_box_from_disc_box(disc_box)
        if cup_idx:
            cup_r = max(int(min(oh, ow) * DISC_RADIUS_RATIO * 0.55), 8)
            cup_box = np.array(
                [
                    max(cup_cx - cup_r, disc_box[0]),
                    max(cup_cy - cup_r, disc_box[1]),
                    min(cup_cx + cup_r, disc_box[2]),
                    min(cup_cy + cup_r, disc_box[3]),
                ],
                dtype=np.float32,
            )
        disc_mask = _sam_predict_box(self.predictor, image_rgb, disc_box)
        cup_mask = _sam_predict_box(self.predictor, image_rgb, cup_box)
        return combine_disc_cup_masks(disc_mask, cup_mask)

    def segment_bgr(self, bgr: np.ndarray, references: list[ReferenceSample]) -> np.ndarray | None:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return self.segment_rgb(rgb, references)

    def segment_g1020_stem(
        self,
        stem: str,
        dataset_root: Path,
        *,
        exclude_stems: set[str] | None = None,
    ) -> np.ndarray | None:
        img_path = self._resolve_g1020_image(stem, dataset_root)
        if img_path is None:
            return None
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        exclude = set(exclude_stems or set())
        exclude.discard(stem)
        refs = self.load_reference_pool(dataset_root, exclude_stems=exclude | {stem})
        if not refs:
            return None
        return self.segment_bgr(bgr, refs)


def eval_leave_one_out(
    osam: OSAMFundus,
    dataset_root: Path,
    *,
    limit: int = 10,
    image_size: int = 224,
) -> dict[str, float | int]:
    """G1020 self-test — 타겟은 참조 풀에서 제외."""
    gt_dir = dataset_root / "disc_cup_masks/G1020"
    stems = sorted(p.stem.replace("_mask", "") for p in gt_dir.glob("*_mask.png"))
    if limit > 0:
        stems = stems[:limit]
    all_refs = osam.load_reference_pool(dataset_root)
    scores: list[float] = []
    failed = 0
    for stem in stems:
        gt_path = gt_dir / f"{stem}_mask.png"
        gt = cv2.imread(str(gt_path), cv2.IMREAD_GRAYSCALE)
        img_path = osam._resolve_g1020_image(stem, dataset_root)
        if img_path is None or gt is None:
            failed += 1
            continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            failed += 1
            continue
        pool = [r for r in all_refs if r.stem != stem]
        pred_full = osam.segment_bgr(bgr, pool)
        if pred_full is None:
            failed += 1
            continue
        if pred_full.shape[:2] != gt.shape[:2]:
            gt_cmp = cv2.resize(gt, (pred_full.shape[1], pred_full.shape[0]), interpolation=cv2.INTER_NEAREST)
        else:
            gt_cmp = gt
        pred_224 = resize_mask(pred_full, image_size)
        gt_224 = resize_mask(gt_cmp, image_size)
        scores.append(mean_disc_cup_dice(pred_224, gt_224))
    if not scores:
        return {"n": 0, "failed": failed}
    arr = np.array(scores, dtype=np.float64)
    return {
        "n": len(scores),
        "failed": failed,
        "mean_dice": float(arr.mean()),
        "median_dice": float(np.median(arr)),
        "min_dice": float(arr.min()),
        "pass_080": int((arr >= 0.80).sum()),
        "pass_080_pct": 100.0 * (arr >= 0.80).sum() / len(scores),
    }
