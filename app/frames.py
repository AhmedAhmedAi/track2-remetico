"""Video download + motion-adaptive frame extraction.

Pipeline per clip:
  1. Download the video (streaming, retries).
  2. Extract tiny 1-fps thumbnails for motion analysis.
  3. Score motion between consecutive seconds (numpy frame differencing).
  4. Spend the frame budget adaptively: busy seconds get more frames,
     first and last frames are always kept.
  5. Re-extract the chosen timestamps at high quality (768px) for Gemma.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import tempfile

import httpx
import numpy as np
from PIL import Image

from . import config

log = logging.getLogger(__name__)

_dl_sem: asyncio.Semaphore | None = None
_ff_sem: asyncio.Semaphore | None = None


def _sems() -> tuple[asyncio.Semaphore, asyncio.Semaphore]:
    global _dl_sem, _ff_sem
    if _dl_sem is None:
        _dl_sem = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)
        _ff_sem = asyncio.Semaphore(config.MAX_CONCURRENT_FFMPEG)
    return _dl_sem, _ff_sem


async def download_video(url: str, workdir: str) -> str:
    """Download video to workdir. Supports local paths for testing."""
    if not url.startswith(("http://", "https://")):
        path = url.removeprefix("file://")
        if os.path.exists(path):
            return path
        raise FileNotFoundError(f"local video not found: {path}")

    dest = os.path.join(workdir, "video.mp4")
    dl_sem, _ = _sems()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            async with dl_sem:
                timeout = httpx.Timeout(config.DOWNLOAD_TIMEOUT, connect=15.0)
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                         "AppleWebKit/537.36 video-caption-agent/1.0"}
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                             headers=headers) as client:
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with open(dest, "wb") as f:
                            async for chunk in resp.aiter_bytes(1 << 20):
                                f.write(chunk)
            if os.path.getsize(dest) > 0:
                return dest
            raise IOError("empty download")
        except Exception as e:  # noqa: BLE001 — must survive anything
            last_err = e
            log.warning("download attempt %d failed for %s: %s", attempt + 1, url, e)
            await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed after retries: {last_err}")


async def _run(cmd: list[str], timeout: float = 120.0) -> tuple[int, str, str]:
    _, ff_sem = _sems()
    async with ff_sem:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise
        return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def probe_duration(video: str) -> float:
    code, out, err = await _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video], timeout=30.0
    )
    if code != 0:
        raise RuntimeError(f"ffprobe failed: {err[:300]}")
    return float(out.strip())


async def _extract_thumbs(video: str, workdir: str) -> list[str]:
    """1-fps tiny thumbnails for motion analysis."""
    thumb_dir = os.path.join(workdir, "thumbs")
    os.makedirs(thumb_dir, exist_ok=True)
    pattern = os.path.join(thumb_dir, "t_%04d.jpg")
    code, _, err = await _run(
        ["ffmpeg", "-v", "error", "-i", video,
         "-vf", f"fps=1,scale={config.THUMB_WIDTH}:-1,format=yuvj420p",
         "-q:v", "6", pattern], timeout=180.0
    )
    if code != 0:
        raise RuntimeError(f"thumb extraction failed: {err[:300]}")
    return sorted(
        os.path.join(thumb_dir, f) for f in os.listdir(thumb_dir) if f.endswith(".jpg")
    )


def _motion_scores(thumbs: list[str]) -> np.ndarray:
    """Mean absolute grayscale difference between consecutive 1-fps thumbnails.

    Result: score[i] = how much happens during second i -> i+1.
    """
    if len(thumbs) < 2:
        return np.array([1.0])
    prev = None
    scores = []
    for path in thumbs:
        img = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
        if prev is not None:
            if img.shape != prev.shape:
                img = np.resize(img, prev.shape)
            scores.append(float(np.abs(img - prev).mean()))
        prev = img
    return np.asarray(scores, dtype=np.float64)


def _adaptive_timestamps(scores: np.ndarray, duration: float, budget: int) -> list[float]:
    """Spend `budget` frames where motion mass is, keeping full-timeline coverage.

    Uses inverse-CDF sampling over (motion + uniform floor): calm videos degrade
    to even spacing, busy segments attract extra frames. First/last always kept.
    """
    first, last = 0.1, max(duration - 0.5, 0.1)
    if budget <= 2 or len(scores) == 0:
        return [first, last]

    # Uniform floor keeps coverage; motion term concentrates the rest.
    weights = scores + max(scores.mean(), 1e-6) * 0.6
    cdf = np.cumsum(weights)
    cdf = cdf / cdf[-1]

    inner = budget - 2
    targets = (np.arange(inner) + 0.5) / inner
    # Each second i spans [i, i+1); pick its middle.
    picks = [float(np.searchsorted(cdf, t) + 0.5) for t in targets]

    stamps = sorted({round(min(max(p, 0.1), duration - 0.2), 2) for p in [first, *picks, last]})
    # Enforce a minimum gap so near-duplicates don't waste budget.
    min_gap = max(0.5, duration / (budget * 3))
    result: list[float] = []
    for s in stamps:
        if not result or s - result[-1] >= min_gap:
            result.append(s)
    return result


async def _extract_at(video: str, ts: float, dest: str) -> bool:
    code, _, _ = await _run(
        ["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", video,
         "-frames:v", "1", "-vf", f"scale={config.FRAME_WIDTH}:-1,format=yuvj420p",
         "-q:v", str(config.JPEG_QUALITY), dest], timeout=45.0
    )
    return code == 0 and os.path.exists(dest) and os.path.getsize(dest) > 0


async def extract_frames(url: str, task_id: str) -> dict:
    """Full pipeline. Returns dict with frames (base64 jpegs), timestamps, duration."""
    workdir = tempfile.mkdtemp(prefix=f"clip_{task_id}_")
    try:
        video = await download_video(url, workdir)
        duration = await probe_duration(video)

        thumbs = await _extract_thumbs(video, workdir)
        scores = _motion_scores(thumbs)

        budget = int(np.clip(round(duration / config.SECONDS_PER_FRAME),
                             config.MIN_FRAMES, config.MAX_FRAMES))
        stamps = _adaptive_timestamps(scores, duration, budget)

        frames: list[bytes] = []
        kept_ts: list[float] = []
        results = await asyncio.gather(
            *[_extract_at(video, ts, os.path.join(workdir, f"f_{i:03d}.jpg"))
              for i, ts in enumerate(stamps)],
            return_exceptions=True,
        )
        for i, (ts, ok) in enumerate(zip(stamps, results)):
            path = os.path.join(workdir, f"f_{i:03d}.jpg")
            if ok is True:
                with open(path, "rb") as f:
                    frames.append(f.read())
                kept_ts.append(ts)

        if not frames:
            raise RuntimeError("no frames extracted")

        log.info("task %s: %.1fs video, motion-adaptive picked %d frames at %s",
                 task_id, duration, len(frames),
                 [f"{t:.1f}" for t in kept_ts])
        return {
            "frames_b64": [base64.b64encode(b).decode() for b in frames],
            "timestamps": kept_ts,
            "duration": duration,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
