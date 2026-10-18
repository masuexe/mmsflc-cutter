"""Find a match from the two full-screen animations.

The collection lets the player drag and resize the two gameplay screens.
The VS intro and the win/loss result do not move with them. A match starts
on the VS intro and stops on the last frame of that result, including the
points card drawn on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from mmsflc.segment import Match

TEMPLATES = Path(__file__).parent / "templates"
SCREEN = (160, 90)
DETAIL = (480, 270)

# "2" / "3" after "Star Force" or "流星ROCKMAN" on a 480x270 game view.
# The Chinese title is wider, so its digit sits further right.
DIGIT_BOXES = ((100, 130, 116, 148), (118, 130, 134, 148))

VS_MIN = 0.45
WIN_MIN = 0.55
LOSE_MIN = 0.70
POINTS_MIN = 0.87
DIGIT_MIN = 0.90
DIGIT_MARGIN = 0.05


@dataclass(frozen=True)
class Splash:
    kind: str  # vs, win, lose, points, other
    game: int | None


def game_view(image: Image.Image, size: tuple[int, int]) -> np.ndarray:
    """Crop a 16:10 capture to its 16:9 game view and return grayscale."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width / height < 1.7:
        content_h = int(round(width * 9 / 16))
        top = (height - content_h) // 2
        rgb = rgb.crop((0, top, width, top + content_h))
    rgb = rgb.resize(size, Image.Resampling.BILINEAR)
    array = np.asarray(rgb, dtype=np.float32)
    return array[:, :, 0] * 0.299 + array[:, :, 1] * 0.587 + array[:, :, 2] * 0.114


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum())) + 1e-6
    return float((a * b).sum() / denom)


def _load(name: str) -> np.ndarray:
    image = Image.open(TEMPLATES / name)
    return np.asarray(image.convert("L"), dtype=np.float32)


class SplashReader:
    def __init__(self) -> None:
        self.vs = _load("splash_vs.png")
        self.win = _load("splash_win.png")
        self.lose = _load("splash_lose.png")
        self.points = _load("splash_points.png")
        self.digit2 = _load("digit_2.png")
        self.digit3 = _load("digit_3.png")

    def read(self, image: Image.Image) -> Splash:
        screen = game_view(image, SCREEN)
        scores = {
            "vs": _ncc(self.vs, screen),
            "win": _ncc(self.win, screen),
            "lose": _ncc(self.lose, screen),
            "points": _ncc(self.points, screen),
        }
        limits = {"vs": VS_MIN, "win": WIN_MIN, "lose": LOSE_MIN, "points": POINTS_MIN}
        kind = "other"
        best = 0.0
        for name, score in scores.items():
            if score >= limits[name] and score > best:
                kind = name
                best = score
        game = self._generation(image) if kind == "vs" else None
        return Splash(kind, game)

    def _generation(self, image: Image.Image) -> int:
        detail = game_view(image, DETAIL)
        found = 1
        found_score = 0.0
        for box in DIGIT_BOXES:
            crop = detail[box[1] : box[3], box[0] : box[2]]
            if crop.shape != self.digit3.shape:
                continue
            digit3 = _ncc(self.digit3, crop)
            digit2 = _ncc(self.digit2, crop)
            if digit3 >= DIGIT_MIN and digit3 >= digit2 + DIGIT_MARGIN and digit3 > found_score:
                found, found_score = 3, digit3
            if digit2 >= DIGIT_MIN and digit2 >= digit3 + DIGIT_MARGIN and digit2 > found_score:
                found, found_score = 2, digit2
        return found


def matches(samples: list[tuple[float, str, int | None]], min_length: float = 20) -> list[Match]:
    """samples are (time_seconds, kind, game) sorted by time.

    kind is vs, win, lose, points, or other. A VS while a result is already
    open closes that match and starts the next one.
    """
    found: list[Match] = []
    start: float | None = None
    end: float | None = None
    games: list[int] = []
    saw_result = False

    def close() -> None:
        nonlocal start, end, games, saw_result
        if start is not None and end is not None and saw_result and end - start >= min_length:
            found.append(Match(start, end, _game(games)))
        start = None
        end = None
        games = []
        saw_result = False

    for time, kind, game in samples:
        if kind == "vs":
            if saw_result:
                close()
            if start is None:
                start = time
            if game:
                games.append(game)
        elif kind in ("win", "lose", "points") and start is not None:
            end = time
            saw_result = True
    close()
    return found


def _game(games: list[int]) -> int | None:
    if not games:
        return None
    if 2 in games or 3 in games:
        return 3 if games.count(3) >= games.count(2) else 2
    return 1
