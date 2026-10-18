"""Turn a timeline of frame labels into match ranges.

A match starts on the first battle/VS/result frame after the matchmaking
hint, and stops on the last of those frames before the hint comes back or
the Battle Opponent lobby returns. The closing lobby frame, and any black
or white wipe after the result, stay out: that wipe can already be the
practice screen. Practice battles stay on the hint the whole time, so they
never open a match.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    start: float
    end: float
    game: int | None = None


def segment(
    samples: list[tuple[float, str, int | None]],
    min_length: float = 20,
) -> list[Match]:
    """samples are (time_seconds, kind, game) sorted by time.

    kind is queue, lobby, flash, or content. game is 1, 2, or 3 when a
    title was readable, otherwise None. A match still running at the last
    sample is left open: it has not returned to the lobby or the queue.
    """
    matches: list[Match] = []
    armed = False
    start: float | None = None
    end: float | None = None
    games: list[int] = []
    for time, kind, game in samples:
        if kind in ("queue", "lobby"):
            if start is not None and end is not None:
                matches.append(_close(start, end, games))
            start = None
            end = None
            games = []
            armed = kind == "queue"
        elif kind == "content" and start is None and armed:
            start = time
            end = time
            games = [game] if game else []
        elif kind == "content" and start is not None:
            end = time
            if game:
                games.append(game)
    return [m for m in matches if m.end - m.start >= min_length]


def _close(start: float, end: float, games: list[int]) -> Match:
    game = max(set(games), key=games.count) if games else None
    return Match(start, end, game)
