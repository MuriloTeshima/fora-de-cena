from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from teleport_cam.app import App


class SettingsWindowTests(unittest.TestCase):
    def app(self, native):
        app = App.__new__(App)
        app.root = Mock()
        app.root.winfo_height.return_value = 790
        app.root.winfo_width.return_value = 1080
        app.root.winfo_rootx.return_value = 60
        app.root.winfo_rooty.return_value = 60
        app.root.winfo_screenwidth.return_value = 1440
        app.root.winfo_screenheight.return_value = 900
        app.settings_window = Mock()
        app.settings_dialog = Mock() if native else None
        app.settings_visible = False
        app.preview_revision = 12
        app.engine = SimpleNamespace(running=True)
        return app

    def test_mac_close_withdraws_the_whole_native_window_and_keeps_video_running(self):
        app = self.app(True)
        App.toggle_settings(app)
        self.assertTrue(app.settings_visible)
        app.settings_dialog.deiconify.assert_called_once()
        app.settings_window.place.assert_not_called()
        App.toggle_settings(app)
        self.assertFalse(app.settings_visible)
        app.settings_dialog.withdraw.assert_called_once()
        self.assertEqual(app.preview_revision, -1)
        self.assertTrue(app.engine.running)
        app.root.focus_set.assert_called_once()

    def test_other_platforms_keep_the_existing_overlay_and_remove_it_on_close(self):
        app = self.app(False)
        App.toggle_settings(app)
        app.settings_window.place.assert_called_once()
        App.hide_settings(app)
        app.settings_window.place_forget.assert_called_once()
        self.assertFalse(app.settings_visible)
        self.assertTrue(app.engine.running)

    def test_native_settings_can_be_reopened_without_losing_control_values(self):
        app = self.app(True)
        window = app.settings_window
        for _ in range(3):
            App.toggle_settings(app)
            App.hide_settings(app)
        self.assertIs(app.settings_window, window)
        self.assertEqual(app.settings_dialog.deiconify.call_count, 3)
        self.assertEqual(app.settings_dialog.withdraw.call_count, 3)

    def test_native_dialog_position_is_clamped_on_a_small_screen(self):
        app = self.app(True)
        app.root.winfo_rootx.return_value = 1300
        app.root.winfo_rooty.return_value = 800
        App.toggle_settings(app)
        app.settings_dialog.geometry.assert_called_once_with('410x570+1005+270')
