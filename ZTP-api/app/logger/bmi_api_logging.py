# Description: This module is responsible for setting up the logging configuration for the application.

import logging
from logging.handlers import TimedRotatingFileHandler

from app.config import config
from app.logger.request_context import RequestContextFilter


def setup_logging():
    settings = config.get_setting()

    # File handler for logging to a file with rotation
    file_handler = TimedRotatingFileHandler(f"{settings.log_dir}/bmi_api_app.log", when="midnight", backupCount=7)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s loglevel=%(levelname)-4s "
        "request_id=%(request_id)s logger=%(name)s "
        "%(funcName)s() L%(lineno)-4d %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(RequestContextFilter())

    # Console handler for real-time logging
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        fmt="%(asctime)s loglevel=%(levelname)-4s " "Fn=%(module)s  logger=%(name)s %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    # Root logger configuration
    app_logger = logging.getLogger()
    app_logger.setLevel(logging.INFO)  # Capture all log levels
    app_logger.addHandler(file_handler)
    app_logger.addHandler(console_handler)

    # Ensure exceptions are logged with stack traces
    logging.captureWarnings(True)
    logging.raiseExceptions = True
