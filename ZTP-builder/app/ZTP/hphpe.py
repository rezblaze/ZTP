# -*- coding: utf-8 -*-

"""
hp_hpe.py -- hpe module to interact with HPE(GEN10) and HP(GEN9) hardware
"""

import copy
import json
import logging
import os
import socket
import time

import tabulate

from app.build_service.cache import HPE_VARIABLES

from ._common import if_resp_not_ok, log_my_msg
from ._healthcheck import check_http_iso
from ._session import (
    create_requests_retry_no_token_auth,
    create_requests_retry_session,
    delete_session,
)
from .exception import PrimaryNetworkGWUnreachable

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)

no_token_sessobj = create_requests_retry_no_token_auth()


class HpHpeServer:
    """Class: HPE deployment functionality"""

    def __init__(self, lom, lomuser, lompass, payload=""):
        """HpeServer class & associate method

        Args:
            lom (str): lights out management ip address
            lomuser (str): lights out management user
            lompass (str): lights out management passwd
        """
        log_my_msg("*** ZTP HpHpeServer module ***")
        self.lom = lom
        self.lomuser = lomuser
        self.lompass = lompass
        self.sessobj = create_requests_retry_session(lom, lomuser, lompass)
        hpe_hardware_model = get_hpe_hardware_model(self.lom, self.sessobj)
        self.model = hpe_hardware_model.split()[1]
        self.generation = hpe_hardware_model.split()[2]
        self.payload = payload
        standards_base_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json"
        self.standards_url = f"{standards_base_url}/{self.generation}_full.json"
        spp_folder = HPE_VARIABLES["spp"]["spp_folder"]
        gen_spp_iso = HPE_VARIABLES["spp"][f"{self.generation}_spp"] or ""
        self.spp_iso = f"{spp_folder}{gen_spp_iso}"

    def __repr__(self):
        return f"HpHpeServer ({self.sessobj})"

    def get_power_status(self):
        """Method: return power status"""
        return get_power_status(self.lom, self.sessobj)

    def set_power_off(self):
        """Method: set power off"""
        return set_power_off(self.lom, self.sessobj)

    def set_power_off_pushpowerbutton(self):
        """Method: set power off with powerpushbutton"""
        return set_power_off_pushpowerbutton(self.lom, self.sessobj)

    def set_power_on(self):
        """Method: set power on"""
        return set_power_on(self.lom, self.sessobj)

    def set_power_forcerestart(self):
        """Method: set power to forcerestart"""
        return set_power_forcerestart(self.lom, self.sessobj)

    def power_cycle_server(self):
        """Method: set power to forcerestart"""
        return power_cycle_server(self.lom, self.sessobj)

    def get_post_status(self):
        """Method: get server POST status"""
        return get_post_status(self.lom, self.sessobj)

    def get_all_ilo_firmeware(self):
        log_my_msg("(HpHpeServer) test fw")
        gen = self.generation
        if gen == "gen9":
            all_ilo_fw = get_all_gen9_firmware(self.lom, self.sessobj)
        else:
            all_ilo_fw = get_all_gen10_firmware(self.lom, self.sessobj)
        return all_ilo_fw

    def check_bios(self):
        """Method: check bios setting"""
        log_my_msg("(HpHpeServer) check_bios")
        bios_check = check_bios(self.lom, self.sessobj, self.standards_url, self.model, self.payload)
        return {"bios_check": bios_check, "standards_url": self.standards_url}

    def apply_bios(self):
        """Method: check and apply standard bios setting"""
        log_my_msg("(HpHpeServer) apply_bios")
        biosdict = {"standards_url": self.standards_url}
        if len(self.payload) > 0:
            bios_check = "fail"
        else:
            bios_check = check_bios(self.lom, self.sessobj, self.standards_url, self.model, self.payload)
        log_my_msg(f"Checking bios {bios_check}")
        if bios_check == "fail":
            apply_bios_settings(self.lom, self.sessobj, self.standards_url, self.model, self.generation, self.payload)
            biosdict.update({"bios_settings": "applied"})
        else:
            biosdict.update({"bios_settings": "unchanged"})
        return biosdict

    def run_stk(self):
        """Method: run stk for raid and eskm enablement"""
        log_my_msg("(HpHpeServer) run_stk")
        log_my_msg("Checking API for disk config ...")
        get_disk_info_list(self.lom, self.sessobj, self.generation)
        log_my_msg("Starting stk boot ...")
        stk_url_path = get_stk_iso()
        stkdict = {"stk_url": stk_url_path}
        run_stk = run_stk_iso(
            self.lom,
            self.sessobj,
            self.generation,
            stk_url_path,
        )
        if run_stk:
            stkdict.update({"stk_settings": "applied"})
        return stkdict

    def run_spp(self):
        """Method: run spp for firmware update"""
        log_my_msg("(HpHpeServer) run_spp : SPP Firmware update")
        # Define satellite servers
        sat_servers = [HPE_VARIABLES["SITE_B"]["media_server1"], HPE_VARIABLES["SITE_A"]["media_server1"]]
        # Try each satellite server until the ISO is found
        spp_url_path = None
        for sat_server in sat_servers:
            url = f"http://{sat_server}{self.spp_iso}"
            logger.info("Checking for SPP ISO at: %s", url)
            if check_http_iso(url):
                spp_url_path = url
                log_my_msg(f"Found SPP ISO at: {spp_url_path}")
                break
        if not spp_url_path:
            log_my_msg("SPP ISO not found on any satellite server.")
            return False
        sppdict = {"spp_url": spp_url_path}
        # Run the SPP ISO
        run_spp = run_spp_process(
            self.lom,
            self.lomuser,
            self.lompass,
            self.sessobj,
            self.generation,
            spp_url_path,
        )
        if run_spp:
            sppdict.update({"spp_settings": "applied"})
            log_my_msg(f"run_spp finished: {sppdict}")
        return sppdict

    def pre_ztp(self):
        """Method: Preztp for ZTP pipeline"""
        log_my_msg("(HpHpeServer) pre_ztp")
        preztpdict = {"standards_url": self.standards_url}
        bios_check = check_bios(self.lom, self.sessobj, self.standards_url, self.model, self.payload)
        secureboot_check = check_secureboot(self.lom, self.sessobj)
        if bios_check == "fail":
            if secureboot_check:
                set_secureboot(self.lom, self.sessobj, False)
            apply_bios_settings(self.lom, self.sessobj, self.standards_url, self.model, self.generation, self.payload)
            secureboot_check = check_secureboot(self.lom, self.sessobj)
            preztpdict.update({"bios_settings": "applied", "SecureBoot": secureboot_check})
        else:
            if secureboot_check:
                apply_secureboot(self.lom, self.sessobj, False)
                secureboot_check = check_secureboot(self.lom, self.sessobj)
            preztpdict.update({"bios_settings": "unchanged", "SecureBoot": secureboot_check})
        set_power_off(self.lom, self.sessobj)
        stkdict = self.run_stk()
        preztpdict.update({"stk": stkdict})
        time.sleep(15)
        set_power_off(self.lom, self.sessobj)
        time.sleep(15)
        return {"pre_ztp": preztpdict}

    def deploy_esxi(self, hostiso):
        """Method: Deploy esxi with any hostiso image on to server"""
        log_my_msg("(HpHpeServer) deploy_esxi")
        currenttime = time.strftime("%X %x %Z")
        log_my_msg(f"- starting time {currenttime}")
        check_http_iso(hostiso)
        eject_virtual_media(self.lom, self.sessobj, self.generation)
        mount_virtual_media(self.lom, self.sessobj, self.generation, hostiso)
        stat = get_power_status(self.lom, self.sessobj)
        log_my_msg(f" - current power state {stat}")
        if stat == "off":
            set_power_on(self.lom, self.sessobj)
            time.sleep(10)
        server_post = ""
        while server_post != "FinishedPost":
            server_post = get_post_status(self.lom, self.sessobj)
            log_my_msg(f"  - current state {server_post}")
            time.sleep(15)
        log_my_msg(" - assuming installation has started!")
        while server_post != "InPost":
            server_post = get_post_status(self.lom, self.sessobj)
            log_my_msg(f"  - current state {server_post}")
            time.sleep(15)
        log_my_msg(" - assuming install completed and rebooting!")
        while server_post != "FinishedPost":
            server_post = get_post_status(self.lom, self.sessobj)
            log_my_msg(f"  - current state {server_post}")
            time.sleep(15)
        log_my_msg("pass: esxi deployment completed")

    def deploy_rhel(self, hostiso):
        """Method: Deploy RHEL with any hostiso image on to server"""
        log_my_msg("(HpHpeServer) deploy_rhel")
        deploy_rhel_dict = {}
        check_http_iso(hostiso)
        eject_virtual_media(self.lom, self.sessobj, self.generation)
        mount_virtual_media(self.lom, self.sessobj, self.generation, hostiso)
        stat = get_power_status(self.lom, self.sessobj)
        log_my_msg(f" - current power state {stat}")
        if stat == "off":
            set_power_on(self.lom, self.sessobj)
            time.sleep(10)
        server_post = ""
        while server_post != "FinishedPost":
            server_post = get_post_status(self.lom, self.sessobj)
            log_my_msg(f"  - current state {server_post}")
            time.sleep(20)
        log_my_msg(" - assuming installation has started! ZTP will start checking IML for status in 3 minutes!")
        time.sleep(180)

        resp_bool, msg_received = check_iml_msg(self.lom, self.sessobj, "ZTP:KS:Pre_primary_network_check_")
        if msg_received.split("_")[4] == "FAIL":
            deploy_rhel_dict.update({"primary network check": "fail"})
            raise PrimaryNetworkGWUnreachable
        if msg_received.split("_")[4] == "PASS":
            log_my_msg("pass: primary network adapter check successful")
            deploy_rhel_dict.update({"primary network check": "pass"})

        if check_iml_msg(self.lom, self.sessobj, "ZTP:KS:Postkickstart_completed")[0]:
            deploy_rhel_dict.update({"post kickstart": "completed"})
        deploy_rhel_dict.update({"os": "completed"})
        log_my_msg(deploy_rhel_dict)
        return deploy_rhel_dict

    def deploy_windows(self, hostiso):
        """Method: Deploy windows with any hostiso image on to server"""
        log_my_msg("(HpHpeServer) deploy_windows")
        clear_iml_log(self.lom, self.sessobj)
        deploy_win_dict = {}
        check_http_iso(hostiso)
        eject_virtual_media(self.lom, self.sessobj, self.generation)
        mount_virtual_media(self.lom, self.sessobj, self.generation, hostiso)
        stat = get_power_status(self.lom, self.sessobj)
        log_my_msg(f" - current power state {stat}")
        if stat == "off":
            set_power_on(self.lom, self.sessobj)
            time.sleep(10)
        server_post = ""
        while server_post != "FinishedPost":
            server_post = get_post_status(self.lom, self.sessobj)
            log_my_msg(f"  - current state {server_post}")
            time.sleep(20)
        log_my_msg(" - Assuming installation has started! ZTP will start monitoring IML 3 minutes!")
        time.sleep(180)
        if check_iml_msg(self.lom, self.sessobj, "ZTP:WIN:Starting_windows_deployment", 10)[0]:
            deploy_win_dict.update({"os": "completed"})
        if check_iml_msg(self.lom, self.sessobj, "ZTP:WIN:Post_build_scripts_completed", 180)[0]:
            deploy_win_dict.update({"post build": "completed"})
        log_my_msg(deploy_win_dict)
        return deploy_win_dict

    def rhel_post_provisioning(self):
        """Method: RHEL post provising
        Directories: kickstart, postbuild
        """
        log_my_msg("(HpHpeServer) rhel_post_provisioning")
        post_prov_dict = {}
        if self_healing_before_post(self.lom, self.sessobj, "ZTP:POSTBUILD:Postbuild_scripts_starting")[0]:
            pass
        if check_iml_msg(
            self.lom,
            self.sessobj,
            "ZTP:POSTBUILD:Server_installation_and_postbuild_completed",
        )[0]:
            pass
        if check_iml_msg(
            self.lom,
            self.sessobj,
            "ZTP:BUILDCOMPLETED:Server_installation_and_postbuild_completed",
        )[0]:
            pass
        log_my_msg("All ZTP log messages from IML")
        all_msg = get_iml_log(self.lom, self.sessobj)
        partial_fail = False
        for message in all_msg:
            if "ZTP" in message["Message"]:
                log_my_msg(message["Message"])
                if "FAIL" in message["Message"]:
                    partial_fail = True
        if partial_fail:
            post_prov_dict.update({"post provisioning": "completed with partial failure"})
        else:
            post_prov_dict.update({"post provisioning": "completed"})
        log_my_msg(post_prov_dict)
        return post_prov_dict

    def reset_api(self):
        """Method: reset API"""
        log_my_msg("(HpHpeServer) reset_api")
        resp = reset_api(self.lom, self.sessobj, self.generation)
        if resp:
            log_my_msg("pass: api reset succeeded, rebooting server.")
            set_power_forcerestart(self.lom, self.sessobj)
            time.sleep(10)
        server_post = ""
        while server_post != "InPostDiscoveryComplete":
            server_post = get_post_status(self.lom, self.sessobj)
            log_my_msg(f"  - current state {server_post}")
            time.sleep(10)
            if server_post == "FinishedPost":
                break

    def apply_secureboot(self, value: bool):
        """Method: set secureboot"""
        log_my_msg("(HpeServer) apply_secureboot ")
        apply_secureboot(self.lom, self.sessobj, value)

    def get_all_iml_logs(self):
        """Method: get all iml log from ilo"""
        all_msg = get_iml_log(self.lom, self.sessobj)
        for message in all_msg:
            if "Maintenance note" in message["Message"]:
                log_my_msg(message["Message"])
        return all_msg

    def get_storage_info(self):
        """Method: get controller info"""
        return get_storage_info(self.lom, self.sessobj)
    
    def setup_NS204_controller(self):
        """Method: setup NS204 controller"""
        return setup_NS204_controller(self.lom, self.sessobj)
    
    def apply_tpm_visibility(self):
        """Method - apply_tpm_visibility"""
        log_my_msg("(HpeServer) apply_tpm_visibility ")
        return apply_tpm_visibility(self.lom, self.sessobj, self.generation)


###
### Helper Functions
###
def get_stk_iso():
    """Fn: get_stk_iso"""
    log_my_msg("Fn: get_stk_iso")
    PUBDIR = "/pub"
    # host_ip = socket.gethostbyname(socket.gethostname())
    # source_iso = "hpe-stk-custom.iso"
    source_iso = "hpe-stk-custom-mr_bugfix.iso"
    # stk_url = f"http://203.0.113.95/pub/{source_iso}"
    # stk_url = f"https://repo1.example.com/artifactory/company-docker/company-component/stk/{source_iso}"
    host_ip = socket.gethostbyname(socket.gethostname())
    url = f"http://{host_ip}{PUBDIR}/{source_iso}"
    if os.path.isdir(PUBDIR) is False:
        # raise Exception(f"fail: {PUBDIR} doesn't exist on the server , it is required!")
        log_my_msg(f" warning: {PUBDIR} does not exist!")
        return url
    os.chdir(PUBDIR)
    if os.path.exists(f"{PUBDIR}/{source_iso}") is True:
        log_my_msg(f"pass: {PUBDIR}/{source_iso} exists... Nothing to do!")
    else:
        log_my_msg(f" {source_iso} iso image does not exist!")
        raise Exception(f"fail: {source_iso} iso image does not exist!")
    # host_ip = socket.gethostbyname(socket.gethostname())
    stk_url = f"http://{host_ip}{PUBDIR}/{source_iso}"
    log_my_msg(f" info: using artifactory {stk_url}")
    return stk_url


def get_hardware_vendor(lom):
    """Fn: Get hardware vendor name"""
    log_my_msg("Fn: get_hardware_vendor")
    url = f"https://{lom}/redfish/v1"
    resp = no_token_sessobj.get("%s" % url)
    if_resp_not_ok(resp)
    data = resp.json()
    return next(iter(data["Oem"])).lower()


def get_hpe_hardware_model(lom, session):
    """Fn: Get hpe mode like proliant dl380 gen9"""
    log_my_msg("Fn: get_hpe_hardware_model")
    url = f"https://{lom}/redfish/v1/Chassis/1"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    return data["Model"].lower()


def error_on_none(status):
    """Fn: exit if no value"""
    log_my_msg("Fn: error_on_none")
    for key, value in status.items():
        if value is None:
            log_my_msg(f" fail: {key}:{value} has no value.")
            raise Exception()


def get_bios_standard_data(url, model):
    """Fn: get_bios_standard_data"""
    log_my_msg("Fn: Get bios data from standard")
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    if model == "dl380":
        hpe_bios_standards = resp.json()["#dl380_Bios.v1_0_0.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    if model == "dl385":
        hpe_bios_standards = resp.json()["#dl385_Bios.v1_0_0.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    if model == "dl325":
        hpe_bios_standards = resp.json()["#dl325_Bios.v1_0_4.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    if model == "dl345":
        hpe_bios_standards = resp.json()["#dl345_Bios.v1_0_4.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    if model == "dl560":
        hpe_bios_standards = resp.json()["#dl560_Bios.v1_0_0.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    ## CHANGE TO UEFI FOR ZTP
    hpe_bios_standards["Attributes"]["BootMode"] = "Uefi"
    return hpe_bios_standards


def check_bios(lom, session, standard_url, model, payload):
    """Check and compare BIOS settings on the server with the standard."""
    log_my_msg("Fn: check_bios")
    log_my_msg(f"model: {model}")
    log_my_msg(f"standard: {standard_url}")

    # Retrieve standard BIOS settings
    standard_bios = get_bios_standard_data(standard_url, model)["Attributes"]

    # Retrieve server BIOS settings
    server_bios = get_api_settings(lom, session, "/redfish/v1/systems/1/bios")
    # log_my_msg(f"Initial server_bios: {server_bios}")
    try:
        generation_variable = standard_url.split("/")[-1].split("_")[0]
        if "gen9" in generation_variable:
            server_bios = server_bios
        else:
            server_bios = server_bios["Attributes"]
    except KeyError:
        log_my_msg("KeyError: 'Attributes' not found in server_bios")
        return {}
    if len(payload) > 0:
        # Create a dictionary with the payload keys and their corresponding server BIOS values
        my_dict = {key: server_bios.get(key) for key in payload if key in server_bios}
        return my_dict
    else:
        # Compare server BIOS settings with standard BIOS settings
        return compare_two_dict({key: server_bios[key] for key in standard_bios if key in server_bios}, standard_bios)


def apply_bios_settings(lom, session, standard_url, model, generation, payload):
    """Fn: Apply standard bios setting based on gen"""
    log_my_msg("Fn: apply_bios_settings")
    url = "/redfish/v1/systems/1/bios/settings"
    log_my_msg(f"{url}, {model}, {generation}")
    bios_payload = get_bios_standard_data(standard_url, model)
    if generation == "gen9":
        bios_payload = bios_payload["Attributes"]
        if len(payload) > 0:
            bios_payload = payload
        patch_api_hpe(lom, session, url, bios_payload)
    # if generation == "gen10":
    if "gen1" in generation:
        if len(payload) > 0:
            bios_payload = payload
        # post_api_hpe(lom, session, url, bios_payload)
        patch_api_hpe(lom, session, url, bios_payload)
    time.sleep(10)
    set_power_off(lom, session)
    time.sleep(10)
    set_power_on(lom, session)
    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        log_my_msg(f"  - current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break
    bios_data = check_bios(lom, session, standard_url, model, payload)
    log_my_msg(bios_data)
    if bios_data == "fail":
        log_my_msg(" fail: apply bios failed")
        log_my_msg(bios_data)
    return bios_data


def get_api_settings(lom, session, end_point):
    """Fn: Get call from api endpoint"""
    log_my_msg(f"Fn: get_api_settings for {end_point}")
    url = f"https://{lom}{end_point}"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    return data


def post_api_hpe(lom, session, end_point, payload):
    """Fn: Post call to api endpoint"""
    log_my_msg("Fn: post_api_hpe")
    log_my_msg(f"Fn: post_api_hpe lom = {lom}, end_point = {end_point}, payload = {payload}")
    url = f"https://{lom}{end_point}"
    resp = session.post(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("pass: post accepted successful")


def patch_api_hpe(lom, session, end_point, payload):
    """Fn: Patch call to api endpoint"""
    log_my_msg("Fn: patch_api_hpe")
    time.sleep(10)
    url = f"https://{lom}{end_point}"
    resp = session.patch(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("pass: patch accepted successful")


def compare_two_dict(dict1, dict2):
    """Compare two dictionaries and log the differences."""
    settings_check = "pass"

    # Log header
    log_my_msg("{:=<120}".format(""))
    log_my_msg("{:<40}{:<35}{:<30}".format("Attributes", "Current Value", "Expected Value"))
    log_my_msg("{:=<120}".format(""))

    # Get all unique keys from both dictionaries
    all_keys = set(dict1.keys()).union(dict2.keys())

    for key in all_keys:
        current_value = dict1.get(key, "N/A")
        expected_value = dict2.get(key, "N/A")

        # Log the types of current_value and expected_value
        # log_my_msg(f"Key: {key}, Current Value Type: {type(current_value)}, Expected Value Type: {type(expected_value)}")

        # Compare values and log the results
        if current_value == expected_value:
            log_my_msg("{:<40}{:<35}{:<30}".format(str(key), str(current_value), str(expected_value)))
        else:
            log_my_msg("{:<40}{:<35}{:<30}{:<8}".format(str(key), str(current_value), str(expected_value), "XXX"))
            settings_check = "fail"

    # Log footer
    log_my_msg("{:=<120}".format(""))

    return settings_check


def get_power_status(lom, session):
    """Fn: Server power status"""
    log_my_msg("Fn: get_power_status")
    url = f"https://{lom}/redfish/v1/Systems/1"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    return data["PowerState"].lower()


def fail_if_power_on(lom, session):
    """Fn: raise exception if server is powered on"""
    log_my_msg("Fn: fail_if_power_on")
    power = get_power_status(lom, session)
    if power == "on":
        log_my_msg(" fail: server power must be off!")
        raise Exception()


def get_post_status(lom, session):
    """Fn: Get post status"""
    # log_my_msg("Fn: get_post_status")
    url = f"https://{lom}/redfish/v1/systems/1"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    try:
        return data["Oem"]["Hpe"]["PostState"]
    except KeyError:
        return data["Oem"]["Hp"]["PostState"]


def set_power_off_pushpowerbutton(lom, session):
    """Fn: Power Off server with push power button"""
    log_my_msg("Fn: set_power_off_pushpowerbutton")
    power = get_power_status(lom, session)
    if power == "off":
        log_my_msg(f"pass: Power state is: {power}")
        return
    url = f"https://{lom}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
    payload = {"ResetType": "PushPowerButton"}
    resp = session.post(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    if "Success" in resp.text:
        log_my_msg("pass: post accepted, waiting for server to poweroff")
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "off":
            log_my_msg(f"pass: power state is: {power}")
            break
        elif time.time() > timeout:
            log_my_msg(" 5 min since waiting server status should be poweroff")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(" - waiting for poweroff")


def set_power_off(lom, session):
    """Fn: Power Off server"""
    log_my_msg("Fn: set_power_off")
    power = get_power_status(lom, session)
    if power == "off":
        log_my_msg(f"pass: Power state is: {power}")
        return
    url = f"https://{lom}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
    payload = {"ResetType": "ForceOff"}
    resp = session.post(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    if "Success" in resp.text:
        log_my_msg("pass: post accepted, waiting for server to poweroff")
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "off":
            log_my_msg(f"pass: power state is: {power}")
            break
        elif time.time() > timeout:
            log_my_msg(" 5 min since waiting server status should be poweroff")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(" - waiting for poweroff")


def set_power_on(lom, session):
    """Fn: Power on server"""
    log_my_msg("Fn: set_power_on")
    power = get_power_status(lom, session)
    if power == "on":
        log_my_msg(f"pass: power state is: {power}")
        return
    url = f"https://{lom}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
    payload = {"ResetType": "On"}
    resp = session.post(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    if "Success" in resp.text:
        log_my_msg("pass: post accepted, waiting for server to poweron")
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "on":
            log_my_msg(f"pass: power state is: {power}")
            break
        elif time.time() > timeout:
            log_my_msg(" 5 min since waiting server status should be poweron")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(" - waiting for poweron")


def set_power_forcerestart(lom, session):
    """Fn: Force restart server"""
    log_my_msg("Fn: set_power_forcerestart")
    power = get_power_status(lom, session)
    if power == "off":
        log_my_msg(f"pass: power state is: {power}")
        log_my_msg("server is off running power on")
        set_power_on(lom, session)
    log_my_msg(f"current power status {power}. issuing a force restart on server.")
    url = f"https://{lom}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
    payload = {"ResetType": "ForceRestart"}
    resp = session.post(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    if "Success" in resp.text:
        log_my_msg("pass: post accepted, waiting for server to poweron")
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "on":
            log_my_msg(f"pass: Power state is: {power}")
            break
        elif time.time() > timeout:
            log_my_msg(" 5 min since waiting server status should be poweroff")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(f" current power state is {power}")
            log_my_msg(" - waiting for poweron")


def power_cycle_server(lom, session):
    """Fn: Power off the server and then power it back on, wait for boot completion"""
    log_my_msg("Fn: power_cycle_server")
    set_power_off(lom, session)
    log_my_msg("Server powered off. Waiting for a few seconds before powering on.")
    time.sleep(10)  # Wait for 10 seconds before powering on
    set_power_on(lom, session)
    log_my_msg("Server powered on. Waiting for boot to complete.")

    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        log_my_msg(f"  - current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break

    log_my_msg("Server boot complete.")
    return True


def check_virtual_media(lom, session):
    """Fn: Check virtual media"""
    log_my_msg("Fn: check_virtual_media")
    url = f"https://{lom}/redfish/v1/Managers/1/VirtualMedia/2/"
    resp = session.get(url)
    data = resp.json()
    if_resp_not_ok(resp)
    # return data["Image"]
    return data["Inserted"]


def eject_virtual_media(lom, session, generation):
    """Fn: Eject virtual media"""
    log_my_msg("Fn: eject_virtual_media")
    url = f"https://{lom}/redfish/v1/Managers/1/VirtualMedia/2/"
    resp = session.get(url)
    data = resp.json()
    if_resp_not_ok(resp)
    if "NotConnected" in data["ConnectedVia"] and data["Image"] == "" and data["Inserted"] is False:
        log_my_msg(" - no virtual media connected")
    else:
        end_point = "/redfish/v1/Managers/1/VirtualMedia/2/Actions/VirtualMedia.EjectMedia/"
        if generation == "gen9":
            end_point = "/redfish/v1/Managers/1/VirtualMedia/2/Actions/Oem/Hp/HpiLOVirtualMedia.EjectVirtualMedia/"
        body = {}
        resp = session.post(f"https://{lom}{end_point}", data=json.dumps(body))
        statuscode = resp.status_code
        if statuscode == 200:
            log_my_msg("pass: eject virtual media completed")
        else:
            log_my_msg(f" fail: post failed with response {statuscode}")
            raise Exception()


def mount_virtual_media(lom, session, generation, iso):
    """Fn: Mount virtual media"""
    log_my_msg("Fn: Mount virtualmedia")
    body = {"Image": iso}
    log_my_msg(body)
    url = f"https://{lom}/redfish/v1/Managers/1/VirtualMedia/2/Actions/VirtualMedia.InsertMedia/"
    if generation == "gen9":
        url = f"https://{lom}/redfish/v1/Managers/1/VirtualMedia/2/Actions/Oem/Hp/HpiLOVirtualMedia.InsertVirtualMedia/"
    resp = session.post(url, data=json.dumps(body))
    if_resp_not_ok(resp)
    boot_order_url = f"https://{lom}/redfish/v1/Managers/1/VirtualMedia/2/"
    resp = session.get(boot_order_url)
    if_resp_not_ok(resp)
    data = resp.json()
    if "Image" in data:
        iso = data["Image"]
        log_my_msg(f"  pass: virtual media mounted {iso}")
    body = {"Oem": {"Hpe": {"BootOnNextServerReset": True}}}
    if generation == "gen9":
        body = {"Oem": {"Hp": {"BootOnNextServerReset": True}}}
    resp = session.patch(boot_order_url, data=json.dumps(body))
    if_resp_not_ok(resp)
    log_my_msg("pass: virtual media boot on next server reset")


def clear_iml_log(lom, session):
    """Fn: Clear IML log messages"""
    log_my_msg("Fn: clear_iml_log")
    body = {}
    url = f"https://{lom}/redfish/v1/Systems/1/LogServices/IML/Actions/LogService.ClearLog/"
    resp = session.post(url, data=json.dumps(body))
    if_resp_not_ok(resp)
    log_my_msg("pass: clear IML log")


def get_iml_log(lom, session):
    """Fn: Get IML log messages"""
    url = f"https://{lom}/redfish/v1/Systems/1/LogServices/IML/Entries"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    page_iml_items = []
    try:
        chk_page = data["links"].get("NextPage", "NULL")
        if chk_page == "NULL":
            return resp.json()["Items"]
        for x in range(1, chk_page["page"] + 1):
            url = f"https://{lom}/redfish/v1/Systems/1/LogServices/IML/Entries/?page={x}"
            resp = session.get(url)
            if_resp_not_ok(resp)
            data = resp.json()["Items"]
            page_iml_items.extend(data)
        return page_iml_items
    except KeyError:
        return data["Members"]


def check_iml_msg(lom, session, msg, timeout_minutes=30):
    """Fn: Check IML messages"""
    log_my_msg(f"Fn: check_iml_msg - message we are looking for is: {msg}")
    log_my_msg(f" - will wait up to {timeout_minutes} minutes for the message to appear in IML")
    timeout = time.time() + timeout_minutes * 60
    msg_list = []
    while True:
        time.sleep(10)
        message = get_iml_log(lom, session)
        msg_received = False
        for items in message:
            if msg in items.get("Message", "NULL"):
                log_my_msg(items["Message"])
                msg_received = True
                return msg_received, items["Message"]
            else:
                new_message = items.get("Message", "NULL")
                if new_message not in msg_list:
                    log_my_msg(new_message)
                    msg_list.append(new_message)
            if time.time() > timeout:
                log_my_msg(f" critical: {timeout_minutes} min since waiting, {msg} did not received!")
                raise Exception(f" critical: {timeout_minutes} min since waiting, {msg} did not received!")


def self_healing_before_post(lom, session, msg):
    """Fn: Check IML messages"""
    log_my_msg(f"Fn: self_healing_before_post - message we are looking for is: {msg}")
    timeout = time.time() + 15 * 60
    force_reseted = False
    while True:
        if force_reseted:
            return force_reseted, "server was force resetted one time"
        time.sleep(10)
        message = get_iml_log(lom, session)
        msg_received = False
        for items in message:
            if msg in items["Message"]:
                log_my_msg(items["Message"])
                msg_received = True
                return msg_received, items["Message"]
            if time.time() > timeout:
                log_my_msg(" self-healing: 15 min since waiting for postbuild to start, trying reseting server")
                set_power_forcerestart(lom, session)
                force_reseted = True
                break


def countdown(string, time_in_sec):
    """Fn: countdown"""
    while time_in_sec:
        mins, secs = divmod(time_in_sec, 60)
        timer = "{} : {:02d}:{:02d}".format(string, mins, secs)
        logger.info(timer, end="\r")
        time.sleep(1)
        time_in_sec -= 1


def run_stk_iso(lom, session, generation, stk_url):
    """Fn: Run STK iso image for ESKM & RAID 1 configurations"""
    log_my_msg("Fn: run_stk_iso")
    log_my_msg("Cleaning the iml")
    stk_reboot = None
    clear_iml_log(lom, session)
    timeout = time.time() + 60 * 60
    log_my_msg(f"Setting timeout for {timeout}!")
    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
    log_my_msg(f"=====> STK stating at {start_time} <=====")
    fail_if_power_on(lom, session)
    log_my_msg(" - verifying and mounting stk iso")
    check_http_iso(stk_url)
    eject_virtual_media(lom, session, generation)
    mount_virtual_media(lom, session, generation, stk_url)
    set_power_on(lom, session)
    time.sleep(10)
    log_my_msg(" - waiting for FinishedPost")
    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        log_my_msg(f"  - current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break
    log_my_msg(" - will start checking stk status in iml in 180s")
    time.sleep(180)
    stkdone = False
    while True:
        time.sleep(10)
        message = get_iml_log(lom, session)
        log_my_msg("{:=<120}".format(""))
        for items in message:
            if "ZTP:STK" in items["Message"]:
                log_my_msg(items["Message"])
            if "ZTP:STK:REBOOT" in items["Message"]:
                set_power_off(lom, session)
                time.sleep(10)
                stk_reboot = True
                break
                # run_stk_iso(lom, session, generation, stk_url)
            if "ZTP:STK:SUCCESS" in items["Message"]:
                log_my_msg(items["Message"])
                stkdone = True
                break
            if "ZTP:STK:FAIL" in items["Message"]:
                log_my_msg(items["Message"])
                # check ns204 controller
                if "No storage controller found" in items["Message"]:
                    log_my_msg("No storage controller found in stk log, checking if its HPE NS204i-u Gen12 Boot Controller")
                    setup_NS204_controller(lom, session)
                    stkdone = True
                    break
                else:
                    log_my_msg("fail: stk log shows failure, login to console check iml for detail")
                    raise Exception()
        if stkdone is True:
            break
        if stk_reboot is True:
            break
        if time.time() > timeout:
            fail_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
            log_my_msg(f"=====> STK failed at {fail_time} <=====")
            log_my_msg(" 60 min since waiting, stk work should be completed")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
    if stk_reboot is True:
        stk_reboot = None
        clear_iml_log(lom, session)
        run_stk_iso(lom, session, generation, stk_url)
    log_my_msg("{:=<120}".format(""))
    stop_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
    log_my_msg(f"=====> STK finished at {stop_time} <=====")
    return stkdone


def run_spp_process(lom, lomuser, lompass, session, generation, spp_url):
    """Fn: Run SPP iso image for firmware update
    steps: check to see if tpm is visible in bios, if it is set to hidden
        - mount spp iso and power on the server
        - wait for post to complete and clear IML log
        - wait for 5 minutes and start checking IML log every 3 minutes
        - check for message Maintenance note: Starting F10 GUI
        - once virtual media is unmounted and post is finished, we are done
    """
    log_my_msg("Fn: run_spp_process")
    # Check if TpmVisibility is set correctly in BIOS
    if generation == "gen9":
        log_my_msg(" - Verifying TpmVisibility for Gen9")
        tpm_hidden_payload = {"TpmVisibility": "Hidden"}
        tpm_visible_payload = {"TpmVisibility": "Visible"}
    else:
        tpm_hidden_payload = {"Attributes": {"PlatformCertificate": "Disabled", "TpmVisibility": "Hidden"}}
        tpm_visible_payload = {"Attributes": {"PlatformCertificate": "Disabled", "TpmVisibility": "Visible"}}
    log_my_msg("Verifying TpmVisibility")
    bios_ep = "/redfish/v1/systems/1/bios/settings"
    server_bios = get_api_settings(lom, session, bios_ep)
    tpm_visibility = server_bios.get("TpmVisibility") or server_bios.get("Attributes", {}).get("TpmVisibility")
    log_my_msg(f"Current TpmVisibility setting: {tpm_visibility}")
    if tpm_visibility == "Hidden":
        log_my_msg(" pass: TpmVisibility is already set to Hidden.")
    else:
        log_my_msg(
            f" fail: Applying TpmVisibility to Hidden in BIOS so SPP can run unattended, payload = {tpm_hidden_payload}"
        )
        patch_api_hpe(lom, session, bios_ep, tpm_hidden_payload)
    timeout = time.time() + 6 * 3600  # 6 hours timeout
    logger.info(f"(*) Starting SPP Firmware update process at {time.strftime('%X %x %Z')}")
    eject_virtual_media(lom, session, generation)
    mount_virtual_media(lom, session, generation, spp_url)
    set_power_on(lom, session)
    time.sleep(10)
    clear_iml_log(lom, session)
    timeout_2hr = time.time() + 2 * 3600  # 2 hours timeout
    while (server_post := get_post_status(lom, session)) != "InPostDiscoveryComplete":
        if time.time() > timeout_2hr:
            log_my_msg("Critical: Timeout reached. 2 hours elapsed waiting for InPostDiscoveryComplete.")
            raise Exception("Critical: Timeout reached. 2 hours elapsed waiting for InPostDiscoveryComplete.")
        logger.info(f"  - Current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break
        if server_post == "Reset":
            if not check_virtual_media(lom, session):
                log_my_msg(" Alert: SPP ISO is no longer mounted during Reset state. Remounting SPP ISO.")
                time.sleep(3)
                mount_virtual_media(lom, session, generation, spp_url)
    logger.info(" - BMI will begin monitoring SPP status in IML every 3 minutes")
    if not check_iml_msg(lom, session, "Maintenance note: Starting F10 GUI")[0]:
        log_my_msg(" fail: SPP process did not start, login to console check console make sure iso is booted")
        raise Exception("SPP process failed to start - F10 GUI message not found in IML")
    else:
        log_my_msg(" pass: SPP process has started, waiting additional 5 minutes for inventory to complete")
        log_my_msg(
            f" - Applying TpmVisibility to Visible in BIOS so next reboot it will be visible to OS, payload = {tpm_visible_payload}"
        )
        patch_api_hpe(lom, session, bios_ep, tpm_visible_payload)
    # inventory can take from 5 to 15 minutes to complete
    time.sleep(180)
    server_post = False
    spp_mounted = True if check_virtual_media(lom, session) else False
    log_my_msg("we are now monitoring the SPP process, this can take up to 6 hours to complete")
    while spp_mounted or server_post:
        time.sleep(180)
        try:
            spp_mounted = check_virtual_media(lom, session)
            server_post = True if get_post_status(lom, session) == "FinishedPost" else False
            log_my_msg(f"SPP mounted: {spp_mounted} so update is running.")
        except Exception:
            log_my_msg(" Warning: Exception occurred while checking SPP & Post status.")
            try:
                delete_session(session)
            except Exception:
                log_my_msg(" - Warning: Failed to delete session. Proceeding with recreation.")
            log_my_msg(" - Recreating session and continuing monitoring.")
            session = create_requests_retry_session(lom, lomuser, lompass)
        elapsed_time = timeout - time.time()
        if elapsed_time <= 4 * 3600 and elapsed_time > 2 * 3600:
            log_my_msg(" - 2-hour mark reached, continuing to monitor SPP process.")
        elif elapsed_time <= 2 * 3600 and elapsed_time > 0:
            log_my_msg(" - 4-hour mark reached, continuing to monitor SPP process.")
        elif elapsed_time <= 0:
            log_my_msg("Critical: Timeout reached. 6 hours elapsed, SPP update process should have completed.")
            raise Exception("Critical: Timeout reached. 6 hours elapsed, SPP update process should have completed.")
    log_my_msg("All IML log messages:")
    all_iml_logs = get_iml_log(lom, session)
    for log_entry in all_iml_logs:
        log_my_msg(log_entry.get("Message", "No message found"))
    logger.info(f"(*) SPP Firmware update process completed at {time.strftime('%X %x %Z')}")
    # Wait for the server to reboot and complete POST
    log_my_msg("Waiting for server to reboot and complete POST after SPP process.")
    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        log_my_msg(f"  - current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break
    log_my_msg("Server reboot and POST completed successfully.")
    return True


def check_secureboot(lom, session):
    """Fn: check secureboot is enabled or not"""
    log_my_msg("Fn: check_secureboot")
    url = "/redfish/v1/systems/1/SecureBoot/"
    resp = session.get(f"https://{lom}{url}")
    data = resp.json()
    if resp.ok:
        if data["SecureBootEnable"] is True:
            log_my_msg(f"secureBoot is enabled, {data}")
        else:
            log_my_msg(f"secureBoot is not enabled, {data}")
    return data["SecureBootEnable"]


def set_secureboot(lom, session, set_bool):
    """Fn: set secureboot to true or false"""
    log_my_msg("Fn: set_secureboot")
    payload = {"SecureBootEnable": set_bool}
    url = "/redfish/v1/systems/1/SecureBoot/"
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(f"pass: secureBoot {set_bool}, server reboot required.")
    return set_bool


def apply_secureboot(lom, session, set_bool):
    """Fn: Apply secureboot"""
    log_my_msg(f"Fn: Apply SecureBootEnable: {set_bool} setting with required reboot")
    payload = {"SecureBootEnable": set_bool}
    url = "/redfish/v1/systems/1/SecureBoot/"
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(f"pass: secureBoot {set_bool}, resetting server.")
    time.sleep(10)
    set_power_off(lom, session)
    time.sleep(10)
    set_power_on(lom, session)
    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        log_my_msg(f"  - current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break
    new_secureboot_setting = check_secureboot(lom, session)
    if new_secureboot_setting == set_bool:
        log_my_msg(f"pass: secureBoot {set_bool} is set.")
    else:
        log_my_msg(f" fail: secureBoot {set_bool}, failed to set")
        raise Exception()


def reset_api(lom, session, generation):
    """FN: Reset redfish api"""
    log_my_msg("Fn: reset_api")
    url = None
    resp = None
    # if generation == "gen10":
    if "gen1" in generation:
        url = f"https://{lom}/redfish/v1/Managers/1/Actions/Oem/Hpe/HpeiLO.ClearRestApiState/"
        resp = session.post(url)
    elif generation == "gen9":
        url = f"https://{lom}/redfish/v1/Managers/1"
        payload = {"Action": "ClearRestApiState", "Target": "/Oem/Hp"}
        resp = session.post(url, data=json.dumps(payload))
    else:
        log_my_msg(f"  error: {generation} not supported")
        raise Exception()
    if resp.ok:
        log_my_msg(f"pass: API reset succeeded, response code = {resp.status_code} \n {resp.text}")
    else:
        log_my_msg(f"  error: url={url} response={resp.status_code}")
        raise Exception()
    return resp.ok


def get_all_gen9_firmware(lom, session):
    """Fn: Get all firmware versions"""
    url = "/redfish/v1/Systems/1/FirmwareInventory/"
    resp = session.get(f"https://{lom}{url}")
    if resp.ok:
        data = resp.json()
        fw_dict = {}
        for i in data["Current"]:
            for x in data["Current"][i]:
                if x is not None:
                    fw_dict[x["Name"]] = x["VersionString"]
        return fw_dict
    else:
        log_my_msg(f"  error: url={url} response={resp.status_code}")
        raise Exception()


def get_all_gen10_firmware(lom, session):
    """Fn: Get all firmware versions"""
    url = "/redfish/v1/UpdateService/FirmwareInventory/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()

    fw_dict = {}  # Initialize the dictionary

    if "Members" in data:
        list_1 = [item["@odata.id"] for item in data["Members"]]

        for x in list_1:
            resp = session.get(f"https://{lom}{x}")
            if_resp_not_ok(resp)
            data = resp.json()
            key = f'{data["Description"]} {data["Name"]}'
            value = data["Version"]
            fw_dict[key] = value  # Update the dictionary

    return fw_dict


def get_ctlr_ep_list(lom, session, generation):
    """Fn: get_ctlr_ep_list Get HPE disk ctlr ep list"""
    ctrl_ep_list = []
    if generation == "gen11":
        return ctrl_ep_list
    url = "/redfish/v1/Systems/1/SmartStorage/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    if "gen1" in generation:
        data = resp.json().get("Links", {})
    else:
        data = resp.json().get("links", {})
    if len(data) > 0:
        for val in data.values():
            if "gen1" in generation:
                ctrl_ep_list.append(val["@odata.id"])
            else:
                ctrl_ep_list.append(val["href"])
    return ctrl_ep_list


def get_ctrl_slot_ep(lom, session, generation):
    """Fn: get_ctrl_slot_ep Get HPE disk ctlr slot and ep list"""
    ctrl_slot_ep_list = []
    ctlr_ep = get_ctlr_ep_list(lom, session, generation)
    if len(ctlr_ep) > 0:
        for url in ctlr_ep:
            resp = session.get(f"https://{lom}{url}")
            if_resp_not_ok(resp)
            mcount = resp.json().get("Members@odata.count", "0")
            if int(mcount) > 0 and "Array" in resp.json()["Description"]:
                for x in resp.json()["Members"]:
                    ctrl_slot = x["@odata.id"].split("/")[-2]
                    ctrl_slot_ep_list.append((ctrl_slot, x["@odata.id"]))
        return ctrl_slot_ep_list
    else:
        return []


def get_disk_ep_list(lom, session, generation):
    """Fn: get_ctrl_slot_ep Get HPE disk ctlr slot and ep list"""
    pd_ep = ""
    ep_list = get_ctrl_slot_ep(lom, session, generation)
    if len(ep_list) > 0:
        for index, tuple in enumerate(ep_list):
            tuple[0]
            ep = tuple[1]
            resp = session.get(f"https://{lom}{ep}")
            if_resp_not_ok(resp)
            if "gen1" in generation:
                pd_ep = resp.json()["Links"]["PhysicalDrives"]["@odata.id"]
            else:
                pd_ep = resp.json()["links"]["PhysicalDrives"]["href"]
        return pd_ep
    else:
        return []


def get_pd_ep_list(lom, session, generation):
    """Fn: get_ctrl_slot_ep Get HPE physical disk list"""
    my_list = []
    ep = get_disk_ep_list(lom, session, generation)
    if len(ep) > 0:
        resp = session.get(f"https://{lom}{ep}")
        if_resp_not_ok(resp)
        disk_ep_list = resp.json()["Members"]
        for index in range(len(disk_ep_list)):
            for key in disk_ep_list[index]:
                my_list.append(disk_ep_list[index][key])
        return my_list
    else:
        return []


def get_disk_info(lom, session, generation):
    """Fn: get_disk_info Get HPE physical disk information"""
    tmp_disk_info_dict = {}
    disk_list = []
    ep_list = get_pd_ep_list(lom, session, generation)
    if len(ep_list) > 0:
        for ep in ep_list:
            resp = session.get(f"https://{lom}{ep}")
            if_resp_not_ok(resp)
            disk_keys = ["Id", "CapacityGB", "InterfaceType", "Location", "MediaType"]
            for x in disk_keys:
                i = {x: resp.json()[x]}
                tmp_disk_info_dict.update(i)
            disk_list.append(copy.deepcopy(tmp_disk_info_dict))
        return disk_list
    else:
        return []


def get_disk_info_list(lom, session, generation):
    """fn: get_disk_info_list root disk list is [0]"""
    """fn: get_disk_info_list non disk list is [1]"""
    log_my_msg("Fn: get_disk_info_list")
    root_disk_list = []
    disk_list = []
    disks = get_disk_info(lom, session, generation)
    if len(disks) > 0:
        for i in disks:
            if int(i["CapacityGB"]) < 1000:
                root_disk_list.append(i)
            else:
                disk_list.append(i)
        if len(root_disk_list) > 0:
            root_disk_header = root_disk_list[0].keys()
            root_disk_rows = [x.values() for x in root_disk_list]
            log_my_msg("get_disk_info_list root disks:")
            log_my_msg(tabulate.tabulate(root_disk_rows, root_disk_header))
        if len(disk_list) > 0:
            disk_header = disk_list[0].keys()
            disk_rows = [x.values() for x in disk_list]
            log_my_msg("get_disk_info_list app disks:")
            log_my_msg(tabulate.tabulate(disk_rows, disk_header))
        return root_disk_list, disk_list
    return []


def get_storage_info(lom, session):
    """Fn: get_controller_info Get HPE disk controller information"""
    log_my_msg("Fn: get_controller_info")
    controller_info_list = []
    url = "/redfish/v1/Systems/1/Storage/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()

    if "Members" in data:
        for member in data["Members"]:
            member_url = member["@odata.id"]
            resp = session.get(f"https://{lom}{member_url}")
            if_resp_not_ok(resp)
            member_data = resp.json()
            controller_name = member_data.get("Name", "Unknown")
            controller_info_list.append({"Name": controller_name, "Endpoint": member_url})
            log_my_msg(f"Controller: {controller_name}")
            # Get Drives information
            if "Drives" in member_data:
                drives_info = []
                for drive in member_data["Drives"]:
                    drive_url = drive["@odata.id"]
                    drive_resp = session.get(f"https://{lom}{drive_url}")
                    if_resp_not_ok(drive_resp)
                    drive_data = drive_resp.json()

                    drive_info = {
                        "Name": drive_data.get("Name", "Unknown"),
                        "MediaType": drive_data.get("MediaType", "Unknown"),
                        "CapacityBytes": drive_data.get("CapacityBytes", 0),
                    }
                    drives_info.append(drive_info)
                    log_my_msg(
                        f"  Drive: {drive_info['Name']}, Type: {drive_info['MediaType']}, Capacity: {drive_info['CapacityBytes']} bytes"
                    )
                controller_info_list[-1]["Drives"] = drives_info
    log_my_msg(f"Controller info list: {json.dumps(controller_info_list, indent=2)}")
    return controller_info_list


def setup_NS204_controller(lom, session):
    """Fn: setup_for_NS204_controller Setup for NS204 controller
        - check firmware version is 1.2.14.1022 or higher
        GET /redfish/v1/Systems/1/Storage/DE00C000/Controller/0
        "FirmwareVersion": "1.2.14.1022",
        - check encryption is enabled 
        GET /redfish/v1/Systems/1/Storage/DE00C000/Volumes/1
        "Encrypted": true,
            if encryption is not enabled, enable it by
            PATCH /redfish/v1/Systems/1/Storage/DE00C000
                {"EncryptionMode": "UseExternalKey"}
        - check encryption mode
        GET /redfish/v1/Systems/1/Storage/DE00C000/
        "EncryptionMode": "UseExternalKey"
        enable encryption if not enabled by
        PATCH /redfish/v1/Systems/1/Storage/DE00C000
        {"EncryptionMode": "UseExternalKey"}
        - reset to default settings 
        POST  /redfish/v1/Systems/1/Storage/DE00C000/Actions/Storage.ResetToDefaults
        {"ResetType": "ResetAll”}
    """
    log_my_msg("Fn: setup_for_NS204_controller")
    # Get storage info to find NS204 controller
    storage_info = get_storage_info(lom, session)
    
    ns204_controller = None
    for controller in storage_info:
        if "NS204" in controller.get("Name", ""):
            ns204_controller = controller
            break
    
    if not ns204_controller:
        log_my_msg("No NS204 controller found")
        return False
    
    controller_endpoint = ns204_controller["Endpoint"]    
    log_my_msg(f"Found {ns204_controller} controller at: {controller_endpoint}")

    # Check firmware version
    controller_url = f"{controller_endpoint}Controllers/0"
    resp = session.get(f"https://{lom}{controller_url}")
    if_resp_not_ok(resp)
    controller_details = resp.json()

    firmware_version = controller_details.get("FirmwareVersion", "Unknown")
    log_my_msg(f"NS204 controller firmware version: {firmware_version}")

    # Check if firmware is 1.2.14.1022 or higher
    required_version = "1.2.14.1022"
    if firmware_version != "Unknown":
        current_parts = [int(x) for x in firmware_version.split(".")]
        required_parts = [int(x) for x in required_version.split(".")]
        
        if current_parts < required_parts:
            log_my_msg(f"Warning: Firmware version {firmware_version} is below required version {required_version}")
            update_ns204_fw(lom, session)
        else:
            log_my_msg(f"Firmware version {firmware_version} meets requirements")            
            # Reset to default settings
            log_my_msg("Resetting NS204 controller to default settings")
            reset_url = f"{controller_endpoint}Actions/Storage.ResetToDefaults"
            payload = {"ResetType": "ResetAll"}
            resp = session.post(f"https://{lom}{reset_url}", data=json.dumps(payload))
            if_resp_not_ok(resp)
            log_my_msg(resp.text)
            log_my_msg("Successfully reset NS204 controller to default settings")

    power_cycle_server(lom, session)
    
    resp = session.get(f"https://{lom}{controller_endpoint}")
    if_resp_not_ok(resp)
    controller_data = resp.json()
    
    # Check encryption mode
    encryption_mode = controller_data.get("EncryptionMode", "Unknown")
    log_my_msg(f"Current encryption mode: {encryption_mode}")
    
    if encryption_mode != "UseExternalKey":
        log_my_msg("Enabling UseExternalKey encryption mode")
        payload = {"EncryptionMode": "UseExternalKey"}
        resp = session.patch(f"https://{lom}{controller_endpoint}", data=json.dumps(payload))
        if_resp_not_ok(resp)
        log_my_msg("Successfully enabled UseExternalKey encryption mode")
    else:
        log_my_msg("Encryption mode already set to UseExternalKey")
   
    
    log_my_msg("Server reset completed")
    # Check if volumes are encrypted
    if "Volumes" in controller_data:
        volumes_url = controller_data["Volumes"]["@odata.id"]
        resp = session.get(f"https://{lom}{volumes_url}")
        if_resp_not_ok(resp)
        volumes_data = resp.json()
        
        if "Members" in volumes_data and len(volumes_data["Members"]) > 0:
            volume_url = volumes_data["Members"][0]["@odata.id"]
            resp = session.get(f"https://{lom}{volume_url}")
            if_resp_not_ok(resp)
            volume_data = resp.json()
            
            is_encrypted = volume_data.get("Encrypted", False)
            log_my_msg(f"Volume encryption status: {is_encrypted}")
    


    return True


def boot_into_bios_setup(lom, session):
    """Fn: Boot into BIOS setup on next reboot"""
    log_my_msg("Fn: boot_into_bios_setup")
    url = "/redfish/v1/Systems/1/"
    payload = {
        "Boot": {
            "BootSourceOverrideEnabled": "Once",
            "BootSourceOverrideTarget": "BiosSetup"
        }
    }
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("pass: Server configured to boot into BIOS setup on next reboot")
    return True


def update_ns204_fw(lom, session):
    """Fn: update_ns204_fw"""
    log_my_msg("Fn: update_ns204_fw")
    url = "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate/"
    payload = {"ImageURI": "http://bmi-prod.example.com/pub/spp/ns204/HPE_NS204i_Gen10p_Gen11_1.2.14.1022_A.fwpkg"}
    log_my_msg(f"URL: {url}, Payload: {payload}")
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    task_monitor = resp.json().get("TaskMonitor")
    log_my_msg(f"TaskMonitor: {task_monitor}")
    # Extract task number from TaskMonitor URL
    task_number = task_monitor.split('/')[-2] if task_monitor else None
    log_my_msg(f"Task number: {task_number}")
    # Wait until TaskState is Completed
    max_wait_time = 600  # 10 minutes timeout
    start_time = time.time()
    # Verify task exists before monitoring
    try:
        resp = session.get(f"https://{lom}/redfish/v1/TaskService/Tasks/{task_number}")
        if_resp_not_ok(resp)
        log_my_msg(f"Task {task_number} found and monitoring started")
    except Exception as e:
        log_my_msg(f"Failed to access task {task_number}: {str(e)}")
        raise Exception(f"Task {task_number} does not exist or is not accessible")
    
    while True:
        resp = session.get(f"https://{lom}/redfish/v1/TaskService/Tasks/{task_number}")
        if_resp_not_ok(resp)
        task_data = resp.json()
        task_state = task_data.get("TaskState", "Unknown")
        
        log_my_msg(f"Current TaskState: {task_state}")
        
        if task_state == "Completed":
            log_my_msg("Firmware update completed successfully")
            break
        elif task_state in ["Exception", "Killed", "Cancelled"]:
            log_my_msg(f"Firmware update failed with state: {task_state}")
            raise Exception(f"Firmware update failed: {task_state}")
        elif time.time() - start_time > max_wait_time:
            log_my_msg("Firmware update timed out")
            raise Exception("Firmware update timed out after 10 minutes")
        time.sleep(10)  # Wait 10 seconds before checking again
    return task_monitor


def apply_tpm_visibility(lom, session, generation):
    """Fn: Apply TPM visibility setting with required reboot"""
    log_my_msg("Fn: apply_tpm_visibility")
    if generation == "gen9":
        bios_ep = "/redfish/v1/systems/1/bios/settings"
        payload = {"TpmVisibility": "Visible"}
    else:
        bios_ep = "/redfish/v1/systems/1/bios/settings"
        payload = {"Attributes": {"TpmVisibility": "Visible"}}
    
    log_my_msg("Applying TpmVisibility to Visible in BIOS")
    patch_api_hpe(lom, session, bios_ep, payload)
    log_my_msg("TPM visibility set to Visible, resetting server.")
    time.sleep(10)
    set_power_off(lom, session)
    time.sleep(10)
    set_power_on(lom, session)
    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        log_my_msg(f"  - current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            break
    log_my_msg("Server reboot and POST completed successfully after TPM visibility change.")
    log_my_msg("Verifying TpmVisibility")
    bios_ep = "/redfish/v1/systems/1/bios/settings"
    server_bios = get_api_settings(lom, session, bios_ep)
    tpm_visibility = server_bios.get("TpmVisibility") or server_bios.get("Attributes", {}).get("TpmVisibility")
    log_my_msg(f"Current TpmVisibility setting: {tpm_visibility}")
    if tpm_visibility != "Visible":
        log_my_msg(" fail: TpmVisibility is not set to Visible.")
        raise Exception(" fail: TpmVisibility is not set to Visible.")
    log_my_msg(" pass: TpmVisibility is set to Visible.")
    return {"TpmVisibility": tpm_visibility,
            "applied": True
            }
