import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.services import visualization_watcher as teamcenter_visualization


class TeamcenterVisualizationTests(unittest.TestCase):
    def test_my_files_open_uses_busy_flag_and_cleans_it_up(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "assembly.jt"
            jt_file.write_bytes(b"JT")
            busy_flag = Path(directory) / "teamcenter_visualization_busy.flag"
            window = Mock()
            window.handle = 10
            native_window = Mock()
            dialog_controls = (Mock(), Mock(), Mock())

            def trigger_open(*_args):
                self.assertTrue(busy_flag.exists())
                return dialog_controls

            def submit_file(*_args):
                self.assertTrue(busy_flag.exists())

            with (
                patch.object(
                    teamcenter_visualization,
                    "VISUALIZATION_BUSY_FLAG",
                    busy_flag,
                ),
                patch.object(
                    teamcenter_visualization,
                    "find_visualization_window",
                    return_value=window,
                ),
                patch(
                    "app.services.visualization_watcher.Desktop",
                    return_value=Mock(
                        **{"window.return_value": native_window}
                    ),
                ),
                patch.object(
                    teamcenter_visualization,
                    "_has_open_jt_model",
                    return_value=False,
                ),
                patch.object(
                    teamcenter_visualization,
                    "_trigger_open_dialog",
                    side_effect=trigger_open,
                ),
                patch.object(
                    teamcenter_visualization,
                    "_navigate_and_submit_file",
                    side_effect=submit_file,
                ),
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file
                )

            self.assertTrue(result)
            self.assertFalse(busy_flag.exists())

    def test_my_files_open_cleans_busy_flag_when_automation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            jt_file = Path(directory) / "assembly.jt"
            jt_file.write_bytes(b"JT")
            busy_flag = Path(directory) / "teamcenter_visualization_busy.flag"
            window = Mock()
            window.handle = 10

            with (
                patch.object(
                    teamcenter_visualization,
                    "VISUALIZATION_BUSY_FLAG",
                    busy_flag,
                ),
                patch.object(
                    teamcenter_visualization,
                    "find_visualization_window",
                    return_value=window,
                ),
                patch(
                    "app.services.visualization_watcher.Desktop",
                    return_value=Mock(),
                ),
                patch.object(
                    teamcenter_visualization,
                    "_has_open_jt_model",
                    return_value=True,
                ),
                patch.object(
                    teamcenter_visualization,
                    "_trigger_insert_dialog",
                    side_effect=RuntimeError("dialog failed"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "dialog failed"):
                    teamcenter_visualization.open_file_in_visualization(
                        jt_file
                    )

            self.assertFalse(busy_flag.exists())

    def test_open_jt_model_detection_accepts_titles_with_suffix_text(self):
        window = Mock()
        window.window_text.return_value = (
            "model.jt - Teamcenter Visualization"
        )
        window.descendants.return_value = []

        self.assertTrue(teamcenter_visualization._has_open_jt_model(window))

    def test_open_jt_model_detection_checks_document_tabs(self):
        window = Mock()
        window.window_text.return_value = "Teamcenter Visualization"
        document_tab = Mock()
        document_tab.window_text.return_value = "assembly.jt"
        window.descendants.side_effect = lambda control_type: (
            [document_tab] if control_type == "TabItem" else []
        )

        self.assertTrue(teamcenter_visualization._has_open_jt_model(window))

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
            "app.services.visualization_watcher.Desktop",
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
            "app.services.visualization_watcher.Desktop",
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
                    "app.services.visualization_watcher.Desktop",
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
                    "_trigger_open_dialog",
                    return_value=(dialog, filename, open_button),
                ) as trigger_open,
                patch.object(
                    teamcenter_visualization,
                    "_navigate_to_file",
                    return_value=file_item,
                ) as navigate,
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file
                )

        self.assertTrue(result)
        trigger_open.assert_called_once_with(window, native_window)
        navigate.assert_called_once_with(dialog, jt_file, 15)
        file_item.click_input.assert_called_once_with()
        open_button.wait.assert_called_once_with("enabled", timeout=2)
        open_button.click.assert_called_once_with()
        dialog.wait_not.assert_called_once_with("visible", timeout=15)

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
                    "app.services.visualization_watcher.Desktop",
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
                    "app.services.visualization_watcher.Desktop",
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
            "_navigate_to_file",
            return_value=file_item,
        ) as navigate:
            teamcenter_visualization._navigate_and_submit_file(
                dialog,
                submit_button,
                target,
            )

        navigate.assert_called_once_with(dialog, target, 15)
        file_item.click_input.assert_called_once_with()
        submit_button.wait.assert_called_once_with("enabled", timeout=2)
        submit_button.click.assert_called_once_with()
        dialog.wait_not.assert_called_once_with("visible", timeout=15)

    def test_file_picker_browses_the_complete_target_folder(self):
        target = Path(
            "C:/Project_Visualization/new/Backend/ServerUploads/dev/model.jt"
        )
        dialog = Mock()
        my_computer = Mock()
        filename_edit = Mock()
        open_button = Mock()
        list_view = Mock()
        list_view.item_count.return_value = 0
        controls = {
            1006: list_view,
            3070: my_computer,
            3078: filename_edit,
            1: open_button,
        }
        dialog.child_window.side_effect = lambda control_id: controls[control_id]
        items = [Mock() for _ in range(6)]

        with patch.object(
            teamcenter_visualization,
            "_wait_for_list_item",
            side_effect=items,
        ) as wait_for_item:
            result = teamcenter_visualization._navigate_to_file(
                dialog,
                target,
                timeout=15,
            )
        self.assertIs(result, items[-1])
        my_computer.click.assert_called_once_with()
        my_computer.click.assert_called_once_with()
        filename_edit.set_edit_text.assert_any_call("C:\\")
        for folder_name in target.parent.parts[1:]:
            filename_edit.set_edit_text.assert_any_call(folder_name + "\\")
        self.assertEqual(open_button.click.call_count, 6)
        self.assertEqual(wait_for_item.call_count, 6)
        wait_for_item.assert_any_call(
            list_view,
            "Project_Visualization",
            15,
        )
        wait_for_item.assert_called_with(list_view, target.name, 15)

    def test_wait_for_file_list_item_uses_native_win32_list_view(self):
        list_view = Mock()
        drive = Mock()
        drive.text.return_value = "C: ()"
        folder = Mock()
        folder.text.return_value = "Project_Visualization"
        list_view.item_count.return_value = 2
        list_view.get_item.side_effect = [drive, folder, drive, folder]

        result = teamcenter_visualization._wait_for_list_item(
            list_view,
            "Project_Visualization",
            timeout=1,
        )

        self.assertIs(result, folder)

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
        main_window.process_id.return_value = 42
        dialog_window = Mock()
        dialog_window.handle = 20
        dialog_window.process_id.return_value = 42
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
            "app.services.visualization_watcher.Desktop",
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
                "app.services.visualization_watcher.time.monotonic",
                side_effect=(0, 100),
            ), patch(
                "app.services.visualization_watcher.os.startfile",
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
                    "app.services.visualization_watcher.Desktop",
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
                    "app.services.visualization_watcher.os.startfile",
                    create=True,
                ) as startfile,
                patch("app.services.visualization_watcher.time.sleep"),
            ):
                result = teamcenter_visualization.open_file_in_visualization(
                    jt_file
                )

        self.assertTrue(result)
        startfile.assert_called_once_with(str(teamcenter_visualization.VIS_EXE))
        trigger_open.assert_called_once_with(window, native_window)
        submit_file.assert_called_once_with(
            dialog,
            open_button,
            jt_file,
        )

    def test_wait_for_open_dialog_uses_native_filename_and_open_controls(self):
        main_window = Mock()
        main_window.process_id.return_value = 42
        main_window.handle = 10
        dialog = Mock()
        dialog.handle = 20
        dialog.process_id.return_value = 42
        dialog.window_text.return_value = "Open"
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
            "app.services.visualization_watcher.Desktop",
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

    def test_wait_for_open_dialog_ignores_other_app_dialogs(self):
        main_window = Mock()
        main_window.handle = 10
        main_window.process_id.return_value = 42
        other_app_dialog = Mock()
        other_app_dialog.handle = 20
        other_app_dialog.process_id.return_value = 99
        other_app_dialog.is_visible.return_value = True
        other_app_dialog.element_info.class_name = "#32770"
        other_app_dialog.window_text.return_value = "Open"
        desktop = Mock()
        desktop.windows.return_value = [other_app_dialog]

        with (
            patch(
                "app.services.visualization_watcher.Desktop",
                return_value=desktop,
            ),
            patch(
                "app.services.visualization_watcher.time.monotonic",
                side_effect=(0, 100),
            ),
            patch("app.services.visualization_watcher.time.sleep"),
        ):
            with self.assertRaisesRegex(
                TimeoutError,
                "native Open file dialog did not appear",
            ):
                teamcenter_visualization._wait_for_open_dialog(
                    main_window,
                    timeout=1,
                )

        other_app_dialog.child_window.assert_not_called()

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
                "app.services.visualization_watcher.Desktop",
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
            patch.object(teamcenter_visualization, "_select_ribbon_tab"),
            patch("app.services.visualization_watcher.time.sleep"),
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
                "app.services.visualization_watcher.Desktop",
                return_value=desktop,
            ),
            patch.object(
                teamcenter_visualization,
                "_wait_for_open_dialog",
                return_value=dialog_controls,
            ) as wait_for_dialog,
            patch.object(teamcenter_visualization, "_activate_window"),
            patch.object(
                teamcenter_visualization,
                "_select_ribbon_tab",
            ) as select_tab,
        ):
            result = teamcenter_visualization._trigger_open_dialog(
                window,
                native_window,
            )

        self.assertEqual(result, dialog_controls)
        open_command.invoke.assert_called_once_with()
        select_tab.assert_called_once_with(window_spec, "File")
        native_window.type_keys.assert_not_called()
        wait_for_dialog.assert_called_once_with(native_window)

    def test_open_dialog_falls_back_when_ribbon_command_does_not_open_dialog(self):
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
                "app.services.visualization_watcher.Desktop",
                return_value=desktop,
            ),
            patch.object(
                teamcenter_visualization,
                "_wait_for_open_dialog",
                side_effect=(TimeoutError("ribbon missed"), dialog_controls),
            ) as wait_for_dialog,
            patch.object(teamcenter_visualization, "_activate_window"),
            patch.object(teamcenter_visualization, "_select_ribbon_tab"),
        ):
            result = teamcenter_visualization._trigger_open_dialog(
                window,
                native_window,
            )

        self.assertEqual(result, dialog_controls)
        open_command.invoke.assert_called_once_with()
        native_window.type_keys.assert_called_once_with("^o")
        self.assertEqual(wait_for_dialog.call_count, 2)

    def test_open_dialog_uses_file_menu_keyboard_fallback(self):
        window = Mock()
        window.handle = 10
        window_spec = Mock()
        native_window = Mock()
        open_command = Mock()
        open_command.exists.return_value = False
        application_menu = Mock()
        application_menu.invoke.side_effect = RuntimeError("menu unavailable")
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
                "app.services.visualization_watcher.Desktop",
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
            patch.object(teamcenter_visualization, "_select_ribbon_tab"),
        ):
            result = teamcenter_visualization._trigger_open_dialog(
                window,
                native_window,
            )

        self.assertEqual(result, dialog_controls)
        self.assertEqual(
            [call.args[0] for call in native_window.type_keys.call_args_list],
            ["^o", "%f", "o"],
        )

    def test_select_ribbon_tab_ignores_workspace_tabs(self):
        ribbon_tab = Mock()
        ribbon_tab.window_text.return_value = "Assembly"
        ribbon_tab.rectangle.return_value.top = 24
        workspace_tab = Mock()
        workspace_tab.window_text.return_value = "Assembly"
        workspace_tab.rectangle.return_value.top = 210
        window_spec = Mock()
        window_spec.descendants.return_value = [workspace_tab, ribbon_tab]

        selected = teamcenter_visualization._select_ribbon_tab(
            window_spec,
            "Assembly",
        )

        self.assertTrue(selected)
        ribbon_tab.select.assert_called_once_with()
        workspace_tab.select.assert_not_called()


if __name__ == "__main__":
    unittest.main()
