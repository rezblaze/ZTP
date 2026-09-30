# -*- coding: utf-8 -*-

"""Action module for specific actions"""
import json
import logging
import time

import requests

import app.build_service.cache as cache
from app.build_service.cache import CREDS

from ._common import if_resp_not_ok, log_my_msg
from ._hardware import get_primary_ethernet_mac
from .dell import DellServer
from .exception import PowerOnException, UnsupportedFirmware, UnsupportedHardware
from .hphpe import HpHpeServer
from .idrac import DellidracActions
from .ilo import HpeiloActions
from .secrets import admin_lom_creds, del_non_std_ilo_accounts, del_companylo_account
from .serverhealth import esxi_server_health

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)


def update_eskm_config(networkdata: dict) -> dict:
    """fn: update eskm configuration from hpe variable data"""
    data = cache.HPE_VARIABLES
    for key, value in data["Global"].items():
        if key in ["time1", "time2", "SiteAEskm", "SiteBEskm", "EskmUser", "EskmPass"]:
            networkdata.update({key.upper(): value})
    generation = networkdata["GENERATION"]
    for key, value in data[generation].items():
        if key in ["eskm_group", "eskm_key"]:
            networkdata.update({key.upper(): value})
    return networkdata


class Actions:
    """Class: Dell deployment functionality"""

    def __init__(self, build, lomuser="", lompass="", payload={}):
        """Actions class & associate method

        Args:
            build (dict): build json
            lomuser (str, optional): [description]. Defaults to "".
            lompass (str, optional): [description]. Defaults to "".
        """
        log_my_msg("*** ZTP Actions module ***")
        self.payload = payload
        if type(build) is str:  # string usually will be pass as part of testing locally as server/hostname
            bmi_env = "bmi-prod.example.com"
            resp = requests.get(f"http://{bmi_env}/networkdata/{build}", verify=CREDS["verify"])
            if not resp.ok:
                raise Exception(
                    f"response failed http://{bmi_env}/networkdata/{build} with {resp.status_code} - {resp.text}"
                )
            networkdata = resp.json()
            resp = requests.get(f"http://{bmi_env}/serverinfo/{build}", verify=CREDS["verify"])
            if not resp.ok:
                raise Exception(
                    f"response failed http://{bmi_env}/serverinfo/{build} with {resp.status_code} - {resp.text}"
                )
            serverinfo = resp.json()
            build = {}
            build["networkdata"] = networkdata
            build["serverinfo"] = serverinfo
        elif type(build) is dict:  # dictionary is expected from bmi-service
            self.server = build["build_details"]["host"]
        else:
            raise Exception("build unknow type")
        self.networkdata = build["networkdata"]
        self.hardware = build["networkdata"]["HARDWARE"]
        self.generation = build["networkdata"]["GENERATION"]
        if "hp" in self.hardware:
            networkdata = update_eskm_config(networkdata)
        self.lomip = build["networkdata"]["LOMIP"]
        if lomuser == "" and lompass == "":
            lomcred = admin_lom_creds(
                self.lomip,
                self.generation,
                self.hardware,
            )
            self.lomuser = lomcred[0]
            self.lompass = lomcred[1]
        else:
            self.lomuser = lomuser
            self.lompass = lompass
        self.serverip = build["networkdata"]["IP"]
        self.env = build.get("bmi_env", "bmi-prod.example.com")

    def __repr__(self):
        return f"Actions ({self.server})"

    def ztp_ilo_firmware_check(self):
        """Method - ztp_ilo_firmware_check"""
        log_my_msg("(Actions) ztp_ilo_firmware_check")
        ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
        result = ilo.check_ilo_firmware()
        log_my_msg(json.dumps(result, indent=4))
        return result

    def ztp_chk_ad(self):
        """Method - ztp_ilo_firmware_check"""
        log_my_msg("(Actions) ztp_ilo_firmware_check")
        ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
        return ilo.chk_ad()

    def ztp_ilo_firmware(self):
        """Method - ztp_ilo_firmware"""
        log_my_msg("(Actions) ztp_ilo_firmware")
        ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
        ilo_firmware_result = ilo.update_ilo_firmware()
        if ilo_firmware_result["ilo_firmware_check"] == "fail":
            logger.critical(" - ilo firmware failed to update, please investigate.")
            log_my_msg(ilo_firmware_result)
            raise UnsupportedFirmware
        del ilo
        return ilo_firmware_result

    def ztp_ilo_config_check(self):
        """Method - ztp_ilo_config_check"""
        log_my_msg("(Actions) ztp_ilo_config_check")
        ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
        del_companylo_account(self.lomip, self.lomuser, self.lompass)
        return ilo.check_ilo_settings()

    def ztp_ilo_config(self):
        """Method:  ilo_standard_config - Check and if necessary apply standard config for HPE ilo"""
        log_my_msg("(Actions) ztp_ilo_config")
        ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
        del_companylo_account(self.lomip, self.lomuser, self.lompass)
        iloresult = ilo.check_ilo_settings()
        if iloresult.get("ilo_check") == "fail":
            log_my_msg(" - applying ilo standards to fix configuration")
            ilo.apply_standard_ilo_setting()
            ilo.reset_ilo()
            del ilo
            ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
            iloresult = ilo.check_ilo_settings()
            log_my_msg(iloresult)
        else:
            log_my_msg(iloresult)
        ilo.clear_iml_log()
        del ilo
        return iloresult

    def ztp_hpe_bios_check(self):
        """Method - ztp_hpe_bios_check"""
        log_my_msg("(Actions) ztp_hpe_bios_check")
        if "hp" not in self.hardware:
            raise UnsupportedHardware
        myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass, self.payload)
        return myserver.check_bios()

    def ztp_hpe_bios(self):
        """Method - ztp_hpe_bios setting"""
        log_my_msg("(Actions) ztp_hpe_bios")
        if "hp" not in self.hardware:
            raise UnsupportedHardware
        myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass, self.payload)
        if myserver.get_power_status() == "on":
            raise PowerOnException
        ztp_hpe_bios = myserver.apply_bios()
        del myserver
        return ztp_hpe_bios

    def ztp_prep(self):
        """Method: ztp_prep - Preparing server with BIOS, RAID for deployment"""
        log_my_msg("(Actions) ztp_prep")
        ztp_prep_dict = {}
        if self.hardware == "dell":
            myserver = DellServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            myserver.odi_preztp()
            del myserver
        if "hp" in self.hardware:
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass, self.payload)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_prep_dict = myserver.pre_ztp()
            del myserver
        return ztp_prep_dict

    def ztp_deploy_esxi(self, hostiso):
        """Method: ztp_deploy_esxi - Deploy ESXi for Dell or HPE"""
        log_my_msg("(Actions) ztp_deploy_esxi")
        if self.hardware == "dell":
            myserver = DellServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            myserver.odi_deploy_esxi(hostiso)
            esxi_server_health(self.serverip)
            myserver.odi_apply_secureboot()
            del myserver
        if "hp" in self.hardware:
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            myserver.deploy_esxi(hostiso)
            esxi_server_health(self.serverip)
            time.sleep(60)
            myserver.set_power_off_pushpowerbutton()
            time.sleep(10)
            myserver.apply_secureboot(True)
            esxi_server_health(self.serverip)
            del_non_std_ilo_accounts(self.lomip, self.lomuser, self.lompass)
            del myserver

    def ztp_deploy_rhel(self, hostiso):
        """Method: ztp_deploy_rhel - Deploy RHEL for Dell or HPE"""
        log_my_msg("(Actions) ztp_deploy_rhel")
        ztp_deploy_rhel_dict = {}
        if self.hardware == "dell":
            myserver = DellServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_deploy_rhel_dict = myserver.deploy_rhel(hostiso)
            del myserver

        if "hp" in self.hardware:
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_deploy_rhel_dict = myserver.deploy_rhel(hostiso)
            del myserver
        return ztp_deploy_rhel_dict

    def ztp_deploy_windows(self, hostiso):
        """Method: ztp_deploy_windows - Deploy Windows for Dell or HPE"""
        log_my_msg("(Actions) ztp_deploy_windows")
        ztp_deploy_windows_dict = {}
        if "hp" in self.hardware:
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_deploy_windows_dict = myserver.deploy_windows(hostiso)
            del myserver
        return ztp_deploy_windows_dict

    def ztp_post_provisioning_rhel(self):
        """Method: ztp_post_provisioning_rhel - post provisioning"""
        log_my_msg("(Actions) ztp_post_provisioning_rhel")
        ztp_post_prov_dict = {}
        if "hp" in self.hardware:
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            ztp_post_prov = myserver.rhel_post_provisioning()
            ztp_post_prov_dict.update(ztp_post_prov)
            del_non_std_ilo_accounts(self.lomip, self.lomuser, self.lompass)
            del myserver
        return ztp_post_prov_dict

    def ztp_apply_spp(self):
        """Method: spp"""
        log_my_msg("(Actions) ztp_apply_spp")
        servername = self.networkdata["SHORT_NAME"]
        laboneview = False
        log_my_msg(f"Checking OneView for server {servername}")
        resp = requests.get(f"https://{self.env}/bmo/iLO/oneview/{self.lomip}", verify=CREDS["verify"])
        if_resp_not_ok(resp)
        log_my_msg(resp.json())
        if resp.json().get("status") == "ERROR":
            log_my_msg("Temporarily adding to LAB openview instance")
            url_add = f"https://{self.env}/bmo/oneview/lab/add/{servername}"
            resp = requests.post(url_add, verify=CREDS["verify"])
            if_resp_not_ok(resp)
            laboneview = True
            log_my_msg(resp.json())
            log_my_msg("Waiting 60 seconds for OneView to process syncing...")
            time.sleep(60)


        def _check_firmware():
            log_my_msg("Fn: _check_firmware")
            url = f"https://{self.env}/bmo/oneview/firmware_compliance_report/{servername}"
            log_my_msg(f"Querying firmware compliance report from {url}")
            resp = requests.post(url, verify=CREDS["verify"])
            if not resp.ok:
                log_my_msg("host is not on any oneview or error getting firmware compliance report")

            resp_data = resp.json()
            firmware_update_required = resp_data.get("FirmwareUpdateRequired", True)
            # Log everything except the Details key
            log_data = {k: v for k, v in resp_data.items() if k != "Details"}
            log_my_msg(f"Firmware compliance report: {json.dumps(log_data, indent=2)}")
            if not firmware_update_required:
                log_my_msg("Firmware is compliant! No SPP update needed.")
            return firmware_update_required

        max_attempts = 3
        attempts = 0

        while _check_firmware() is True and attempts < max_attempts:
            attempts += 1
            log_my_msg(f"SPP update attempt {attempts} of {max_attempts}")
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass, self.payload)
            if attempts != 1 and myserver.get_power_status() == "on":
                log_my_msg("Powering off server for subsequent SPP update attempt")
                myserver.set_power_off()
            myserver.run_spp()
            del myserver
            log_my_msg("Waiting 60 seconds for firmware information sync to oneview...")
            time.sleep(60)  # wait before checking firmware again
            if attempts >= max_attempts and _check_firmware() is False:
                log_my_msg("Maximum SPP update attempts reached, firmware may still be non-compliant")

        if laboneview:
            log_my_msg("Removing server from LAB openview instance")
            url_remove = f"https://{self.env}/bmo/oneview/lab/remove/{servername}"
            resp = requests.delete(url_remove, verify=CREDS["verify"])
            if_resp_not_ok(resp)
            log_my_msg(resp.json())

    def ztp_power_off(self):
        """Method: power_off"""
        log_my_msg("(Actions) ztp_power_off")
        if self.hardware == "dell":
            myserver = DellServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                myserver.set_power_off()
            del myserver
        if "hp" in self.hardware:
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                myserver.set_power_off()
            del myserver

    def ztp_get_primary_ethernet_mac(self):
        """Method: get_primary_ethernet_mac"""
        log_my_msg("(Actions) ztp_get_primary_ethernet_mac")
        return get_primary_ethernet_mac(self.hardware, self.generation, self.lomip, self.lomuser, self.lompass)

    def ztp_apply_secureboot(self, set_bool):
        """Method: ztp_apply_secureboot - apply SecureBoot for Dell or HPE"""
        log_my_msg("(Actions) ztp_apply_secureboot")
        if self.hardware == "dell":
            myserver = DellServer(self.lomip, self.lomuser, self.lompass)
            myserver.odi_apply_secureboot()
            del myserver
        if self.hardware == "hpe":
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            myserver.apply_secureboot(set_bool)
            del myserver

    def ztp_idrac_config_check(self):
        """Method - ztp_idrac_config_check"""
        log_my_msg("(Actions) ztp_idrac_config_check")
        idrac = DellidracActions(self.networkdata, self.lomuser, self.lompass)
        return idrac.check_idrac()

    def ztp_get_iml(self):
        """Method - ztp_get_iml"""
        log_my_msg("(Actions) ztp_get_iml")
        hpeobj = HpHpeServer(self.lomip, self.lomuser, self.lompass)
        return hpeobj.get_all_iml_logs()

    def ztp_clear_iml(self):
        """Method - ztp_clear_iml"""
        log_my_msg("(Actions) ztp_clear_iml")
        ilo = HpeiloActions(self.networkdata, self.lomuser, self.lompass)
        return ilo.clear_iml_log()

    def ztp_check(self):
        """Method - ztp_check"""
        log_my_msg("(Actions) ztp_check")
        esxi_server_health(self.serverip)

    def ztp_check_secureboot(self):
        """Method - ztp_check_secureboot"""
        log_my_msg("(Actions) ztp_check_secureboot")
        if self.hardware == "dell":
            myserver = DellServer(self.lomip, self.lomuser, self.lompass)
            myserver.check_secureboot()
            del myserver
        if self.hardware == "hpe":
            myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass)
            myserver.check_secureboot()
            del myserver

    def ztp_hpe_tpm_check(self):
        """Method - ztp_hpe_tpm_check"""
        log_my_msg("(Actions) ztp_hpe_tpm_check")
        if "hp" not in self.hardware:
            raise UnsupportedHardware
        myserver = HpHpeServer(self.lomip, self.lomuser, self.lompass, self.payload)
        return myserver.apply_tpm_visibility()