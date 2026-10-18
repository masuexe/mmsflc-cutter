"""Cut finished matches out of one recording.

    python -m mmsflc
    python -m mmsflc RECORDING OUTPUT_DIR

RECORDING is a Steam session.mpd or a video file. A match runs from the
VS intro through the full-screen win/loss result. The two gameplay screens
can be moved or resized. English and Chinese both work.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mmsflc.cut import export_matches
from mmsflc.find import cache_dir, find_matches
from mmsflc.segment import Match


def main(argv: list[str]) -> int:
    if not argv:
        from mmsflc.gui import run

        run()
        return 0
    if len(argv) != 2:
        print("用法: python -m mmsflc 录像 输出目录", file=sys.stderr)
        return 2
    recording = Path(argv[0])
    dest = Path(argv[1])
    if not recording.is_file():
        print(f"找不到录像: {recording}", file=sys.stderr)
        return 1
    cache = cache_dir(recording)
    matches = find_matches(recording, cache)
    if not matches:
        print("没有对局")
        return 0
    for index, match in enumerate(matches, start=1):
        print(_line(index, match))
    for path in export_matches(recording, dest, matches):
        print(path)
    return 0


def _line(index: int, match: Match) -> str:
    game = f"sf{match.game}" if match.game else "sf?"
    length = match.end - match.start
    return f"{index:02d}  {game}  {_clock(match.start)} -> {_clock(match.end)}  ({length:.0f}s)"


def _clock(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600:d}:{total % 3600 // 60:02d}:{total % 60:02d}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
