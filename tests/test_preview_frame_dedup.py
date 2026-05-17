# SPDX-License-Identifier: Apache-2.0
"""Dédup des frames preview par référence forte (régression : id() réutilisé
après GC → frame silencieusement sautée, preview figé) et ordre d'arrêt du
RenderEngine (le sink ne doit être fermé qu'après le join du thread)."""
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display.render_engine import RenderEngine


class TestRenderEngineStopClose(unittest.TestCase):
    def _engine(self, sink):
        eng = RenderEngine.__new__(RenderEngine)
        eng.logger = mock.MagicMock()
        eng._sink = sink
        eng._event_bus = None
        eng._generator = None
        import threading
        eng._stop_event = threading.Event()
        return eng

    def test_stop_does_not_close_sink(self):
        sink = mock.MagicMock()
        eng = self._engine(sink)
        eng.stop()
        sink.close.assert_not_called()
        self.assertTrue(eng._stop_event.is_set())

    def test_close_closes_sink(self):
        sink = mock.MagicMock()
        eng = self._engine(sink)
        eng.close()
        sink.close.assert_called_once()

    def test_stop_all_closes_after_join(self):
        """DeviceLoader.stop_all : stop → join → close, dans cet ordre."""
        from thermalright_lcd_control.device_controller.display.device_loader import DeviceLoader
        loader = DeviceLoader.__new__(DeviceLoader)
        loader.logger = mock.MagicMock()
        order = []
        engine = mock.MagicMock()
        engine.stop.side_effect = lambda: order.append("stop")
        engine.close.side_effect = lambda: order.append("close")
        thread = mock.MagicMock()
        thread.join.side_effect = lambda timeout=None: order.append("join")
        loader._active = {"dev1": (engine, thread)}
        loader.stop_all()
        self.assertEqual(order, ["stop", "join", "close"])


if __name__ == "__main__":
    unittest.main()
