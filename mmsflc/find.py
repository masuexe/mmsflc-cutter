"""Sample a recording once a second and return one range per finished match.

The VS intro and the win/loss result last only a few seconds, so a coarser
grid can skip them. One second is enough to land inside either animation.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image

from mmsflc.sample import frame_time, grab_many
from mmsflc.segment import Match
from mmsflc.splash import SplashReader, matches

STEP = 1


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-allowed_extensions",
            "ALL",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    text = result.stdout.strip()
    if not text or text == "N/A":
        raise RuntimeError(f"no duration for {path}")
    return float(text)


def find_matches(
    recording: Path,
    cache: Path,
    log=_log,
) -> list[Match]:
    duration = probe_duration(recording)
    times = _seconds(0, duration, STEP, duration)
    log(f"每 {STEP} 秒抽一帧（{len(times)} 帧）")
    reader = SplashReader()
    samples = []
    for path in grab_many(recording, cache, times):
        with Image.open(path) as image:
            splash = reader.read(image)
        samples.append((frame_time(path), splash.kind, splash.game))
    samples.sort()
    return matches(samples)


def _seconds(start: float, end: float, step: int, duration: float) -> list[float]:
    first = max(0, math.floor(start))
    last = min(math.floor(duration) - 1, math.floor(end))
    if last < first:
        return []
    return [float(t) for t in range(first, last + 1, step)]
