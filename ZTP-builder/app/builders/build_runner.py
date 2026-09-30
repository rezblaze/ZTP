import logging
import os
import signal
import time

import psutil

import app.build_service.kafka_service as kafka_service
import app.build_service.loran_service as loran_service
import app.builders.baseline_dell as baseline_dell
import app.builders.baseline_hpe as baseline_hpe
import app.builders.esxi_builder as esxi_builder
import app.builders.linux_builder as linux_builder
import app.builders.test_builder as test_builder
import app.builders.windows_builder as windows_builder
import app.logger.bmi_builder_logging as bmi_builder_logging
import app.ZTP as ZTP
from app.common.domain.build_statuses import BuildStatuses

logger = logging.getLogger(__name__)


def run(build):
    host = build["host"]
    build_id = build["id"]
    build_type = build["build_type"]
    ztp_version = ZTP.__version__
    try:
        starttime = time.time()
        logfile = bmi_builder_logging.setup_host_logging(host, build_id)
        signal.signal(signal.SIGTERM, abort_signal_handler)
        logger = logging.getLogger(__name__)
        logger.info(
            f"starting build for id: {build_id} host: {host} build_type: {build_type} ZTP Version: {ztp_version}"
        )
        env = build["bmi_env"]
        build.update(
            {
                "metadata": {
                    "cpid": os.getpid(),
                    "ppid": os.getppid(),
                    "logfile": f"https://{env}/buildlog/{logfile}",
                    "loran": f"https://loran-core.example.com/bmiapi/{host}",
                    "ZTP": f"{ztp_version}",
                }
            }
        )

        loran_service.add_hostdata_loran(host, build)
        status = f"{build_type} build is processing at the moment see log"
        kafka_service.append_build_event(build, BuildStatuses.PROCESSING.value, status)

        if build_type == "builds_linux":
            linux_builder.run_linux_build(build)

        if build_type == "builds_windows":
            windows_builder.run_windows_build(build)

        if build_type == "builds_esxi":
            esxi_builder.run_esxi_build(build)

        if build_type == "builds_test":
            test_builder.run_test_build(build)

        if build_type == "baseline_hpe_ilo":
            baseline_hpe.baseline_hpe_ilo(build)

        if build_type == "baseline_hpe_bios":
            baseline_hpe.baseline_hpe_bios(build)

        if build_type == "baseline_hpe_prep":
            baseline_hpe.baseline_hpe_prep(build)

        if build_type == "baseline_hp_spp":
            baseline_hpe.baseline_hp_spp(build)

        if build_type == "baseline_hpe_tpm":
            baseline_hpe.baseline_hpe_tpm(build)
        # if build_type == "baseline_hp_checkfirmware":
        #     baseline_hpe.baseline_hp_checkfirmware(build)

        if build_type == "baseline_dell_idrac":
            baseline_dell.baseline_dell_idrac(build)

        endtime = time.time() - starttime
        status_detail = "build completed successfully"
        build.update({"duration": round(endtime / 60, 2)})
        kafka_service.append_build_event(build, BuildStatuses.COMPLETE.value, status_detail)
    except (
        ZTP.exception.ServerNotInDNSException,
        ZTP.exception.PowerOnException,
        ZTP.exception.PrimaryMacNotFound,
        ZTP.exception.PrimaryNetworkGWUnreachable,
        ZTP.exception.ServerPingsException,
        ZTP.exception.UnsupportedByZTP,
        ZTP.exception.UnsupportedFirmware,
        ZTP.exception.UnsupportedHardware,
    ) as exception:
        logger.error(f"fn:run: exception processing build: {str(exception)}", exc_info=True)
        if build:
            endtime = time.time() - starttime
            build.update({"duration": round(endtime / 60, 2)})
            kafka_service.append_build_event(build, BuildStatuses.ABORTED.value, str(exception))
    except InterruptedError:
        logger.info("fn:run: ABORT signal received")
        if build:
            status = "build is aborting by request"
            endtime = time.time() - starttime
            build.update({"duration": round(endtime / 60, 2)})
            kafka_service.append_build_event(build, BuildStatuses.ABORTING.value, status)
    except Exception as exception:
        logger.error(f"fn:run: exception processing build: {str(exception)}", exc_info=True)
        if build:
            endtime = time.time() - starttime
            build.update({"duration": round(endtime / 60, 2)})
            kafka_service.append_build_event(
                build, BuildStatuses.ERROR.value, f"something went wrong! {str(exception)}"
            )


def abort_signal_handler(signal, frame):
    logger.info("!" * 80)
    logger.info("!" * 80)
    logger.info("!" * 80)
    logger.info("ABORT SIGNAL RECEIVED - TERMINATING PROCESS".center(80, "!"))
    logger.info("!" * 80)
    logger.info("!" * 80)
    logger.info("!" * 80)
    raise InterruptedError


def abort_build(build):
    print(f"fn:abort_build: {build}")
    host = "abort_" + build["host"]
    build_id = build["id"]
    env = build["bmi_env"]
    logfile = bmi_builder_logging.setup_host_logging(host, build_id)
    build.update(
        {
            "metadata": {
                "cpid": os.getpid(),
                "ppid": os.getppid(),
                "logfile": f"http://{env}/buildlog/{logfile}",
            }
        }
    )
    logger.info(f"fn:abort_build: {build}")
    cpid = build["build_details"]["cpid_to_kill"]
    print(f"fn:abort_build: {build} \nsending signal to abort child process ({cpid})")
    if psutil.pid_exists(cpid):
        print(f"child process ({cpid}) exists, sending SIGTERM")
        os.kill(cpid, signal.SIGTERM)
        time.sleep(2)
        if psutil.pid_exists(cpid):
            print(f"child process ({cpid}) still exists, sending SIGKILL")
            os.kill(cpid, signal.SIGKILL)
            time.sleep(1)
        if not psutil.pid_exists(cpid):
            print(f"child process ({cpid}) terminated successfully")
            status_detail = f"build child process ({cpid}) terminated successfully"
            kafka_service.append_build_event(build, BuildStatuses.ABORTING.value, status_detail)
    else:
        print(f"child process ({cpid}) already terminated")
        status_detail = f"build child process ({cpid}) already terminated! powering off server if its still running"
        kafka_service.append_build_event(build, BuildStatuses.ABORTING.value, status_detail)
    # process server power off
    host = build["build_details"]["host"]
    logger.warning(f"powering off server {host}")
    try:
        server_action = ZTP.Actions(host)
        server_action.ztp_power_off()
        msg = """

    CAUTION NOTE:  BMI has successfully force power off server to finish ABORT process!

    """
        logger.warning(msg)
    except Exception as err:
        logger.info(f"ABORT procedure fail to power off the server\n{err}")
    if build["build_details"].get("jenkins_job_url"):
        logger.info("Killing Jenkins job " + build["build_details"]["jenkins_job_url"])
        windows_builder.stop_job(build["build_details"]["jenkins_job_url"])
    logger.info("build aborted sucessfully")
    status_detail = "build aborted sucessfully"
    kafka_service.append_build_event(build, BuildStatuses.ABORTED.value, status_detail)
