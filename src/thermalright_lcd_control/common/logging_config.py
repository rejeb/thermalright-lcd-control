# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Centralised logging configuration for the project.

Every component (GUI and device controller) writes to a single shared log
file so that the whole application can be diagnosed from one place. A single
:class:`RotatingFileHandler` instance is shared across all loggers to avoid
two handlers competing over the same file during rotation.

The log file always lives in the user's standard XDG state directory
(``$XDG_STATE_HOME`` or ``~/.local/state``); the application never writes to
system locations such as ``/var/log``.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Single, unified log file name used by every component.
LOG_FILE_NAME = "thermalright-lcd-control.log"


def _user_log_dir() -> Path:
    """Application log directory under the XDG state home (per the XDG Base
    Directory spec). Falls back to ``~/.local/state`` when unset."""
    xdg_state = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(xdg_state) if xdg_state else Path.home() / ".local/state"
    return base / "thermalright-lcd-control"


class LoggerConfig:
    """Centralised configuration for the project loggers."""

    # Shared handler instances (created lazily, reused by every logger).
    _shared_file_handler: logging.Handler | None = None
    _shared_console_handler: logging.Handler | None = None

    @staticmethod
    def is_development_mode():
        """
        Detect if running in development mode by checking various indicators.

        Returns:
            bool: True if in development mode
        """
        # Check if running from source directory
        current_file = Path(__file__).resolve()
        if 'src' in current_file.parts:
            return True

        # Check if installed in system directories
        system_paths = ['/usr', '/opt', '/var']
        if any(str(current_file).startswith(path) for path in system_paths):
            return False

        # Check if virtual environment is in current directory tree
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            venv_path = Path(sys.prefix)
            project_path = current_file.parent.parent.parent
            try:
                venv_path.relative_to(project_path)
                return True
            except ValueError:
                pass

        # Check environment variable
        return os.getenv('THERMALRIGHT_DEV_MODE', '').lower() in ('1', 'true', 'yes')

    @staticmethod
    def resolve_log_file() -> str:
        """Resolve the unified log file path.

        Always under the user's XDG state directory; the application never
        writes to system locations such as ``/var/log``."""
        return str(_user_log_dir() / LOG_FILE_NAME)

    @staticmethod
    def _create_console_handler():
        """Create a console handler with optional colors."""
        try:
            # Try to use colored output if colorlog is available
            import colorlog

            color_format = '%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            handler = colorlog.StreamHandler()
            handler.setFormatter(colorlog.ColoredFormatter(
                color_format,
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            ))
        except ImportError:
            # Fallback to standard console logging
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            handler.setFormatter(formatter)

        return handler

    @staticmethod
    def _create_file_handler(log_file_path):
        """Create a rotating file handler for the unified log file."""
        log_file = Path(log_file_path)

        try:
            # Ensure log directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)

            handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            handler.setFormatter(formatter)

            return handler

        except (PermissionError, OSError):
            return LoggerConfig._create_console_handler()

    @staticmethod
    def _get_shared_file_handler() -> logging.Handler:
        """Return the process-wide shared file handler (created once)."""
        if LoggerConfig._shared_file_handler is None:
            log_file = LoggerConfig.resolve_log_file()
            LoggerConfig._shared_file_handler = LoggerConfig._create_file_handler(log_file)
        return LoggerConfig._shared_file_handler

    @staticmethod
    def _get_shared_console_handler() -> logging.Handler:
        """Return the process-wide shared console handler (created once)."""
        if LoggerConfig._shared_console_handler is None:
            LoggerConfig._shared_console_handler = LoggerConfig._create_console_handler()
        return LoggerConfig._shared_console_handler

    @staticmethod
    def _configure(logger_name: str) -> logging.Logger:
        """Configure a named logger to write to the unified log file.

        The file handler is always attached so the log file exists for the
        "Open logs" action; in development mode a console handler is added too.
        """
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        logger.addHandler(LoggerConfig._get_shared_file_handler())
        if LoggerConfig.is_development_mode():
            logger.addHandler(LoggerConfig._get_shared_console_handler())

        logger.propagate = False  # Prevent duplicate logs
        return logger

    @staticmethod
    def setup_service_logger():
        """Setup logger for the device controller component."""
        return LoggerConfig._configure('thermalright.device_controller')

    @staticmethod
    def setup_gui_logger():
        """Setup logger for the LCD control UI component."""
        return LoggerConfig._configure('thermalright.lcd_control_ui')


def get_log_file_path() -> str:
    """Return the path of the unified log file."""
    return LoggerConfig.resolve_log_file()


def get_service_logger():
    """Get the device controller logger instance."""
    return LoggerConfig.setup_service_logger()


def get_gui_logger():
    """Get the LCD control UI logger instance."""
    return LoggerConfig.setup_gui_logger()
