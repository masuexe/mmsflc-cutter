"""Turn a timeline of frame labels into match ranges.

A match starts on the first battle/VS/result frame after the matchmaking
hint, and ends when that hint comes back or the Battle Opponent lobby
returns. Practice battles stay on the hint the whole time, so they never
open a match. Short black or white frames do not open or close one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    start: float
    end: float
    game: int | None = None


def segment(samples: list[tuple[float, str, int | None]]) -> list[Match]:
    """samples are (time_seconds, kind, game) sorted by time.

    kind is queue, lobby, flash, or content. game is 1, 2, or 3 when a
    title was readable, otherwise None.
    """
    matches: list[Match] = []
    armed = False
    start: float | None = None
    games: list[int] = []
    for time, kind, game in samples:
        if kind == "queue":
            if start is not None:
                matches.append(_close(start, time, games))
                start = None
                games = []
            armed = True
        elif kind == "lobby":
            if start is not None:
                matches.append(_close(start, time, games))
                start = None
                games = []
            armed = False
        elif kind == "content" and start is None and armed:
            start = time
            games = [game] if game else []
        elif kind == "content" and start is not None and game:
            games.append(game)
    return [m for m in matches if m.end - m.start >= 20]


def _close(start: float, end: float, games: list[int]) -> Match:
    game = max(set(games), key=games.count) if games else None
    return Match(start, end, game)
