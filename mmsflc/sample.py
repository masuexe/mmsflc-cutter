"""Grab evenly spaced frames from a Steam Game Recording session."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def frame_time(path: Path) -> float:
    return float(path.stem.replace("_", "."))


def grab(mpd: Path, dest: Path, t: float, width: int = 640) -> Path:
    stamp = f"{t:07.1f}".replace(".", "_")
    out = dest / f"{stamp}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 0:
        return out
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-allowed_extensions",
        "ALL",
        "-ss",
        f"{t:.3f}",
        "-i",
        str(mpd),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:-1",
        str(out),
    ]
    last_error: subprocess.CalledProcessError | None = None
    for _ in range(2):
        try:
            subprocess.run(command, check=True, stderr=subprocess.DEVNULL)
            return out
        except subprocess.CalledProcessError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def grab_many(
    mpd: Path,
    dest: Path,
    times: list[float],
    workers: int = 6,
    width: int = 640,
) -> list[Path]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda t: grab(mpd, dest, t, width), times))
