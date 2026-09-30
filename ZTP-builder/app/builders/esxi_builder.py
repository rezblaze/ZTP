import concurrent.futures
import json
import logging

import app.ZTP as ZTP

logger = logging.getLogger(__name__)


def run_esxi_build(build):
    """Fn: run esxi build"""
    build["build_details"]["host"]
    hardware = build["networkdata"]["HARDWARE"]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        if "hp" in hardware:
            future = executor.submit(build_esxi_hpe, build)
        if "dell" in hardware:
            future = executor.submit(build_esxi_dell, build)
        try:
            # 1 hour 50 minutes timeout for esxi build per JJ's request
            future.result(timeout=6600)  
        except concurrent.futures.TimeoutError:
            logger.warning("Build process exceeded 2 hours and was terminated.")
            raise Exception("Build process exceeded 2 hours and was terminated.")


def build_esxi_hpe(build):
    """Fn: build esxi on hpe hardware"""
    logger.info(f"fn:build_esxi_hpe: {json.dumps(build, indent=4)}")
    hostname = build["build_details"]["host"]
    os = build["build_details"]["os"]
    if os.split("-")[-1].lower() != "hpe":
        raise Exception(f"{os} is unsupported for hpe hardware")
    immutable_iso = ZTP.Immutable(build).make_esxi_iso()
    ztp_actions = ZTP.Actions(hostname)
    if build.get("build_details").get("deploy_only") is not True:
        ztp_actions.ztp_ilo_config()
        ztp_actions.ztp_ilo_firmware_check()
        ztp_actions.ztp_prep()
    ztp_actions.ztp_deploy_esxi(immutable_iso["immutable"]["hostiso_url"])


def build_esxi_dell(build):
    """Fn: build esxi on dell hardware"""
    logger.info(f"fn:build_esxi_dell: {json.dumps(build, indent=4)}")
    hostname = build["build_details"]["host"]
    os = build["build_details"]["os"]
    if os.split("-")[-1].lower() != "dell":
        raise Exception(f"{os} is unsupported for dell hardware")
    ztp_actions = ZTP.Actions(hostname)
    if build.get("build_details").get("deploy_only") is not True:
        ztp_actions.ztp_prep()
    immutable_iso = ZTP.Immutable(build).make_esxi_iso()
    ztp_actions.ztp_deploy_esxi(immutable_iso["immutable"]["hostiso_url"])
