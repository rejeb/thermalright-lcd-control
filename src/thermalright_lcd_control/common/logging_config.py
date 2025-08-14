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
    def _ensure_log_directory(cls):
        try:
            # Create directory with proper permissions
            Path(cls.LOG_DIR).mkdir(parents=True, exist_ok=True)
            # Set directory permissions (755)
            os.chmod(cls.LOG_DIR, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            # Create log file if it doesn't exist
            log_file = os.path.join(cls.LOG_DIR, cls.ERROR_LOG)
            Path(log_file).touch(exist_ok=True)
            # Set file permissions (644)
            os.chmod(log_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            
            return log_file
        except Exception as e:
            print(f"Failed to create log directory/file: {e}")
            return None

    @classmethod
    def _init_log_dir(cls):
        try:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
            error_log = cls.LOG_DIR / 'error.log'
            error_log.touch(exist_ok=True)
            print(f"Log directory created at: {cls.LOG_DIR}")
            return True
        except Exception as e:
            print(f"Failed to create log directory: {e}")
            return False

    @classmethod
    def setup_service_logger(cls):
        """Setup logger for the device controller component"""
        if cls._logger is not None:
            return cls._logger

        logger = logging.getLogger('thermalright.device_controller')

        # Clear any existing handlers
        logger.handlers.clear()

        # Set log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        if LoggerConfig.is_development_mode():
            # Development mode: console output
            handler = LoggerConfig._create_console_handler()
            logger.info("Device controller logger configured for development mode (console)")
        else:
            # Production mode: file logging
            handler = LoggerConfig._create_file_handler(LoggerConfig.SERVICE_LOG_FILE)
            logger.info(
                f"Device controller logger configured for production mode (file: {LoggerConfig.SERVICE_LOG_FILE})")

        logger.addHandler(handler)
        logger.propagate = False  # Prevent duplicate logs

        # File handler for errors only
        log_dir = os.path.expanduser('~/.local/share/thermalright-lcd-control/logs')
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, 'error.log')
        
        try:
            file_handler = RotatingFileHandler(
                error_log,
                maxBytes=1024*1024,  # 1MB
                backupCount=3
            )
            file_handler.setLevel(logging.ERROR)
            file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s\nTraceback:\n%(exc_info)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to setup file logging: {e}")

        cls._logger = logger
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
