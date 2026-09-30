import logging
import time

logger = logging.getLogger(__name__)


def run_test_build(build):
    """This is test builder"""
    sleeptime = build["build_details"]["sleep"]
    cycle = build["build_details"]["cycle"]

    for i in range(cycle):
        logger.info(f"going to sleep for {sleeptime} for {i}/{cycle}")
        time.sleep(sleeptime)
