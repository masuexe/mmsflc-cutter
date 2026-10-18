"""Sample a recording, then return one range per finished match.

The first pass is every 8 seconds. Each coarse range is then re-sampled
every second around its start and end, and the timeline is read again.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image

from mmsflc.classify import Classifier
from mmsflc.sample import frame_time, grab_many
from mmsflc.segment import Match, segment

COARSE_STEP = 8
REFINE_STEP = 1
# A coarse sample can sit up to one step off the real boundary, and the
# VS wipe or the post-result flash can cover another step.
REFINE_PAD = 24


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
    classifier = Classifier()
    coarse_times = _seconds(0, duration, COARSE_STEP, duration)
    log(f"每 {COARSE_STEP} 秒抽一帧（{len(coarse_times)} 帧）")
    coarse = _label(recording, cache, coarse_times, classifier)
    rough = segment(coarse, min_length=0)
    refine_times = sorted(
        {
            t
            for match in rough
            for t in _seconds(match.start - REFINE_PAD, match.start + REFINE_PAD, REFINE_STEP, duration)
        }
        | {
            t
            for match in rough
            for t in _seconds(match.end - REFINE_PAD, match.end + REFINE_PAD, REFINE_STEP, duration)
        }
        - set(coarse_times)
    )
    refined: list[tuple[float, str, int | None]] = []
    if refine_times:
        log(f"边界改成每 {REFINE_STEP} 秒（{len(refine_times)} 帧）")
        refined = _label(recording, cache, refine_times, classifier)
    merged = {time: (time, kind, game) for time, kind, game in coarse}
    for time, kind, game in refined:
        merged[time] = (time, kind, game)
    return segment([merged[time] for time in sorted(merged)])


def _seconds(start: float, end: float, step: int, duration: float) -> list[float]:
    first = max(0, math.floor(start))
    last = min(math.floor(duration) - 1, math.floor(end))
    if last < first:
        return []
    return [float(t) for t in range(first, last + 1, step)]


def _label(
    recording: Path,
    cache: Path,
    times: list[float],
    classifier: Classifier,
) -> list[tuple[float, str, int | None]]:
    samples = []
    for path in grab_many(recording, cache, times):
        with Image.open(path) as image:
            info = classifier.read(image)
        samples.append((frame_time(path), info.kind, info.game))
    return samples
