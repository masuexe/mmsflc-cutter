import unittest
from pathlib import Path

from mmsflc.gui import clock, generation, list_dir, match_rows, recording_path
from mmsflc.segment import Match


class GuiTextTest(unittest.TestCase):
    def test_windows_drive_path_maps_into_wsl(self):
        self.assertEqual(
            recording_path(r"D:\video\mmsflc-matches-zh"),
            Path("/mnt/d/video/mmsflc-matches-zh"),
        )

    def test_wsl_path_stays(self):
        self.assertEqual(recording_path("/mnt/d/video/a.mp4"), Path("/mnt/d/video/a.mp4"))

    def test_listing_a_file_returns_its_folder(self):
        listed = list_dir(Path("/mnt/d/BaiduNetdiskDownload/3 (10).mp4"))
        self.assertEqual(listed["path"], "/mnt/d/BaiduNetdiskDownload")
        self.assertTrue(any(entry["name"] == "3 (10).mp4" and entry["video"] for entry in listed["entries"]))

    def test_match_rows(self):
        rows = match_rows([Match(69, 326, 3)])
        self.assertEqual(rows[0]["game"], "3代")
        self.assertEqual(rows[0]["start"], "0:01:09")
        self.assertEqual(rows[0]["length"], "257秒")

    def test_clock_and_generation(self):
        self.assertEqual(clock(69), "0:01:09")
        self.assertEqual(clock(1727), "0:28:47")
        self.assertEqual(generation(3), "3代")
        self.assertEqual(generation(Match(0, 1).game), "未知")


if __name__ == "__main__":
    unittest.main()
