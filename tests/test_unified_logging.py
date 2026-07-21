# SPDX-License-Identifier: Apache-2.0
import unittest

from thermalright_lcd_control.common.logging_config import (
    LoggerConfig,
    get_gui_logger,
    get_log_file_path,
    get_service_logger,
)


class TestUnifiedLogging(unittest.TestCase):
    def test_log_file_path_is_single_unified_file(self):
        path = get_log_file_path()
        self.assertTrue(path.endswith("thermalright-lcd-control.log"))

    def test_gui_and_service_loggers_share_the_same_file_handler(self):
        gui = get_gui_logger()
        service = get_service_logger()

        def file_handlers(logger):
            from logging import FileHandler
            return [h for h in logger.handlers if isinstance(h, FileHandler)]

        gui_fh = file_handlers(gui)
        service_fh = file_handlers(service)
        self.assertTrue(gui_fh, "GUI logger has no file handler")
        self.assertTrue(service_fh, "Service logger has no file handler")
        # Same shared handler instance → single file, no rotation conflict.
        self.assertIs(gui_fh[0], service_fh[0])


if __name__ == "__main__":
    unittest.main()
