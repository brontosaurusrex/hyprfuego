"""Exercise reversible config changes without connecting to a compositor."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("hyprfuego", str(ROOT / "hyprfuego"))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.main = self.root / "hyprland.lua"
        self.module = self.root / "hyprfuego.lua"
        self.original = '-- Personal config\nrequire("hypr.mine")\n'
        self.main.write_text(self.original)
        patches = [patch.object(app, "MAIN", self.main), patch.object(app, "MODULE", self.module),
            patch.object(app, "SETTINGS", self.root / "settings/config.json"),
            patch.object(app, "BUILD", self.root / "build"), patch.object(app, "version"),
            patch.object(app, "apply_duration"),
            patch.object(app, "configerrors"), patch.object(app, "build"),
            patch.object(app, "load_plugin", return_value=True),
            patch.object(app, "artifact", return_value=self.root / "test.so"),
            patch.object(app, "ctl", return_value="")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_enable_twice_keeps_one_block_and_personal_settings(self):
        app.enable()
        app.enable()
        text = self.main.read_text()
        self.assertEqual(text.count(app.START), 1)
        self.assertTrue(text.startswith(self.original.rstrip()))
        self.assertEqual(len(list(self.root.glob("*.bak.hyprfuego-*"))), 2)

    def test_reload_failure_restores_files_and_unloads(self):
        app.configerrors.side_effect = [None, RuntimeError("bad config")]
        with self.assertRaisesRegex(RuntimeError, "bad config"):
            app.enable()
        self.assertEqual(self.main.read_text(), self.original)
        self.assertFalse(self.module.exists())
        app.ctl.assert_any_call("plugin", "unload", self.root / "test.so")

    def test_failure_restores_existing_managed_module(self):
        previous = "-- Managed by Hyprfuego.\n-- Previous version\n"
        self.module.write_text(previous)
        app.configerrors.side_effect = [None, RuntimeError("bad config")]
        with self.assertRaises(RuntimeError):
            app.enable()
        self.assertEqual(self.module.read_text(), previous)

    def test_unmanaged_module_is_preserved(self):
        self.module.write_text("-- My own file\n")
        with self.assertRaisesRegex(RuntimeError, "Unmanaged"):
            app.enable()
        app.load_plugin.assert_not_called()
        self.assertEqual(self.module.read_text(), "-- My own file\n")

    def test_disable_preserves_changes_added_after_enable(self):
        app.enable()
        self.main.write_text(self.main.read_text() + "-- Later personal change\n")
        app.disable()
        text = self.main.read_text()
        self.assertNotIn(app.START, text)
        self.assertIn('require("hypr.mine")', text)
        self.assertIn("-- Later personal change", text)

    def test_disable_does_not_require_old_hyprland_version(self):
        app.version.side_effect = RuntimeError("new version")
        app.disable()
        app.version.assert_not_called()

    def test_broken_markers_do_not_change_config(self):
        broken = self.original + app.START + "\n-- incomplete\n"
        self.main.write_text(broken)
        with self.assertRaises(RuntimeError):
            app.enable()
        self.assertEqual(self.main.read_text(), broken)
        app.load_plugin.assert_not_called()

    def test_module_uses_start_hook_and_only_close_shader(self):
        text = app.module_text()
        self.assertIn("hl.on('hyprland.start'", text)
        self.assertIn("session-load", text)
        self.assertIn("+shader_close_default:", text)
        self.assertNotIn("plugin.load", text)
        self.assertNotIn("shader_open", text)

    def test_reload_builds_before_unloading_owned_plugin(self):
        old = app.BUILD / "old/HyprWindowShade.so"
        old.parent.mkdir(parents=True)
        old.touch()
        new = app.BUILD / "new/HyprWindowShade.so"
        app.build.return_value = new
        events = []
        app.build.side_effect = lambda: events.append("build") or new
        app.ctl.side_effect = lambda *args: events.append(args) or ""
        with patch.object(app, "loaded", side_effect=[True, False]), patch.object(app, "owns_loaded", return_value=True):
            app.reload_plugin()
        self.assertEqual(events[0], "build")
        self.assertIn(("plugin", "unload", old), events)
        app.load_plugin.assert_called_once()

    def test_failed_reload_restores_old_binary(self):
        old = app.BUILD / "old/HyprWindowShade.so"
        old.parent.mkdir(parents=True)
        old.touch()
        app.build.return_value = app.BUILD / "new/HyprWindowShade.so"
        app.load_plugin.side_effect = RuntimeError("load failed")
        with patch.object(app, "loaded", side_effect=[True, False]), patch.object(app, "owns_loaded", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "load failed"):
                app.reload_plugin()
        app.ctl.assert_any_call("plugin", "load", old)

    def test_reload_refuses_foreign_plugin(self):
        with patch.object(app, "loaded", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "another installation"):
                app.reload_plugin()
        app.build.assert_not_called()
        app.ctl.assert_not_called()

    def test_build_failure_keeps_current_plugin_loaded(self):
        old = app.BUILD / "old/HyprWindowShade.so"
        old.parent.mkdir(parents=True)
        old.touch()
        app.build.side_effect = RuntimeError("compiler failure")
        with patch.object(app, "loaded", return_value=True), patch.object(app, "owns_loaded", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "compiler failure"):
                app.reload_plugin()
        app.ctl.assert_not_called()

    def test_size_preview_only_tags_two_test_windows(self):
        with patch.object(app, "loaded", return_value=True), patch.object(app, "reload_plugin"), \
             patch.object(app.subprocess, "Popen") as popen, patch.object(app.time, "sleep"):
            popen.return_value.returncode = 0
            popen.return_value.poll.return_value = 0
            app.preview(size_test=True)
        self.assertEqual(popen.call_count, 2)
        rules = [str(c.args[1]) for c in app.ctl.call_args_list if c.args[0] == "eval"]
        self.assertEqual(len(rules), 2)
        self.assertTrue(all("burn-close-size-preview.glsl" in s for s in rules))
        self.assertTrue(all("hyprfuego-preview-" in s for s in rules))
        self.assertIn("size={760,480}", rules[0])
        self.assertIn("size={440,260}", rules[1])
        self.assertEqual(self.main.read_text(), self.original)
        self.assertFalse(self.module.exists())
        self.assertFalse(any(c.args[:2] == ("plugin", "unload") for c in app.ctl.call_args_list))

    def test_duration_applies_and_preserves_personal_edits(self):
        app.enable()
        original_main = self.main.read_text()
        self.module.write_text(self.module.read_text() + "-- personal module note\n")
        app.configure_duration("1.8")
        self.assertEqual(app.duration_seconds(), 1.8)
        self.assertIn("burn-close.glsl", self.module.read_text())
        self.assertNotIn("@1.8", self.module.read_text())
        app.apply_duration.assert_called_once()
        self.assertIn("-- personal module note", self.module.read_text())
        self.assertEqual(self.main.read_text(), original_main)
        self.assertNotIn("@", app.rule(shader=app.ROOT / "shaders/burn-close-size-preview.glsl"))
        app.ctl.assert_any_call("reload")

    def test_duration_failure_restores_settings_and_module(self):
        app.enable()
        app.configure_duration("1.6")
        previous_settings = app.SETTINGS.read_text()
        previous_module = self.module.read_text()
        app.configerrors.side_effect = [None, RuntimeError("bad config")]
        with self.assertRaisesRegex(RuntimeError, "bad config"):
            app.configure_duration("2.5")
        self.assertEqual(app.SETTINGS.read_text(), previous_settings)
        self.assertEqual(self.module.read_text(), previous_module)

    def test_duration_without_enable_is_saved_without_desktop_access(self):
        app.configure_duration("2")
        self.assertEqual(app.duration_seconds(), 2)
        app.ctl.assert_not_called()
        self.assertFalse(self.module.exists())
        app.configure_duration("default")
        self.assertEqual(app.duration_seconds(), 1.15)
        self.assertNotIn("@", app.rule())

    def test_duration_range_is_saved_including_fractional_endpoints(self):
        for value in ("0.1", "0.75", "5.1", "12.5", "20"):
            with self.subTest(value=value):
                app.configure_duration(value)
                self.assertEqual(app.duration_seconds(), float(value))
        app.ctl.assert_not_called()

    def test_effect_switch_preserves_duration_and_personal_module_lines(self):
        app.enable()
        app.configure_duration("0.75")
        original_main = self.main.read_text()
        self.module.write_text(self.module.read_text() + "-- personal note\n")
        app.configure_effect("teleport")
        self.assertEqual(app.effect_name(), "teleport")
        self.assertIn("effects/teleport/close.glsl", self.module.read_text())
        self.assertIn("-- personal note", self.module.read_text())
        self.assertEqual(app.duration_seconds(), 0.75)
        self.assertEqual(self.main.read_text(), original_main)
        app.configure_effect("burn")
        self.assertIn("effects/burn/burn-close.glsl", self.module.read_text())
        self.assertEqual(app.duration_seconds(), 0.75)

    def test_effect_defaults_and_disabled_selection_need_no_desktop(self):
        app.configure_effect("teleport")
        self.assertEqual(app.duration_seconds(), 1.6)
        self.assertEqual(app.active_shader(True), app.active_shader())
        app.configure_effect("burn")
        self.assertEqual(app.duration_seconds(), 1.15)
        self.assertNotEqual(app.active_shader(True), app.active_shader())
        app.ctl.assert_not_called()

    def test_unknown_effect_changes_nothing(self):
        with self.assertRaises(ValueError):
            app.configure_effect("../other")
        self.assertFalse(app.SETTINGS.exists())
        app.ctl.assert_not_called()

    def test_failed_effect_switch_restores_settings_and_rule(self):
        app.enable()
        app.configure_effect("burn")
        previous_settings = app.SETTINGS.read_text()
        previous_module = self.module.read_text()
        app.apply_duration.side_effect = [RuntimeError("runtime update failed"), None]
        with self.assertRaisesRegex(RuntimeError, "runtime update failed"):
            app.configure_effect("teleport")
        self.assertEqual(app.SETTINGS.read_text(), previous_settings)
        self.assertEqual(self.module.read_text(), previous_module)

    def test_invalid_duration_does_not_touch_files_or_desktop(self):
        for value in ("nan", "inf", "0", "0.09", "-1", "20.1", "bad", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                app.configure_duration(value)
        self.assertFalse(app.SETTINGS.exists())
        self.assertEqual(self.main.read_text(), self.original)
        app.ctl.assert_not_called()

    def test_duration_does_not_overwrite_unrecognized_rule(self):
        app.enable()
        self.module.write_text("-- Managed by Hyprfuego.\n-- custom module\n")
        with self.assertRaisesRegex(RuntimeError, "Managed close rule not found"):
            app.configure_duration("2")
        self.assertFalse(app.SETTINGS.exists())

    def test_changing_duration_does_not_accumulate_window_tags(self):
        app.enable()
        original_rule = app.rule()
        app.configure_duration("5")
        self.assertEqual(app.rule(), original_rule)
        app.configure_duration("1")
        self.assertEqual(app.rule(), original_rule)
        self.assertEqual(app.duration_seconds(), 1)
        self.assertEqual(app.apply_duration.call_count, 2)

    def test_runtime_update_failure_restores_previous_duration(self):
        app.enable()
        app.configure_duration("5")
        applied = []
        def update():
            applied.append(app.duration_seconds())
            if len(applied) == 1:
                raise RuntimeError("runtime update failed")
        app.apply_duration.side_effect = update
        with self.assertRaisesRegex(RuntimeError, "runtime update failed"):
            app.configure_duration("1")
        self.assertEqual(applied, [1, 5])
        self.assertEqual(app.duration_seconds(), 5)


class RuntimeTiming(unittest.TestCase):
    def test_saved_duration_is_sent_to_both_shader_paths(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "SETTINGS", Path(tmp) / "config.json"), patch.object(app, "ctl") as ctl:
            for seconds in (0.1, 0.75, 5.1, 20, 1):
                app.SETTINGS.write_text('{"duration": ' + str(seconds) + '}')
                app.apply_duration()
                script = ctl.call_args.args[1]
                self.assertIn(f', {seconds})', script)
                self.assertIn(str(app.SHADER), script)
                self.assertIn("burn-close-size-preview.glsl", script)


if __name__ == "__main__":
    unittest.main()
