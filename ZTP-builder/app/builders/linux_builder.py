import json
import logging

import requests

import app.build_service.loran_service as loran_service
import app.ZTP as ZTP
from app.build_service.cache import CREDS

logger = logging.getLogger(__name__)


def chk_del_sat_reg(host):
    """Check and if exist delete satellite registration"""
    sat_creds = CREDS["satellite"]
    satuser = next(iter(sat_creds.keys()))
    satpass = next(iter(sat_creds.values()))
    satellites = ["lab-sat-01.example.com", "lab-sat-02.example.com", "lab-sat-03.example.com", "lab-sat-04.example.com"]
    logger.info(f"checking if {host} registered to satellite?")
    for sat in satellites:
        endpoint = f"https://{sat}/api/v2/hosts/{host}"
        HEADERS = {"content-type": "application/json"}
        try:
            resp = requests.get(endpoint, headers=HEADERS, verify=CREDS["verify"], auth=(satuser, satpass))
            if resp.status_code == 404:
                logger.info(f"Host {host} not found on satellite {sat}")
                continue
            elif resp.status_code == 401:
                logger.error(f"Unauthorized access to satellite {sat}. Check credentials.")
                continue
            if resp.ok:
                data = resp.json()
                hostid = data["id"]
                logger.info(f"pass: host found on {sat} with id {hostid}...going to delete it!")
                try:
                    resp = requests.delete(endpoint, headers=HEADERS, verify=CREDS["verify"], auth=(satuser, satpass))
                    if resp.ok:
                        logger.info(f"Host {host} deleted from satellite {sat}")
                        break
                except Exception as e:
                    logger.error(f"Error deleting host {host} on satellite {sat}: {e}")
        except Exception as e:
            logger.error(f"Erro checking host {host} on satellite {sat}: {e}")


def run_linux_build(build):
    logger.info(f"fn:run_linux_build: {json.dumps(build, indent=4)}")
    if build["networkdata"]["HARDWARE"] == "dell":
        run_linux_build_on_dell(build)
    if "hp" in build["networkdata"]["HARDWARE"]:
        run_linux_build_on_hpe(build)


def run_linux_build_on_hpe(build):
    hostname = build["build_details"]["host"]
    server_action = ZTP.Actions(hostname)
    if build.get("build_details").get("deploy_only") is True:
        logger.info("Clearing IML")
        server_action.ztp_clear_iml()
        logger.info("NOTE: deploy_only is True: Skipping ilo config, hardware prep steps")
    else:
        run_linux_build_full_deploy(server_action, hostname)
    immutable_iso = ZTP.Immutable(build).make_rhel_iso()
    loran_service.update_loran_hostdata(hostname, immutable_iso)
    logger.info(f"Host iso provider created {immutable_iso['immutable']['hostiso_url']}")

    ztp_deploy_rhel = server_action.ztp_deploy_rhel(immutable_iso["immutable"]["hostiso_url"])
    loran_service.update_loran_hostdata(hostname, ztp_deploy_rhel)

    if build["build_details"]["os"].startswith("rhel"):
        chk_del_sat_reg(hostname)
    ztp_post = server_action.ztp_post_provisioning_rhel()
    loran_service.update_loran_hostdata(hostname, ztp_post)


def run_linux_build_on_dell(build):
    hostname = build["build_details"]["host"]

    server_action = ZTP.Actions(hostname)
    if build.get("build_details").get("deploy_only") is False:
        server_action.ztp_prep()
    else:
        logger.info("NOTE: deploy_only is True: Skipping prep")
    immutable_iso = ZTP.Immutable(build).make_rhel_iso()
    loran_service.update_loran_hostdata(hostname, immutable_iso)
    logger.info(f"Host iso provider created {immutable_iso['immutable']['hostiso_url']}")

    ztp_deploy_rhel = server_action.ztp_deploy_rhel(immutable_iso["immutable"]["hostiso_url"])
    loran_service.update_loran_hostdata(hostname, ztp_deploy_rhel)

    if build["build_details"]["os"].startswith("rhel"):
        chk_del_sat_reg(hostname)
    ztp_post = server_action.ztp_post_provisioning_rhel()
    loran_service.update_loran_hostdata(hostname, ztp_post)


def run_linux_build_full_deploy(server_action, hostname):
    data = server_action.ztp_ilo_config()
    logger.info(f"\n{data}\n")
    loran_service.update_loran_hostdata(hostname, data)

    data = server_action.ztp_ilo_firmware()
    logger.info(f"\n{data}\n")
    loran_service.update_loran_hostdata(hostname, data)

    ztp_prepdata = server_action.ztp_prep()
    loran_service.update_loran_hostdata(hostname, ztp_prepdata)
