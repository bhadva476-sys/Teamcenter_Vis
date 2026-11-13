import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import teamcenter_visualization_watcher as watcher


class TeamcenterVisualizationWatcherTests(unittest.TestCase):
    def test_insert_watcher_ignores_automation_dialog_while_busy(self):
        with patch.object(watcher, "BUSY_FLAG") as busy_flag:
            busy_flag.exists.return_value = True

            self.assertFalse(watcher.should_handle_insert_dialog("Insert File"))

    def test_insert_watcher_handles_user_insert_when_idle(self):
        with patch.object(watcher, "BUSY_FLAG") as busy_flag:
            busy_flag.exists.return_value = False

            self.assertTrue(watcher.should_handle_insert_dialog("Insert File"))
            self.assertFalse(watcher.should_handle_insert_dialog("Open"))

    def test_insert_dialog_closes_before_launching_and_focusing_viewer(self):
        events = []
        viewer_window = Mock()
        viewer_window.handle = 123

        def find_window():
            events.append(("find_viewer",))
            return viewer_window

        with (
            patch.object(
                watcher,
                "close_popup",
                side_effect=lambda handle: events.append(("close", handle)),
            ),
            patch.object(
                watcher,
                "launch_or_focus",
                side_effect=lambda: events.append(("launch",)),
            ),
            patch.object(
                watcher,
                "find_viewer_window",
                side_effect=find_window,
            ),
            patch.object(
                watcher,
                "force_foreground",
                side_effect=lambda handle: events.append(("focus", handle)),
            ),
        ):
            watcher.handle_insert_dialog(456)

        self.assertEqual(
            events,
            [
                ("close", 456),
                ("launch",),
                ("find_viewer",),
                ("focus", 123),
            ],
        )

    def test_viewer_executable_is_resolved_relative_to_backend(self):
        expected = (
            Path(watcher.__file__).resolve().parent
            / "dist"
            / "JTViewer"
            / "JTViewer.exe"
        )

        self.assertEqual(watcher.APP_EXE, expected)


if __name__ == "__main__":
    unittest.main()
