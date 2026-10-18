"""Write one match out of a Steam recording without re-encoding."""

from __future__ import annotations

import subprocess
from pathlib import Path

from mmsflc.segment import Match


def export_matches(recording: Path, dest: Path, matches: list[Match]) -> list[Path]:
    return [
        cut_match(recording, match, dest, index)
        for index, match in enumerate(matches, start=1)
    ]


def cut_match(mpd: Path, match: Match, dest: Path, index: int) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    game = match.game if match.game else 0
    out = dest / f"{index:02d}_sf{game}.mp4"
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if Path(mpd).suffix == ".mpd":
        command += ["-allowed_extensions", "ALL"]
    command += [
        "-ss",
        f"{match.start:.3f}",
        "-to",
        f"{match.end:.3f}",
        "-i",
        str(mpd),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(out),
    ]
    subprocess.run(command, check=True)
    return out
