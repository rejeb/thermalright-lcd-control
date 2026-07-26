# SPDX-License-Identifier: Apache-2.0
"""UI native Qt Widgets : conversions pixmap, modèle overlay, fenêtre, backend."""
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.display import vips_utils as vu


def _app():
    return QApplication.instance() or QApplication([])


class TestPixmaps(unittest.TestCase):
    def setUp(self):
        _app()

    def test_pixmap_from_vips_rgb(self):
        from thermalright_lcd_control.gui.shared.pixmaps import pixmap_from_vips
        pm = pixmap_from_vips(vu.to_rgb(vu.solid(32, 16, (255, 0, 0, 255))))
        self.assertEqual((pm.width(), pm.height()), (32, 16))

    def test_pixmap_from_vips_rgba_and_other_modes(self):
        from thermalright_lcd_control.gui.shared.pixmaps import pixmap_from_vips
        pm = pixmap_from_vips(vu.solid(8, 8, (0, 255, 0, 128)))
        self.assertFalse(pm.isNull())
        import pyvips
        grey = (pyvips.Image.black(8, 8) + 128).cast("uchar")   # converti en RGB
        pm = pixmap_from_vips(grey)
        self.assertFalse(pm.isNull())

    def test_pixmap_from_data_url_roundtrip(self):
        import base64

        from thermalright_lcd_control.gui.shared.pixmaps import pixmap_from_data_url
        png = vu.png_bytes(vu.to_rgb(vu.solid(10, 10, (1, 2, 3, 255))))
        url = "data:image/png;base64," + base64.b64encode(png).decode()
        pm = pixmap_from_data_url(url)
        self.assertEqual((pm.width(), pm.height()), (10, 10))

    def test_pixmap_from_data_url_invalid(self):
        from thermalright_lcd_control.gui.shared.pixmaps import pixmap_from_data_url
        self.assertTrue(pixmap_from_data_url("").isNull())
        self.assertTrue(pixmap_from_data_url("not-a-data-url").isNull())


class TestOverlayModel(unittest.TestCase):
    def setUp(self):
        _app()

    def test_metric_text_precision_and_unit(self):
        from thermalright_lcd_control.gui.native.overlay import model
        w = {"type": "metric", "key": "cpu_usage", "prec": 1, "unit": "%"}
        self.assertEqual(model.metric_text(w, {"cpu_usage": 42.25}), "42.2%")
        # sans valeur live → valeur d'exemple
        self.assertEqual(model.metric_text(
            {"type": "metric", "key": "cpu_temperature", "prec": 0, "unit": "°"}, {}),
            "46°")

    def test_clock_text_modes(self):
        from thermalright_lcd_control.gui.native.overlay import model
        self.assertRegex(model.clock_text({"mode": "time"}), r"^\d{2}:\d{2}$")
        self.assertRegex(model.clock_text({"mode": "date"}), r"^\d{2}/\d{2}$")

    def test_ink_offset_positive_and_cached(self):
        from thermalright_lcd_control.gui.native.overlay import model
        font = model.widget_font({"font_size": 24})
        dx, dy = model.ink_offset(font)
        self.assertGreaterEqual(dx, 0.0)
        self.assertGreaterEqual(dy, 0.0)
        self.assertEqual(model.ink_offset(font), (dx, dy))    # cache stable

    def test_effective_move_set_rigid_label(self):
        from thermalright_lcd_control.gui.native.overlay import model
        widgets = [
            {"id": 1, "type": "metric", "group": 1},
            {"id": 2, "type": "metric_label", "group": 1, "floating": False},
            {"id": 3, "type": "metric", "group": 3},
            {"id": 4, "type": "metric_label", "group": 3, "floating": True},
        ]
        # valeur rigide → entraîne son label ; label flottant → indépendant
        self.assertEqual(model.effective_move_set(widgets, {1}), {1, 2})
        self.assertEqual(model.effective_move_set(widgets, {3}), {3})
        self.assertEqual(model.effective_move_set(widgets, {2}), {1, 2})
        self.assertEqual(model.effective_move_set(widgets, {4}), {4})


class TestBackendPilFrames(unittest.TestCase):
    """frame_ready_pil émet la frame (bytes JPEG) brute du controller."""

    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        from thermalright_lcd_control.gui.utils.config_loader import load_config
        config = load_config("resources/gui_config.yaml")
        fake = {"vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240, "id": "t"}

        class _Controller:
            def __init__(self):
                self.frame = vu.jpeg_bytes(vu.to_rgb(vu.solid(320, 240, (10, 20, 30, 255))))

            def last_base_frame(self, device_id):
                return self.frame

        self.backend = AppBackend(config, [fake], controller=_Controller())

    def tearDown(self):
        self.backend.cleanup()

    def test_pil_signal_emits_raw_frame(self):
        frames_pil = []
        self.backend.frame_ready_pil.connect(frames_pil.append)
        self.backend._tick()
        self.assertEqual(len(frames_pil), 1)
        self.assertIsInstance(frames_pil[0], bytes)
        img = vu.from_jpeg(frames_pil[0])
        self.assertEqual((img.width, img.height), (320, 240))


class TestNativeWindow(unittest.TestCase):
    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
        fake = {"vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240, "id": "t"}
        self.win = NativeMainWindow("resources/gui_config.yaml", [fake])

    def tearDown(self):
        self.win._really_quit = True
        self.win.close()

    def test_window_composition(self):
        self.assertEqual(self.win.tabs.count(), 4)
        self.assertGreaterEqual(self.win.titlebar.device_tabs.count(), 1)

    def test_hide_pauses_gui_timers_and_show_resumes(self):
        # cachée dans le tray : seule la boucle device doit rester active
        self.win.show()
        self.assertTrue(self.win.backend._timer.isActive())
        self.assertTrue(self.win.editor._live_timer.isActive())
        self.win.hide()
        self.assertFalse(self.win.backend._timer.isActive())
        self.assertFalse(self.win.editor._live_timer.isActive())
        self.win.show()
        self.assertTrue(self.win.backend._timer.isActive())
        self.assertTrue(self.win.editor._live_timer.isActive())

    def test_close_hides_to_tray(self):
        from PySide6.QtGui import QCloseEvent
        self.win.show()
        ev = QCloseEvent()
        self.win.closeEvent(ev)
        self.assertFalse(ev.isAccepted())
        self.assertTrue(self.win.isHidden())

    def test_inspector_edit_updates_preview_item(self):
        # Le widget passe à l'inspecteur via open_config_requested : si le
        # signal copie le dict (Signal(dict) → QVariantMap), l'inspecteur mute
        # une copie — le device reçoit la valeur mais l'item preview jamais.
        self.win.backend.reset_preview()
        editor = self.win.editor
        editor.add_widget("metric", "cpu_usage", None, 0.5, 0.5)
        metric = next(w for w in editor.widgets if w["type"] == "metric")
        editor._on_widget_clicked(metric["id"])    # ouvre l'inspecteur via signal
        insp = self.win.inspector
        self.assertIs(insp._widget, metric)        # même objet, pas une copie
        insp._edit(insp._widget, "font_size", 44)
        insp._edit(insp._widget, "bold", True)
        item = editor.view.items_by_id[metric["id"]]
        self.assertEqual(item.font().pixelSize(), 44)
        self.assertTrue(item.font().bold())

    def test_overlay_add_update_delete_roundtrip(self):
        editor = self.win.editor
        # le thème initial charge ses propres widgets → repartir d'un état vide
        self.win.backend.reset_preview()
        self.assertEqual(editor.widgets, [])
        editor.add_widget("metric", "cpu_usage", None, 0.5, 0.5)
        # a metric is value-only now — no auto-created label widget
        types = sorted(w["type"] for w in editor.widgets)
        self.assertEqual(types, ["metric"])
        self.assertEqual(len(json.loads(self.win.backend.get_widgets())), 1)
        # a label is an independent Text widget the user adds separately
        editor.add_widget("text", None, None, 0.3, 0.3)
        self.assertEqual(sorted(w["type"] for w in editor.widgets), ["metric", "text"])
        # editing the value's font size does NOT touch any other widget
        metric = next(w for w in editor.widgets if w["type"] == "metric")
        metric["font_size"] = 30
        editor.edit_widget(metric)
        self.assertEqual(metric["font_size"], 30)
        # deleting the selected metric removes only it (text stays)
        self.win.preview.view.set_selection({metric["id"]})
        editor.delete_selected()
        self.assertEqual(sorted(w["type"] for w in editor.widgets), ["text"])


class TestDeviceDialogHelpers(unittest.TestCase):
    def test_header_value_validation(self):
        from thermalright_lcd_control.gui.native.device_dialog import (
            _parse_value,
            _value_valid,
        )
        for good in ("", "width", "payload_size", "cmd", "2", "-3", "0x1F", "DADB"):
            self.assertTrue(_value_valid(good), good)
        for bad in ("foo", "0xZZ", "DAD", "1.5"):
            self.assertFalse(_value_valid(bad), bad)
        self.assertEqual(_parse_value("width"), "width")
        self.assertEqual(_parse_value("2"), 2)
        self.assertEqual(_parse_value("0x1F"), 31)
        self.assertEqual(_parse_value("DADB"), "DADB")


class TestDeviceDialogFocus(unittest.TestCase):
    """Le dialogue (sans transient parent) doit repasser devant quand la
    fenêtre principale est réactivée par le compositeur."""

    class _Backend:
        def get_ui_theme(self):
            return "dark"

        def get_usb_devices(self):
            return "[]"

        def suggest_device_id(self, *a):
            return ""

    def test_owner_activation_brings_dialog_to_front(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QWidget

        # pas de show()/processEvents réels : sous offscreen, pomper la boucle
        # d'événements peut toucher des objets Qt détruits par d'autres tests
        # (segfault) → QTimer.singleShot stubbé en appel immédiat
        from thermalright_lcd_control.gui.native import device_dialog as dd
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        _app()
        owner = QWidget()
        dialog = DeviceDialog(self._Backend(), parent=owner)
        called = []
        dialog._bring_to_front = lambda: called.append(True)
        visible = True
        dialog.isVisible = lambda: visible

        class _Now:
            @staticmethod
            def singleShot(_ms, fn):
                fn()

        orig = dd.QTimer
        dd.QTimer = _Now
        try:
            dialog.eventFilter(owner, QEvent(QEvent.WindowActivate))
            self.assertTrue(called)
            # dialogue fermé → plus de remise au premier plan
            visible = False
            del called[:]
            dialog.eventFilter(owner, QEvent(QEvent.WindowActivate))
            self.assertFalse(called)
        finally:
            dd.QTimer = orig


class TestConfirmDialog(unittest.TestCase):
    def test_buttons_and_focus_filter(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QDialog, QPushButton, QWidget

        from thermalright_lcd_control.gui.native import confirm_dialog as cd
        _app()
        owner = QWidget()
        dialog = cd.ConfirmDialog(owner, "Confirm deletion", "Delete X?",
                                  confirm_label="Delete", ui_theme="dark")
        labels = {b.text(): b for b in dialog.findChildren(QPushButton)}
        self.assertIn("Delete", labels)
        self.assertIn("Cancel", labels)
        self.assertEqual(labels["Delete"].objectName(), "danger")

        results = []
        dialog.accepted.connect(lambda: results.append(QDialog.Accepted))
        dialog.rejected.connect(lambda: results.append(QDialog.Rejected))
        labels["Delete"].click()
        labels["Cancel"].click()
        self.assertEqual(results, [QDialog.Accepted, QDialog.Rejected])

        # même remise au premier plan que DeviceDialog (pas de transient parent)
        called = []
        dialog._bring_to_front = lambda: called.append(True)
        dialog.isVisible = lambda: True

        class _Now:
            @staticmethod
            def singleShot(_ms, fn):
                fn()

        orig = cd.QTimer
        cd.QTimer = _Now
        try:
            dialog.eventFilter(owner, QEvent(QEvent.WindowActivate))
        finally:
            cd.QTimer = orig
        self.assertTrue(called)


if __name__ == "__main__":
    unittest.main()
