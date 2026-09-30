import logging
import os

import app.config.config as config
from app.common.logger.request_context_filter import RequestContextFilter


def setup_host_logging(host, build_id):
    settings = config.get_setting()
    name = host.split(".")[0]
    log_file = f"{name}_{str(build_id)}.log"
    handler = logging.FileHandler(f"{settings.log_dir}/{log_file}", delay=False)
    formatter = logging.Formatter(fmt="%(asctime)s %(levelname)-6s %(funcName)s() L%(lineno)-4d %(message)s")

    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    app_logger = logging.getLogger()
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)

    kafka_logger = logging.getLogger("kafka")
    kafka_logger.setLevel(logging.ERROR)
    kafka_logger.addHandler(handler)
    return log_file


def setup_consumer_logging():
    settings = config.get_setting()

    handler = logging.FileHandler(f"{settings.log_dir}/pid-{os.getpid()}.log", delay=False)
    formatter = logging.Formatter(fmt="%(asctime)s %(levelname)-6s %(funcName)s() L%(lineno)-4d %(message)s")
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    app_logger = logging.getLogger()
    app_logger.setLevel(logging.ERROR)
    app_logger.addHandler(handler)

    kafka_logger = logging.getLogger("kafka")
    kafka_logger.setLevel(logging.ERROR)
    kafka_logger.addHandler(handler)
