import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.services import teamcenter_visualization


class TeamcenterVisualizationTests(unittest.TestCase):
    def test_find_window_prefers_active_visualization_window(self):
        blank_window = Mock()
        blank_window.window_text.return_value = "Teamcenter Visualization"
        blank_window.is_active.return_value = False
        document_window = Mock()
        document_window.window_text.return_value = (
            "Teamcenter Visualization - part.jt"
        )
        document_window.is_active.return_value = True
        desktop = Mock()
        desktop.windows.return_value = [blank_window, document_window]

        with patch(
            "app.services.teamcenter_visualization.Desktop",
            return_value=desktop,
        ):
            window = teamcenter_visualization.find_visualization_window()

        self.assertIs(window, document_window)

    def test_find_window_prefers_loaded_document_when_none_is_active(self):
        blank_window = Mock()
        blank_window.window_text.return_value = "Teamcenter Visualization"
        blank_window.is_active.return_value = False
        document_window = Mock()
        document_window.window_text.return_value = (
            "Teamcenter Visualization - part.jt"
        )
        document_window.is_active.return_value = False
        desktop = Mock()
        desktop.windows.return_value = [blank_window, document_window]

        with patch(
            "app.services.teamcenter_visualization.Desktop",
            return_value=desktop,
        ):
            window = teamcenter_visualization.find_visualization_window()

        self.assertIs(window, document_window)

    def test_open_uses_native_open_dialog_and_opens_file(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "assembly.jt"
            jt_file.write_bytes(b"JT")
            window = Mock()
            window.handle = 10
            window.window_text.return_value = ""
            window.descendants.return_value = []
            native_window = Mock()
            dialog = Mock()
            filename = Mock()
            open_button = Mock()
            file_item = Mock()
            file_item.text.return_value = jt_file.name
            file_list = Mock()
            file_list.items.return_value = [file_item]
            dialog.child_window.return_value = file_list
            directory_control = Mock()
            directory_control.element_info.control_id = 1003
            directory_control.element_info.class_name = "ComboBox"
            dialog.descendants.return_value = [directory_control]
            uia_desktop = Mock()
            uia_desktop.window.return_value = window
            win32_desktop = Mock()
            win32_desktop.window.return_value = native_window
            with (
                patch.object(
                    teamcenter_visualization,
                    "find_visualization_window",
                    return_value=window,
                ),
                patch(
                    "app.services.teamcenter_visualization.Desktop",
                    side_effect=lambda backend: (
                        uia_desktop if backend == "uia" else win32_desktop
                    ),
                ),
                patch.object(teamcenter_visualization, "_activate_window"),
                patch.object(
                    teamcenter_visualization,
                    "_has_open_jt_model",
                    return_value=False,
                ),
                patch.object(
                    teamcenter_visualization,
                    "_wait_for_open_dialog",
                    return_value=(dialog, filename, open_button),
                ),
                patch.object(
                    teamcenter_visualization,
                    "_selected_folder_name",
                    return_value=jt_file.parent.name,
                ),
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file
                )

        self.assertTrue(result)
        filename.set_edit_text.assert_called_once_with(
            str(jt_file.resolve().parent)
        )
        filename.set_focus.assert_called_once_with()
        filename.type_keys.assert_called_once_with("{ENTER}")
        file_item.click.assert_called_once_with()
        open_button.wait.assert_called_once_with("enabled", timeout=2)
        open_button.click.assert_called_once_with()

    def test_open_inserts_file_into_existing_jt_model(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "assembly.jt"
            jt_file.write_bytes(b"JT")
            window = Mock()
            window.handle = 10
            native_window = Mock()
            dialog = Mock()
            filename = Mock()
            insert_button = Mock()

            with (
                patch.object(
                    teamcenter_visualization,
                    "find_visualization_window",
                    return_value=window,
                ),
                patch(
                    "app.services.teamcenter_visualization.Desktop",
                    return_value=Mock(
                        **{"window.return_value": native_window}
                    ),
                ),
                patch.object(
                    teamcenter_visualization,
                    "_has_open_jt_model",
                    return_value=True,
                ),
                patch.object(
                    teamcenter_visualization,
                    "_trigger_insert_dialog",
                    return_value=(dialog, filename, insert_button),
                ) as trigger_insert,
                patch.object(
                    teamcenter_visualization,
                    "_navigate_and_submit_file",
                ) as submit_file,
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file
                )

        self.assertTrue(result)
        trigger_insert.assert_called_once_with(window, native_window)
        submit_file.assert_called_once_with(
            dialog,
            filename,
            insert_button,
            jt_file,
        )

    def test_open_upload_as_separate_document_even_when_model_is_open(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "uploaded.jt"
            jt_file.write_bytes(b"JT")
            window = Mock()
            window.handle = 10
            native_window = Mock()
            dialog = Mock()
            filename = Mock()
            open_button = Mock()

            with (
                patch.object(
                    teamcenter_visualization,
                    "find_visualization_window",
                    return_value=window,
                ),
                patch(
                    "app.services.teamcenter_visualization.Desktop",
                    return_value=Mock(
                        **{"window.return_value": native_window}
                    ),
                ),
                patch.object(
                    teamcenter_visualization,
                    "_has_open_jt_model",
                    return_value=True,
                ),
                patch.object(
                    teamcenter_visualization,
                    "_trigger_open_dialog",
                    return_value=(dialog, filename, open_button),
                ) as trigger_open,
                patch.object(
                    teamcenter_visualization,
                    "_navigate_and_submit_file",
                ) as submit_path,
                patch.object(
                    teamcenter_visualization,
                    "_trigger_insert_dialog",
                ) as trigger_insert,
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file,
                    open_in_new_document=True,
                )

        self.assertTrue(result)
        trigger_open.assert_called_once_with(window, native_window)
        submit_path.assert_called_once_with(
            dialog,
            filename,
            open_button,
            jt_file,
        )
        trigger_insert.assert_not_called()

    def test_upload_file_picker_navigates_to_its_folder_and_selects_file(self):
        target = Path("C:/uploads/session/model.jt")
        filename = Mock()
        file_item = Mock()
        file_item.text.return_value = target.name
        file_list = Mock()
        file_list.items.return_value = [file_item]
        dialog = Mock()
        directory_control = Mock()
        directory_control.element_info.control_id = 1003
        directory_control.element_info.class_name = "ComboBox"
        dialog.descendants.return_value = [directory_control]
        dialog.child_window.return_value = file_list
        submit_button = Mock()

        with patch.object(
            teamcenter_visualization,
            "_selected_folder_name",
            side_effect=["dev", "session"],
        ):
            teamcenter_visualization._navigate_and_submit_file(
                dialog,
                filename,
                submit_button,
                target,
                timeout=1,
            )

        filename.set_edit_text.assert_called_once_with(str(target.resolve().parent))
        filename.set_focus.assert_called_once_with()
        filename.type_keys.assert_called_once_with("{ENTER}")
        file_item.click.assert_called_once_with()
        submit_button.wait.assert_called_once_with("enabled", timeout=2)
        submit_button.click.assert_called_once_with()
        dialog.wait_not.assert_called_once_with("visible", timeout=15)

    def test_insert_dialog_uses_reference_shortcut(self):
        window = Mock()
        window.handle = 10
        native_window = Mock()
        dialog_controls = (Mock(), Mock(), Mock())

        with (
            patch.object(teamcenter_visualization, "_activate_window"),
            patch.object(
                teamcenter_visualization,
                "_wait_for_insert_dialog",
                return_value=dialog_controls,
            ) as wait_for_dialog,
        ):
            result = teamcenter_visualization._trigger_insert_dialog(
                window,
                native_window,
            )

        self.assertEqual(result, dialog_controls)
        native_window.restore.assert_called_once_with()
        native_window.type_keys.assert_called_once_with("^+i")
        wait_for_dialog.assert_called_once_with(native_window)

    def test_wait_for_insert_dialog_accepts_insert_file_dialog(self):
        main_window = Mock()
        main_window.handle = 10
        dialog_window = Mock()
        dialog_window.handle = 20
        dialog_window.is_visible.return_value = True
        dialog_window.element_info.class_name = "#32770"
        dialog_window.window_text.return_value = "Insert File"
        dialog = Mock()
        filename = Mock()
        filename.exists.return_value = True
        insert_button = Mock()
        insert_button.exists.return_value = True
        dialog.child_window.side_effect = lambda control_id: (
            filename if control_id == 3078 else insert_button
        )
        desktop = Mock()
        desktop.windows.return_value = [dialog_window]
        desktop.window.return_value = dialog

        with patch(
            "app.services.teamcenter_visualization.Desktop",
            return_value=desktop,
        ):
            result = teamcenter_visualization._wait_for_insert_dialog(
                main_window,
                timeout=1,
            )

        self.assertEqual(result, (dialog, filename, insert_button))

    def test_open_reports_when_visualization_window_is_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "assembly.jt"
            jt_file.write_bytes(b"JT")

            with patch.object(
                teamcenter_visualization,
                "find_visualization_window",
                return_value=None,
            ), patch(
                "app.services.teamcenter_visualization.time.monotonic",
                side_effect=(0, 100),
            ), patch(
                "app.services.teamcenter_visualization.os.startfile",
                create=True,
            ):
                with self.assertRaisesRegex(
                    TimeoutError,
                    "Teamcenter Visualization did not open within 90 seconds",
                ):
                    teamcenter_visualization.open_file_in_visualization(jt_file)

    def test_open_starts_visualization_when_it_is_not_running(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "assembly.jt"
            jt_file.write_bytes(b"JT")
            window = Mock()
            window.handle = 10
            window.window_text.return_value = ""
            window.descendants.return_value = []
            native_window = Mock()
            dialog = Mock()
            filename = Mock()
            open_button = Mock()
            file_item = Mock()
            file_item.text.return_value = jt_file.name
            file_list = Mock()
            file_list.items.return_value = [file_item]
            dialog.child_window.return_value = file_list
            directory_control = Mock()
            directory_control.element_info.control_id = 1003
            directory_control.element_info.class_name = "ComboBox"
            dialog.descendants.return_value = [directory_control]
            uia_desktop = Mock()
            uia_desktop.window.return_value = window
            win32_desktop = Mock()
            win32_desktop.window.return_value = native_window
            with (
                patch.object(
                    teamcenter_visualization,
                    "find_visualization_window",
                    side_effect=(None, window),
                ),
                patch(
                    "app.services.teamcenter_visualization.Desktop",
                    side_effect=lambda backend: (
                        uia_desktop if backend == "uia" else win32_desktop
                    ),
                ),
                patch.object(teamcenter_visualization, "_activate_window"),
                patch.object(
                    teamcenter_visualization,
                    "_trigger_open_dialog",
                    return_value=(dialog, filename, open_button),
                ) as trigger_open,
                patch.object(
                    teamcenter_visualization,
                    "_navigate_and_submit_file",
                ) as submit_file,
                patch(
                    "app.services.teamcenter_visualization.os.startfile",
                    create=True,
                ) as startfile,
                patch("app.services.teamcenter_visualization.time.sleep"),
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file
                )

        self.assertTrue(result)
        startfile.assert_called_once_with(str(teamcenter_visualization.VIS_EXE))
        trigger_open.assert_called_once_with(window, native_window)
        submit_file.assert_called_once_with(
            dialog,
            filename,
            open_button,
            jt_file,
        )

    def test_wait_for_open_dialog_uses_native_filename_and_open_controls(self):
        main_window = Mock()
        main_window.process_id.return_value = 42
        main_window.handle = 10
        dialog = Mock()
        dialog.handle = 20
        dialog.window_text.return_value = "Open"
        dialog.process_id.return_value = 99
        dialog.is_visible.return_value = True
        dialog.element_info.class_name = "#32770"
        filename = Mock()
        filename.exists.return_value = True
        open_button = Mock()
        open_button.exists.return_value = True
        dialog.child_window.side_effect = lambda control_id: (
            filename if control_id == 3078 else open_button
        )
        desktop = Mock()
        desktop.windows.return_value = [dialog]
        desktop.window.return_value = dialog

        with patch(
            "app.services.teamcenter_visualization.Desktop",
            return_value=desktop,
        ):
            found_dialog, found_filename, found_button = (
                teamcenter_visualization._wait_for_open_dialog(main_window)
            )

        self.assertIs(found_dialog, dialog)
        self.assertIs(found_filename, filename)
        self.assertIs(found_button, open_button)
        self.assertEqual(
            [call.kwargs["control_id"] for call in dialog.child_window.call_args_list],
            [3078, 1],
        )

    def test_open_dialog_falls_back_to_file_menu(self):
        window = Mock()
        window.handle = 10
        window_spec = Mock()
        native_window = Mock()
        open_command = Mock()
        open_command.exists.return_value = False
        application_menu = Mock()
        dialog_controls = (Mock(), Mock(), Mock())
        window_spec.child_window.side_effect = lambda **kwargs: (
            application_menu
            if kwargs.get("title") == "Application menu"
            else open_command
        )
        desktop = Mock()
        desktop.window.return_value = window_spec

        with (
            patch(
                "app.services.teamcenter_visualization.Desktop",
                return_value=desktop,
            ),
            patch.object(
                teamcenter_visualization,
                "_wait_for_open_dialog",
                side_effect=(
                    TimeoutError("shortcut missed"),
                    dialog_controls,
                ),
            ),
            patch.object(teamcenter_visualization, "_activate_window"),
            patch("app.services.teamcenter_visualization.time.sleep"),
        ):
            result = teamcenter_visualization._trigger_open_dialog(
                window,
                native_window,
            )

        self.assertEqual(result, dialog_controls)
        native_window.type_keys.assert_called_once_with("^o")
        application_menu.invoke.assert_called_once_with()
        open_command.invoke.assert_called_once_with()

    def test_open_dialog_prefers_ribbon_open_button(self):
        window = Mock()
        window.handle = 10
        window_spec = Mock()
        native_window = Mock()
        open_command = Mock()
        open_command.exists.return_value = True
        dialog_controls = (Mock(), Mock(), Mock())
        window_spec.child_window.return_value = open_command
        desktop = Mock()
        desktop.window.return_value = window_spec

        with (
            patch(
                "app.services.teamcenter_visualization.Desktop",
                return_value=desktop,
            ),
            patch.object(
                teamcenter_visualization,
                "_wait_for_open_dialog",
                return_value=dialog_controls,
            ) as wait_for_dialog,
            patch.object(teamcenter_visualization, "_activate_window"),
        ):
            result = teamcenter_visualization._trigger_open_dialog(
                window,
                native_window,
            )

        self.assertEqual(result, dialog_controls)
        open_command.invoke.assert_called_once_with()
        native_window.type_keys.assert_not_called()
        wait_for_dialog.assert_called_once_with(native_window)


if __name__ == "__main__":
    unittest.main()
