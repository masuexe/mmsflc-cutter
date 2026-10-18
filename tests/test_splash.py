import unittest

from mmsflc.segment import Match
from mmsflc.splash import matches


class SplashMatchTest(unittest.TestCase):
    def test_vs_through_the_points_card(self):
        samples = [
            (0, "points", None),
            (4, "vs", 1),
            (5, "vs", 3),
            (200, "other", None),
            (353, "lose", None),
            (360, "points", None),
            (361, "other", None),
        ]
        self.assertEqual(matches(samples), [Match(4, 360, 3)])

    def test_next_vs_closes_the_match(self):
        samples = [
            (1050, "vs", 1),
            (1051, "vs", 2),
            (1227, "win", None),
            (1234, "points", None),
            (1302, "vs", 3),
            (1769, "win", None),
            (1777, "points", None),
        ]
        self.assertEqual(
            matches(samples),
            [Match(1050, 1234, 2), Match(1302, 1777, 3)],
        )

    def test_title_drawn_later_still_labels_the_generation(self):
        samples = [
            (4, "vs", 1),
            (5, "vs", 3),
            (6, "vs", 3),
            (355, "lose", None),
            (360, "points", None),
        ]
        self.assertEqual(matches(samples), [Match(4, 360, 3)])

    def test_no_digit_is_star_force_1(self):
        samples = [
            (636, "vs", 1),
            (637, "vs", 1),
            (890, "lose", None),
            (897, "points", None),
        ]
        self.assertEqual(matches(samples), [Match(636, 897, 1)])

    def test_shorter_than_20s_is_dropped(self):
        samples = [(0, "vs", 3), (10, "win", None)]
        self.assertEqual(matches(samples), [])


if __name__ == "__main__":
    unittest.main()
