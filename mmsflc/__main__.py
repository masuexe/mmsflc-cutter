"""Scan sampled frames and print match ranges.

    python -m mmsflc tmp/scan/may15
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from mmsflc.classify import Classifier
from mmsflc.segment import segment


def frame_time(path: Path) -> float:
    return float(path.stem.replace("_", "."))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m mmsflc FRAME_DIR", file=sys.stderr)
        return 2
    frame_dir = Path(argv[0])
    frames = sorted(frame_dir.glob("*.jpg"), key=frame_time)
    if not frames:
        print(f"no jpg frames in {frame_dir}", file=sys.stderr)
        return 1
    classifier = Classifier()
    samples = []
    for path in frames:
        info = classifier.read(Image.open(path))
        samples.append((frame_time(path), info.kind, info.game))
    matches = segment(samples)
    if not matches:
        print("no matches")
        return 0
    for index, match in enumerate(matches, start=1):
        game = f"sf{match.game}" if match.game else "sf?"
        print(
            f"{index:02d}  {game}  {_clock(match.start)} -> {_clock(match.end)}  "
            f"({match.end - match.start:.0f}s)"
        )
    return 0


def _clock(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600:d}:{total % 3600 // 60:02d}:{total % 60:02d}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
