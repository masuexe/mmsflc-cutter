import unittest

from mmsflc.segment import Match, segment


def content(start: float, end: float, game: int, closer: tuple[float, str], flashes: tuple[float, ...] = ()):
    samples = [
        (start - 2, "queue", None),
        (start, "content", game),
        (end, "content", game),
    ]
    samples.extend((t, "flash", None) for t in flashes)
    samples.append((closer[0], closer[1], None))
    return samples


class SegmentTest(unittest.TestCase):
    def test_end_is_last_content_before_lobby(self):
        matches = segment(content(4, 361, 3, (362, "lobby")))
        self.assertEqual(matches, [Match(4, 361, 3)])

    def test_post_result_flash_stays_out(self):
        matches = segment(content(1300, 1777, 3, (1782, "queue"), flashes=(1778, 1779, 1780, 1781)))
        self.assertEqual(matches, [Match(1300, 1777, 3)])

    def test_single_flash_before_lobby_stays_out(self):
        matches = segment(content(2870, 2906, 1, (2908, "lobby"), flashes=(2907,)))
        self.assertEqual(matches, [Match(2870, 2906, 1)])

    def test_practice_and_unarmed_browsing_are_not_matches(self):
        samples = [
            (0, "queue", None),
            (30, "queue", None),
            (40, "lobby", None),
            (50, "content", 3),
            (80, "lobby", None),
        ]
        self.assertEqual(segment(samples), [])

    def test_open_match_at_end_of_tape_is_kept_open(self):
        samples = [
            (0, "queue", None),
            (10, "content", 1),
            (40, "content", 1),
        ]
        self.assertEqual(segment(samples), [])

    def test_shorter_than_20s_is_dropped(self):
        self.assertEqual(segment(content(10, 25, 1, (26, "lobby"))), [])

    def test_queue_after_a_match_can_arm_the_next_one(self):
        samples = content(1300, 1777, 3, (1782, "queue"), flashes=(1778, 1781))
        samples += [
            (1814, "content", 3),
            (2271, "content", 3),
            (2272, "flash", None),
            (2276, "queue", None),
        ]
        self.assertEqual(
            segment(samples),
            [Match(1300, 1777, 3), Match(1814, 2271, 3)],
        )


if __name__ == "__main__":
    unittest.main()
