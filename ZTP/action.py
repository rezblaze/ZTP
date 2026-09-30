# -*- coding: utf-8 -*-

""" Action module for specific actions
"""
import logging
import time

from ._common import log_my_msg
from ._hardware import get_primary_ethernet_mac
from .dell import DellServer
from .exception import (
    PowerOnException,
    ServerPingsException,
    UnsupportedFirmware,
    UnsupportedHardware,
)
from .hphpe import HpHpeServer
from .idrac import DellidracActions
from .ilo import HpeiloActions
from .networkdata import NetworkData
from .sanitycheck import check_if_host_ping
from .secrets import admin_lom_creds, del_non_std_ilo_accounts, del_companylo_account
from .serverhealth import esxi_server_health

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)


class Actions:
    """Class: Dell deployment functionality"""

    def __init__(self, server, lomuser="", lompass="", payload=""):
        """Actions class & associate method

        Args:
            server (str): ServerName
            lomuser (str, optional): [description]. Defaults to "".
            lompass (str, optional): [description]. Defaults to "".
        """
        log_my_msg("*** ZTP Actions module ***")
        self.server = server
        self.networkdata = NetworkData(self.server)
        self.all_networkdata = self.networkdata.all_networkdata()
        self.payload = payload
        log_my_msg(f"NetworkData: {self.all_networkdata}")
        if lomuser == "" and lompass == "":
            lomcred = admin_lom_creds(
                self.networkdata.lom_ip,
                self.networkdata.generation,
                self.networkdata.vendor,
            )
            self.lomuser = lomcred[0]
            self.lompass = lomcred[1]
        else:
            self.lomuser = lomuser
            self.lompass = lompass

    def __repr__(self):
        return f"Actions ({self.server})"

    def ztp_ilo_firmware_check(self):
        """Method - ztp_ilo_firmware_check"""
        log_my_msg("(Actions) ztp_ilo_firmware_check")
        ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
        return ilo.check_ilo_firmware()

    def ztp_chk_ad(self):
        """Method - ztp_ilo_firmware_check"""
        log_my_msg("(Actions) ztp_ilo_firmware_check")
        ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
        return ilo.chk_ad()

    def ztp_ilo_firmware(self):
        """Method - ztp_ilo_firmware"""
        log_my_msg("(Actions) ztp_ilo_firmware")
        ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
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
        ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
        del_companylo_account(self.networkdata.lom_ip, self.lomuser, self.lompass)
        return ilo.check_ilo_settings()

    def ztp_ilo_config(self):
        """Method:  ilo_standard_config - Check and if necessary apply standard config for HPE ilo"""
        log_my_msg("(Actions) ztp_ilo_config")
        ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
        del_companylo_account(self.networkdata.lom_ip, self.lomuser, self.lompass)
        iloresult = ilo.check_ilo_settings()
        if iloresult.get("ilo_check") == "fail":
            log_my_msg(" - applying ilo standards to fix configuration")
            ilo.apply_standard_ilo_setting()
            ilo.reset_ilo()
            del ilo
            ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
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
        if "hp" not in self.networkdata.vendor:
            raise UnsupportedHardware
        myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass, self.payload)
        return myserver.check_bios()

    def ztp_hpe_bios(self):
        """Method - ztp_hpe_bios setting"""
        log_my_msg("(Actions) ztp_hpe_bios")
        if "hp" not in self.networkdata.vendor:
            raise UnsupportedHardware
        myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass, self.payload)
        if myserver.get_power_status() == "on":
            raise PowerOnException
        ztp_hpe_bios = myserver.apply_bios()
        del myserver
        return ztp_hpe_bios

    def ztp_prep(self):
        """Method: ztp_prep - Preparing server with BIOS, RAID for deployment"""
        log_my_msg("(Actions) ztp_prep")
        ztp_prep_dict = {}
        if check_if_host_ping(self.networkdata.server_ip):
            raise ServerPingsException
        if self.networkdata.vendor == "dell":
            myserver = DellServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            myserver.odi_preztp()
            del myserver
        if "hp" in self.networkdata.vendor:
            myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass, self.payload)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_prep_dict = myserver.pre_ztp()
            del myserver
        return ztp_prep_dict

    def ztp_deploy_esxi(self, hostiso):
        """Method: ztp_deploy_esxi - Deploy ESXi for Dell or HPE"""
        log_my_msg("(Actions) ztp_deploy_esxi")
        if self.networkdata.vendor == "dell":
            myserver = DellServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            myserver.odi_deploy_esxi(hostiso)
            esxi_server_health(self.networkdata.server_ip)
            myserver.odi_apply_secureboot()
            del myserver
        if "hp" in self.networkdata.vendor:
            myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            myserver.deploy_esxi(hostiso)
            esxi_server_health(self.networkdata.server_ip)
            time.sleep(60)
            myserver.set_power_off_pushpowerbutton()
            time.sleep(10)
            myserver.apply_secureboot(True)
            esxi_server_health(self.networkdata.server_ip)
            del_non_std_ilo_accounts(self.networkdata.lom_ip, self.lomuser, self.lompass)
            del myserver

    def ztp_deploy_rhel(self, hostiso):
        """Method: ztp_deploy_rhel - Deploy RHEL for Dell or HPE"""
        log_my_msg("(Actions) ztp_deploy_rhel")
        ztp_deploy_rhel_dict = {}
        if self.networkdata.vendor == "dell":
            myserver = DellServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_deploy_rhel_dict = myserver.deploy_rhel(hostiso)
            del myserver

        if "hp" in self.networkdata.vendor:
            myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                raise PowerOnException
            ztp_deploy_rhel_dict = myserver.deploy_rhel(hostiso)
            del myserver
        log_my_msg("**** log_my_msg(ztp_deploy_rhel_dict) info")
        log_my_msg(ztp_deploy_rhel_dict)
        return ztp_deploy_rhel_dict

    def ztp_post_provisioning_rhel(self):
        """Method: ztp_post_provisioning_rhel - post provisioning"""
        log_my_msg("(Actions) ztp_post_provisioning_rhel")
        ztp_post_prov_dict = {}
        if "hp" in self.networkdata.vendor:
            myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            ztp_post_prov = myserver.rhel_post_provisioning()
            ztp_post_prov_dict.update(ztp_post_prov)
            del_non_std_ilo_accounts(self.networkdata.lom_ip, self.lomuser, self.lompass)
            del myserver
        return ztp_post_prov_dict

    def ztp_apply_spp(self):
        """Method: spp"""
        log_my_msg("(Actions) ztp_apply_spp")
        if self.networkdata.vendor == "hp":
            self.payload = {"TpmVisibility": "Hidden"}
        else:
            self.payload = {"Attributes": {"PlatformCertificate": "Disabled", "TpmVisibility": "Hidden"}}
        myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass, self.payload)
        myserver.apply_bios()
        spp_run = myserver.run_spp()
        del myserver
        if self.networkdata.vendor == "hp":
            self.payload = {"TpmVisibility": "Visible"}
        else:
            self.payload = {"Attributes": {"PlatformCertificate": "Disabled", "TpmVisibility": "Visible"}}
        myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass, self.payload)
        myserver.apply_bios()
        del myserver
        return spp_run

    def ztp_power_off(self):
        """Method: power_off"""
        log_my_msg("(Actions) ztp_power_off")
        if self.networkdata.vendor == "dell":
            myserver = DellServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                myserver.set_power_off()
            del myserver
        if "hp" in self.networkdata.vendor:
            myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            if myserver.get_power_status() == "on":
                myserver.set_power_off()
            del myserver

    def ztp_get_primary_ethernet_mac(self):
        """Method: get_primary_ethernet_mac"""
        log_my_msg("(Actions) ztp_get_primary_ethernet_mac")
        return get_primary_ethernet_mac(self.networkdata.vendor, self.networkdata.lom_ip, self.lomuser, self.lompass)

    def ztp_apply_secureboot(self, set_bool):
        """Method: ztp_apply_secureboot - apply SecureBoot for Dell or HPE"""
        log_my_msg("(Actions) ztp_apply_secureboot")
        if self.networkdata.vendor == "dell":
            myserver = DellServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            myserver.odi_apply_secureboot()
            del myserver
        if self.networkdata.vendor == "hpe":
            myserver = HpHpeServer(self.networkdata.lom_ip, self.lomuser, self.lompass)
            myserver.apply_secureboot(set_bool)
            del myserver

    def ztp_idrac_config_check(self):
        """Method - ztp_idrac_config_check"""
        log_my_msg("(Actions) ztp_idrac_config_check")
        idrac = DellidracActions(self.all_networkdata, self.lomuser, self.lompass)
        return idrac.check_idrac()

    def ztp_clear_iml(self):
        """Method - ztp_clear_iml"""
        log_my_msg("(Actions) ztp_clear_iml")
        ilo = HpeiloActions(self.all_networkdata, self.lomuser, self.lompass)
        return ilo.clear_iml_log()
