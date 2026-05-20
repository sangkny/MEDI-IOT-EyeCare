"""안저 영상(mp4/webm) 업로드 → 프레임 샘플링 → DR(CNN) 집계.

Docker 런타임에는 ``ffmpeg`` 설치 권장. 없으면 ``opencv-python-headless``(requirements-ml) 환경에서만 OpenCV fallback.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from services.retinal_cnn import DrPrediction

log = logging.getLogger("services.fundus_video")

ALLOWED_VIDEO_MIME: frozenset[str] = frozenset({"video/mp4", "video/webm"})
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100MB


def _sniff_video_format(content: bytes, filename: str | None) -> str:
    """``mp4`` | ``webm`` | ``unknown``."""
    fn = (filename or "").lower()
    if fn.endswith(".webm") or (len(content) >= 4 and content[:4] == b"\x1a\x45\xdf\xa3"):
        return "webm"
    if fn.endswith(".mp4") or (len(content) >= 12 and b"ftyp" in content[4:32]):
        return "mp4"
    return "unknown"


def validate_fundus_video_upload(
    content: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    max_bytes: int = MAX_VIDEO_BYTES,
) -> str:
    """영상 바이트 검증 → 포맷 ``mp4`` | ``webm``."""
    if not content:
        raise ValueError("empty video file")
    if len(content) > max_bytes:
        raise ValueError(f"video too large (max {max_bytes // (1024 * 1024)}MB)")

    fmt = _sniff_video_format(content, filename)
    if fmt == "unknown":
        raise ValueError("unsupported video; use .mp4 or .webm")

    ct = (content_type or "").split(";")[0].strip().lower()
    if ct and ct not in ALLOWED_VIDEO_MIME and ct != "application/octet-stream":
        # 일부 브라우저는 video/mp4 미지정 — 파일명·매직으로 이미 통과했으면 허용
        if fmt not in {"mp4", "webm"}:
            raise ValueError(f"unsupported Content-Type: {ct}")

    return fmt


def extract_jpeg_frames_from_video(
    video_bytes: bytes,
    *,
    max_frames: int = 8,
    target_fps: float = 0.25,
    fmt_hint: str = "mp4",
) -> list[bytes]:
    """영상에서 JPEG 프레임 바이트 목록 추출 (최대 ``max_frames``).

    우선 ``ffmpeg``, 실패 시 OpenCV(설치된 경우).
    """
    max_frames = max(1, min(int(max_frames), 32))
    target_fps = max(0.05, float(target_fps))

    frames = _extract_frames_ffmpeg(video_bytes, max_frames, target_fps, fmt_hint)
    if frames:
        log.info("video frames via ffmpeg: n=%s", len(frames))
        return frames

    frames = _extract_frames_opencv(video_bytes, max_frames)
    if frames:
        log.info("video frames via opencv: n=%s", len(frames))
        return frames

    raise RuntimeError(
        "영상 프레임 추출 실패: ffmpeg 미설치이거나 OpenCV 미설치입니다. "
        "Dockerfile에 ffmpeg 추가 또는 requirements-ml(opencv) 환경에서 실행하세요."
    )


def _extract_frames_ffmpeg(
    video_bytes: bytes,
    max_frames: int,
    target_fps: float,
    fmt_hint: str,
) -> list[bytes]:
    if not shutil.which("ffmpeg"):
        return []

    suffix = ".webm" if fmt_hint == "webm" else ".mp4"
    out: list[bytes] = []
    with tempfile.TemporaryDirectory(prefix="medi_vid_") as tmp:
        src = Path(tmp) / f"in{suffix}"
        src.write_bytes(video_bytes)
        out_pat = str(Path(tmp) / "frame_%04d.jpg")
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src),
            "-vf",
            f"fps={target_fps},scale=min(iw\\,1024):-2",
            "-frames:v",
            str(max_frames),
            out_pat,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            log.warning("ffmpeg extract failed: %s", exc)
            return []

        paths = sorted(Path(tmp).glob("frame_*.jpg"))
        for p in paths[:max_frames]:
            try:
                out.append(p.read_bytes())
            except OSError:
                continue
    return out


def _extract_frames_opencv(video_bytes: bytes, max_frames: int) -> list[bytes]:
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError:
        return []

    out: list[bytes] = []
    with tempfile.TemporaryDirectory(prefix="medi_vid_cv_") as tmp:
        src = Path(tmp) / "in.mp4"
        src.write_bytes(video_bytes)
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            return []
        try:
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            if n <= 0:
                n = max_frames * 10
            step = max(1, n // max_frames)
            idx = 0
            taken = 0
            while taken < max_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ok2, buf = cv2.imencode(".jpg", rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if ok2:
                    out.append(buf.tobytes())
                    taken += 1
                idx += step
                if idx >= n:
                    break
        finally:
            cap.release()
    return out


def aggregate_dr_predictions(preds: list[DrPrediction]) -> DrPrediction:
    """프레임별 DR 예측을 집계: **최고(가장 심각) dr_grade** 채택, 동일 등급 중 **최대 confidence**."""
    if not preds:
        raise ValueError("no DR predictions")
    worst_grade = max(p.dr_grade for p in preds)
    same = [p for p in preds if p.dr_grade == worst_grade]
    return max(same, key=lambda p: p.confidence)
