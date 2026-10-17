"""Label one 640x400 collection frame.

Screens are classified from two fixed overlays on a 2560x1600 capture:

- queue: the matchmaking hint "Hold: Cancel Match" (practice, or the
  "opponent found" dialog). That is not a match.
- lobby: the blue "Battle Opponent" header. That is between matches.
- flash: a black or white transition frame.
- content: everything else, including the VS intro, the battle itself,
  and the battle-points result.

A real match also shows "Hold: Vote to Decline Match" in the same corner.
That string only partly matches the queue template, so the queue threshold
stays high enough to leave those frames in the match.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

TEMPLATES = Path(__file__).parent / "templates"
WIDTH = 640
HEIGHT = 400

CANCEL_BOX = (500, 348, 632, 372)
LOBBY_BOX = (8, 18, 210, 40)
# "Star Force" / "Star Force 3" on the left of the VS card.
TITLE_BOX = (22, 204, 178, 226)
# "Star Force" under the rank bar, and the generation digit just after it.
RESULT_PREFIX_BOX = (318, 260, 392, 278)
RESULT_DIGIT_BOX = (378, 258, 408, 278)

CANCEL_MIN = 0.85
LOBBY_MIN = 0.80
TITLE_MIN = 0.72


@dataclass(frozen=True)
class FrameInfo:
    kind: str  # queue, lobby, flash, content
    cancel: float
    lobby: float
    game: int | None


def _gray(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    return rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum())) + 1e-6
    return float((a * b).sum() / denom)


def _load_template(name: str) -> np.ndarray:
    return _gray(Image.open(TEMPLATES / name))


class Classifier:
    def __init__(self) -> None:
        self.cancel = _load_template("cancel_en.png")
        self.lobby = _load_template("lobby_en.png")
        self.title_sf3 = _load_template("title_sf3.png")
        self.title_sf1 = _load_template("title_sf1.png")
        self.result_prefix = _load_template("result_prefix.png")
        self.result_digit2 = _load_template("result_digit2.png")
        self.result_digit3 = _load_template("result_digit3.png")

    def read(self, image: Image.Image) -> FrameInfo:
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
        gray = _gray(image)
        cancel = _ncc(gray[CANCEL_BOX[1] : CANCEL_BOX[3], CANCEL_BOX[0] : CANCEL_BOX[2]], self.cancel)
        lobby = _ncc(gray[LOBBY_BOX[1] : LOBBY_BOX[3], LOBBY_BOX[0] : LOBBY_BOX[2]], self.lobby)
        white = float((gray > 220).mean())
        black = float((gray < 12).mean())
        if cancel >= CANCEL_MIN:
            kind = "queue"
        elif lobby >= LOBBY_MIN:
            kind = "lobby"
        elif white > 0.25 or black > 0.70:
            kind = "flash"
        else:
            kind = "content"
        return FrameInfo(kind=kind, cancel=cancel, lobby=lobby, game=self._game(gray))

    def _crop(self, gray: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
        return gray[box[1] : box[3], box[0] : box[2]]

    def _game(self, gray: np.ndarray) -> int | None:
        title = self._crop(gray, TITLE_BOX)
        sf3 = _ncc(title, self.title_sf3)
        sf1 = _ncc(title, self.title_sf1)
        if sf3 >= TITLE_MIN and sf3 >= sf1 + 0.08:
            return 3
        if sf1 >= TITLE_MIN and sf1 >= sf3 + 0.08:
            return 1
        prefix = _ncc(self._crop(gray, RESULT_PREFIX_BOX), self.result_prefix)
        if prefix < 0.90:
            return None
        digit = self._crop(gray, RESULT_DIGIT_BOX)
        digit2 = _ncc(digit, self.result_digit2)
        digit3 = _ncc(digit, self.result_digit3)
        if digit3 >= 0.97 and digit3 > digit2:
            return 3
        if digit2 >= 0.97 and digit2 > digit3:
            return 2
        return 1
