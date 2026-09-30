import errno
import os
import signal
from json import loads
from multiprocessing import Process

from kafka import KafkaConsumer

import app.builders.build_runner as build_runner
import app.config.config as config
import app.logger.bmi_builder_logging as bmi_builder_logging

# MAX_RUNTIME_SECONDS = 30 * 60 * 60  # 3 hours


def start_consumer():
    """Fn: message consumer from bmi-service"""
    print("starting message consumer")
    settings = config.get_setting()
    bmi_builder_logging.setup_consumer_logging()
    consumer = KafkaConsumer(
        "server_builds",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="main_builds",
        max_poll_interval_ms=settings.kafka_consumer_max_poll_interval_ms,
        value_deserializer=lambda x: loads(x.decode("utf-8")),
    )
    for message in consumer:
        build = message.value
        build_type = build["build_type"]
        print(f"fn:start_consumer: build received for id: {build['id']}")
        try:
            signal.signal(signal.SIGCHLD, wait_child)
            if build_type == "abort_build":
                newproc = Process(target=build_runner.abort_build, args=(build,))
            else:
                newproc = Process(target=build_runner.run, args=(build,))
            newproc.start()
            # newproc.join(timeout=MAX_RUNTIME_SECONDS)
            # if newproc.is_alive():
            #     newproc.terminate()
            #     logger = logging.getLogger(__name__)
            #     logger.error(f"Build process for build id {build['id']} exceeded maximum runtime and was terminated.")
            #     raise TimeoutError("Build process exceeded maximum runtime of 3 hours.")

        except Exception as exception:
            print(f"exception processing build: {str(exception)}")


def wait_child(signum, frame):
    """
    This is to deal with zombie processes
    Thanks to https://ofstack.com/python/24950/the-cause-of-the-python-zombie-process.html
    """
    try:
        while True:
            # -1  Represents any child process
            # os.WNOHANG  Indicates if there are no available needs  wait  Exit status of the child process, immediately return non-blocking
            cpid, status = os.waitpid(-1, os.WNOHANG)
            if cpid == 0:
                print("fn:wait_child: no child process was immediately available")
                break
            exitcode = status >> 8
            print(f"fn:wait_child: child process {cpid} exit with exitcode {exitcode}")
    except OSError as e:
        if e.errno == errno.ECHILD:
            print("fn:wait_child: current process has no existing unwaited-for child processes")
        else:
            raise
