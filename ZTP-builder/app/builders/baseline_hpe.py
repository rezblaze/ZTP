import json
import logging

import app.build_service.loran_service as loran_service
import app.ZTP as ZTP

# from app.build_service.checkfirmware_service import checkfirmware_service

logger = logging.getLogger(__name__)


def baseline_hpe_ilo(build):
    hostname = build["build_details"]["host"]
    logger.info(f"fn:baseline_hpe_ilo: {json.dumps(build, indent=4)}")
    server_action = ZTP.Actions(hostname)
    if build.get("build_details").get("apply_ilo_baseline"):
        ilodata = server_action.ztp_ilo_config()
    else:
        ilodata = server_action.ztp_ilo_config_check()
    logger.info(f"\n\n {ilodata} \n\n")
    loran_service.update_loran_hostdata(hostname, ilodata)
    if build.get("build_details").get("apply_ilo_firmware"):
        ilodata = server_action.ztp_ilo_firmware()
    else:
        ilodata = server_action.ztp_ilo_firmware_check()
    logger.info(f"\n\n {ilodata} \n\n")
    loran_service.update_loran_hostdata(hostname, ilodata)
    del server_action


def baseline_hpe_bios(build):
    hostname = build["build_details"]["host"]
    logger.info(f"fn:baseline_hpe_bios: {json.dumps(build, indent=4)}")

    server_action = ZTP.Actions(hostname)
    if build.get("build_details").get("apply_hpe_bios_baseline"):
        logger.info("applying standard baseline hpe bios")
        biosdata = server_action.ztp_hpe_bios()
    else:
        logger.info("checking baseline hpe bios")
        biosdata = server_action.ztp_hpe_bios_check()
    logger.info(f"\n\n {biosdata} \n\n")
    loran_service.update_loran_hostdata(hostname, biosdata)
    del server_action


def baseline_hpe_prep(build):
    hostname = build["build_details"]["host"]
    server_action = ZTP.Actions(hostname)
    loran_service.add_hostdata_loran(hostname, build)
    logger.info("applying ilo baseline configuration.")
    ilodata = server_action.ztp_ilo_config()
    logger.info(f"\n\n {ilodata} \n\n")
    loran_service.update_loran_hostdata(hostname, ilodata)
    ilodata = server_action.ztp_ilo_firmware()
    logger.info(f"\n\n {ilodata} \n\n")
    loran_service.update_loran_hostdata(hostname, ilodata)
    ztp_prepdata = server_action.ztp_prep()
    logger.info(f"\n\n {ztp_prepdata} \n\n")
    loran_service.update_loran_hostdata(hostname, ztp_prepdata)


def baseline_hp_spp(build):
    """fn: baseline_hp_spp: Run SPP firmware update"""
    logger.info(f"fn:build_esxi_hpe: {json.dumps(build, indent=4)}")
    hostname = build["build_details"]["host"]
    server_action = ZTP.Actions(hostname)
    loran_service.add_hostdata_loran(hostname, build)
    server_action.ztp_apply_spp()


def baseline_hpe_tpm(build):
    hostname = build["build_details"]["host"]
    logger.info(f"fn:baseline_hpe_tpm: {json.dumps(build, indent=4)}")
    server_action = ZTP.Actions(hostname)
    tpmdata = server_action.ztp_hpe_tpm_check()
    logger.info(f"\n\n {tpmdata} \n\n")
    loran_service.update_loran_hostdata(hostname, tpmdata)
    del server_action

# def baseline_hp_checkfirmware(build):
#     lom = build["networkdata"]["LOM_FQDN"]
#     hostname = build["build_details"]["host"]
#     username = "AdminLO"
#     password = CREDS["hpe"].get("AdminLO", "")
#     node_type = build["networkdata"].get("NODE_TYPE", "ilo")
#     node_gen = build["networkdata"]["GENERATION"]
#     deploy = build.get("deploy", False)
#     loran_service.add_hostdata_loran(hostname, build)
#     logger.info(f"Running checkfirmware for {lom}")
#     try:
#         result = checkfirmware_service(lom, username, password, node_type, node_gen, deploy)
#         logger.info(f"Checkfirmware result for {lom}:\n{json.dumps(result, indent=4)}")
#         return result
#     except Exception as e:
#         logger.error(f"Error running checkfirmware_service for {lom}: {e}")
#         result = {"node": lom, "status": "error", "message": str(e), "success": False}
#         logger.info(f"Checkfirmware result for {lom}:\n{json.dumps(result, indent=4)}")
#         return result
