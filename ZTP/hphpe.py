# -*- coding: utf-8 -*-

"""
hp_hpe.py -- hpe module to interact with HPE(GEN10) and HP(GEN9) hardware
"""

import copy
import json
import logging
import time

import tabulate

from ._common import if_resp_not_ok, log_my_msg
from ._healthcheck import check_http_iso
from ._session import create_requests_retry_no_token_auth, create_requests_retry_session
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
        log_my_msg(f"{hpe_hardware_model}")
        self.model = hpe_hardware_model.split()[1]
        self.generation = hpe_hardware_model.split()[2]
        self.payload = payload
        if self.generation == "gen10":
            self.standards_url = (
                "http://bmi-prod.example.com/pub/tools/build_files/gen10_full.json"
            )
        if self.generation == "gen11":
            self.standards_url = (
                "http://bmi-prod.example.com/pub/tools/build_files/gen11_full.json"
            )    
        if self.generation == "gen9":
            self.standards_url = (
                "http://bmi-prod.example.com/pub/tools/build_files/gen9_full.json"
            )

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
        """Method: run spp for raid and eskm enablement"""
        log_my_msg("(HpHpeServer) run_spp")
        gen = self.generation
        if gen == "gen9":
            before_all_ilo_fw = get_all_gen9_firmware(self.lom, self.sessobj)
            spp_url_path = "http://sat-cap-elr-a.example.com/pub/hpe/spp/gen9_spp_current.iso"
        else:
            before_all_ilo_fw = get_all_gen10_firmware(self.lom, self.sessobj)
            spp_url_path = "http://sat-cap-elr-a.example.com/pub/hpe/spp/gen10_spp_current.iso"
        sppdict = {"spp_url": spp_url_path}
        run_spp = run_spp_iso(
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
            del self.sessobj
            self.sessobj = create_requests_retry_session(self.lom, self.lomuser, self.lompass)
            if gen == "gen9":
                after_all_ilo_fw = get_all_gen9_firmware(self.lom, self.sessobj)
            else:
                after_all_ilo_fw = get_all_gen10_firmware(self.lom, self.sessobj)
            return compare_two_dict(before_all_ilo_fw, after_all_ilo_fw)

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

    def rhel_post_provisioning(self):
        """Method: RHEL post provising
        Ref: https://github.example.com/BareMetal/Standards
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
        """ "Method: get all iml log from ilo"""
        return get_iml_log(self.lom, self.sessobj)


###
### Helper Functions
###
def get_stk_iso():
    """Fn: get_stk_iso"""
    log_my_msg("Fn: get_stk_iso")
    # host_ip = socket.gethostbyname(socket.gethostname())
    # source_iso = "hpe-stk-custom.iso"
    source_iso = "hpe-stk-custom-mr_bugfix.iso"
    # url = f"https://203.0.113.57/artifactory/company-docker/company-component/stk/{source_iso}"
    # stk_url = f"http://203.0.113.95/pub/{source_iso}"
    stk_url = f"https://repo1.example.com/artifactory/company-docker/company-component/stk/{source_iso}"
    # host_ip = socket.gethostbyname(socket.gethostname())
    # url = f"http://{host_ip}{PUBDIR}/{source_iso}"
    # if os.path.isdir(PUBDIR) is False:
    #     # raise Exception(f"fail: {PUBDIR} doesn't exist on the server , it is required!")
    #     log_my_msg(f" warning: {PUBDIR} does not exsist, using artifactory!")
    #     return url
    # os.chdir(PUBDIR)
    # if os.path.exists(f"{PUBDIR}/{source_iso}") is True:
    #     log_my_msg(f"pass: {PUBDIR}/{source_iso} exists... Nothing to do!")
    # else:
    #     log_my_msg(f" {source_iso} iso image does not exist! \n downloading it from {url}")
    #     try:
    #         log_my_msg(url)
    #         wget.download(url)
    #     except Exception as error:
    #         log_my_msg(f" fail: download {source_iso} failed with \n {error}")
    #         raise
    # # host_ip = socket.gethostbyname(socket.gethostname())
    # stk_url = f"http://{host_ip}{PUBDIR}/{source_iso}"
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
        hpe_bios_standards = resp.json()["#DL325_Bios.v1_0_4.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    if model == "dl560":
        hpe_bios_standards = resp.json()["#dl560_Bios.v1_0_0.Bios"]["/redfish/v1/systems/1/bios/settings/"]
    ## CHANGE TO UEFI FOR ZTP
    hpe_bios_standards["Attributes"]["BootMode"] = "Uefi"
    return hpe_bios_standards


def check_bios(lom, session, standard_url, model, payload):
    """Fn: Check/compate bios setting on server with standard"""
    log_my_msg("Fn: check_bios")
    log_my_msg(f"model: {model}")
    log_my_msg(f"standard: {standard_url}")
    standard_bios = get_bios_standard_data(standard_url, model)["Attributes"]
    server_bios = get_api_settings(lom, session, "/redfish/v1/systems/1/bios")
    try:
        server_bios = server_bios["Attributes"]
    except KeyError:
        pass
    if len(payload) > 0:
        my_dict = {}
        for key in payload:
            name = server_bios.get(key, None)
            if name:
                my_dict.update({key: name})
        return my_dict
    else:
        return compare_two_dict(server_bios, standard_bios)


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
    #if generation == "gen10":
    if "gen1" in generation:
        if len(payload) > 0:
            bios_payload = payload
        #post_api_hpe(lom, session, url, bios_payload)
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
    log_my_msg("Fn: get_api_settings")
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
    """Fn: Compare two dictionary"""
    settings_check = "pass"
    log_my_msg("{:=<120}".format(""))
    log_my_msg("{:<40}{:<35}{:<30}".format("Attributes", "Current Value", "Expected Value"))
    log_my_msg("{:=<120}".format(""))
    for key in dict1.keys() & dict2.keys():
        if dict1[key] == dict2[key]:
            log_my_msg("{:<40}{:<35}{:<30}".format(str(key), str(dict1[key]), str(dict2[key])))
        else:
            log_my_msg("{:<40}{:<35}{:<30}{:<8}".format(str(key), str(dict1[key]), str(dict2[key]), "XXX"))
            settings_check = "fail"
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


def check_virtual_media(lom, session, generation):
    """Fn: Check virtual media"""
    log_my_msg("Fn: check_virtual_media")
    url = f"https://{lom}/redfish/v1/Managers/1/VirtualMedia/2/"
    resp = session.get(url)
    data = resp.json()
    if_resp_not_ok(resp)
    return data["Image"]


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
    log_my_msg("pass: clear iml log")


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


def check_iml_msg(lom, session, msg):
    """Fn: Check IML messages"""
    log_my_msg(f"Fn: check_iml_msg - message we are looking for is: {msg}")
    timeout = time.time() + 30 * 60
    while True:
        time.sleep(10)
        message = get_iml_log(lom, session)
        msg_received = False
        for items in message:
            if msg in items.get("Message", "NULL"):
                log_my_msg(items["Message"])
                msg_received = True
                return msg_received, items["Message"]
            if time.time() > timeout:
                log_my_msg(f" critical: 30 min since waiting, {msg} did not received!")
                raise Exception(f" critical: 30 min since waiting, {msg} did not received!")


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
                log_my_msg(f" self-healing: 15 min since waiting for postbuild to start, trying reseting server")
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
    timeout = time.time() + 20 * 60
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
                log_my_msg("fail: stk log shows failure, login to console check iml for detail")
                raise Exception()
        if stkdone is True:
            break
        if stk_reboot is True:
            break
        if time.time() > timeout:
            fail_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
            log_my_msg(f"=====> STK failed at {fail_time} <=====")
            log_my_msg(" 20 min since waiting, stk work should be completed")
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


def run_spp_iso(lom, lomuser, lompass, session, generation, spp_url):
    timeout = time.time() + 20 * 360
    currenttime = time.strftime("%X %x %Z")
    logger.info(f"(*) Starting SPP procedure at {currenttime}")
    set_power_off(lom, session)
    logger.info(" - INFO: Checking and mounting SPP ISO")
    check_http_iso(spp_url)
    eject_virtual_media(lom, session, generation)
    mount_virtual_media(lom, session, generation, spp_url)
    set_power_on(lom, session)
    time.sleep(10)
    server_post = ""
    while server_post != "InPostDiscoveryComplete":
        server_post = get_post_status(lom, session)
        logger.info(f"  - Current state {server_post}")
        time.sleep(10)
        if server_post == "FinishedPost":
            server_post = True
            break
    logger.info(" - Will start checking spp status in 420s")
    time.sleep(420)
    spp_mounted = True if check_virtual_media(lom, session, generation) else False
    while spp_mounted or server_post:
        time.sleep(30)
        try:
            spp_mounted = True if check_virtual_media(lom, session, generation) else False
            server_post = True if get_post_status(lom, session) == "FinishedPost" else False
            log_my_msg(server_post, spp_mounted)
            logger.info(" - Assuming SPP update is running!")
        except:
            del session
            session = create_requests_retry_session(lom, lomuser, lompass)
            # pass
        if time.time() > timeout:
            logger.critical(" - WARNING: Its been 40 min since waiting, SPP work should be completed")
            logger.critical(" - FAIL: NOT SURE whats going on!!! CALL SUPPORT !!!")
            raise Exception()
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
    #if generation == "gen10":
    if "gen1" in generation: 
        url = f"https://{lom}/redfish/v1/Managers/1/Actions/Oem/Hpe/HpeiLO.ClearRestApiState/"
        resp = session.post(
            url,
            verify=False,
        )
    elif generation == "gen9":
        url = f"https://{lom}/redfish/v1/Managers/1"
        payload = {"Action": "ClearRestApiState", "Target": "/Oem/Hp"}
        resp = session.post(
            url,
            data=json.dumps(payload),
            verify=False,
        )
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
    resp = session.get(f"https://{lom}{url}", verify=False)
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
    resp = session.get(f"https://{lom}{url}", verify=False)
    if_resp_not_ok(resp)
    data = resp.json()
    list_1 = list()
    fw_dict = {}
    for items in data["Members"]:
        list_1.append(items["@odata.id"])
    if len(list_1) > 0:
        for x in list_1:
            resp = session.get(f"https://{lom}{x}", verify=False)
            if_resp_not_ok(resp)
            data = resp.json()
            key = f'{data["Description"]} {data["Name"]}'
            value = data["Version"]
            fw_dict.update({key: value})
    return fw_dict


def get_ctlr_ep_list(lom, session, generation):
    """Fn: get_ctlr_ep_list Get HPE disk ctlr ep list"""
    ctrl_ep_list = []
    if generation == "gen11":
        return ctrl_ep_list
    url = f"/redfish/v1/Systems/1/SmartStorage/"
    resp = session.get(f"https://{lom}{url}", verify=False)
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
            resp = session.get(f"https://{lom}{url}", verify=False)
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
            resp = session.get(f"https://{lom}{ep}", verify=False)
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
        resp = session.get(f"https://{lom}{ep}", verify=False)
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
            resp = session.get(f"https://{lom}{ep}", verify=False)
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
