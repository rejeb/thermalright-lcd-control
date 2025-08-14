# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import logging
import os
import stat
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LoggerConfig:
    """Configuration centralisée pour les loggers du projet"""

    SERVICE_LOG_FILE = "/var/log/thermalright-lcd-control.log"
    GUI_LOG_FILE = "/tmp/thermalright-lcd-control-gui.log"

    _logger = None
    LOG_DIR = os.path.expanduser('~/.local/share/thermalright-lcd-control/logs')
    ERROR_LOG = 'error.log'

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
    def _create_console_handler():
        """Create a console handler with optional colors"""
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
        """Create a rotating file handler"""
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

        except (PermissionError, OSError) as e:
            return LoggerConfig._create_console_handler()

    @classmethod
    def _get_log_directory(cls):
        """Determine the log directory."""
        # Use explicit environment variable if set
        env_dir = os.getenv('THERMALRIGHT_LOG_DIR')
        if env_dir:
            return Path(env_dir).expanduser()

        # Fallback to $HOME/.local/share/thermalright-lcd-control/logs
        home_dir = os.getenv('HOME', str(Path.home()))
        return Path(home_dir) / '.local' / 'share' / 'thermalright-lcd-control' / 'logs'

    @classmethod
    def _ensure_log_directory(cls):
        """Ensure the log directory and error log file exist."""
        try:
            log_dir = cls._get_log_directory()
            log_dir.mkdir(parents=True, exist_ok=True)

            error_log = log_dir / cls.ERROR_LOG
            error_log.touch(exist_ok=True)

            # Set permissions
            log_dir.chmod(0o755)
            error_log.chmod(0o644)

            print(f"[thermalright] Using log directory: {log_dir}", file=sys.stderr)
            print(f"[thermalright] Error log file: {error_log}", file=sys.stderr)
            return str(error_log)
        except Exception as e:
            print(f"[thermalright] Failed to create log directory: {e}", file=sys.stderr)
            return None

    @classmethod
    def setup_service_logger(cls):
        """Set up the logger for the service."""
        error_log_path = cls._ensure_log_directory()

        logger = logging.getLogger('thermalright.device_controller')
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(console_handler)

        # File handler for error logs
        if error_log_path:
            try:
                file_handler = RotatingFileHandler(
                    error_log_path,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5
                )
                file_handler.setLevel(logging.ERROR)
                file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s\n%(exc_info)s'))
                logger.addHandler(file_handler)
            except Exception as e:
                logger.error(f"[thermalright] Failed to add file handler: {e}")

        logger.propagate = False
        return logger

    @staticmethod
    def setup_gui_logger():
        """Setup logger for the LCD control UI component"""
        logger = logging.getLogger('thermalright.lcd_control_ui')

        # Clear any existing handlers
        logger.handlers.clear()

        # Set log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        if LoggerConfig.is_development_mode():
            # Development mode: console output
            handler = LoggerConfig._create_console_handler()
            logger.info("LCD Control UI logger configured for development mode (console)")
        else:
            # Production mode: file logging
            handler = LoggerConfig._create_file_handler(LoggerConfig.GUI_LOG_FILE)
            logger.info(f"LCD Control UI logger configured for production mode (file: {LoggerConfig.GUI_LOG_FILE})")

        logger.addHandler(handler)
        logger.propagate = False  # Prevent duplicate logs

        return logger


def get_service_logger():
    """Get the device controller logger instance"""
    return LoggerConfig.setup_service_logger()


def get_gui_logger():
    """Get the LCD control UI logger instance"""
    return LoggerConfig.setup_gui_logger()
    """Get the LCD control UI logger instance"""
    return LoggerConfig.setup_gui_logger()
    return LoggerConfig.setup_gui_logger()
    """Get the LCD control UI logger instance"""
    return LoggerConfig.setup_gui_logger()
