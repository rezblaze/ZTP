# -*- coding: utf-8 -*-

"""ilo module for gen9 & gen10 ilo configurations"""

import json
import logging
import time

from ._common import if_resp_not_ok, log_my_msg
from ._session import create_requests_retry_no_token_auth, create_requests_retry_session
from .exception import HpGen9ilo4EskmBug
from .secrets import admin_lom_creds, get_lom_creds

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)

no_token_sessobj = create_requests_retry_no_token_auth()

###
### HPE ilo class
###


class HpeiloActions:
    """Class: HPE ilo action"""

    def __init__(
        self,
        networkdata,
        lomuser="",
        lompass="",
    ):
        """HpeiloActions

        Args:
            networkdata (dict): networkdata from NetworkData
            lomuser (str): lights out management user
            lompass (str): lights out management passwd
            standard_url (str, optional): standard url.
        """
        log_my_msg("*** ZTP ilo module ***")
        self.networkdata = networkdata
        self.hardware = networkdata["HARDWARE"]
        self.generation = networkdata["GENERATION"].lower()
        self.lom = networkdata["LOMIP"]
        if "hp" not in self.hardware:
            raise ValueError(f"Invalid hardware type: {self.hardware}")
        if self.generation == "gen10":
            self.standard_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json/gen10_full.json"
            self.firmware_url = "https://capsule-elr-lb-c-prod.example.com/pub/hpe/spp/gen10/packages/ilo5_310.fwpkg"
            self.standard_firmware_version = 3.10
        if self.generation == "gen11":
            self.standard_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json/gen11_full.json"
            self.firmware_url = "https://capsule-elr-lb-c-prod.example.com/pub/hpe/spp/gen11/packages/ilo6_166.fwpkg"
            self.standard_firmware_version = 1.66
        if self.hardware == "hp":
            self.generation = "gen9"
            self.standard_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json/gen9_full.json"
            self.firmware_url = "http://203.0.113.107/firmware/g9/ilo4/ilo4_282.bin"
            self.standard_firmware_version = 2.82
        self.standard_data = get_standard_hpe_json(networkdata, self.standard_url)
        if lomuser == "" and lompass == "":
            lomcred = admin_lom_creds(self.lom, self.generation, vendor="hp")
            self.lomuser = lomcred[0]
            self.lompass = lomcred[1]
        else:
            self.lomuser = lomuser
            self.lompass = lompass
        self.sessobj = create_requests_retry_session(self.lom, lomuser, lompass)
        self.ilo_endpoints = self.standard_data[0]
        self.ilo_standard = self.standard_data[1]
        self.check_n_fix_user_previleges(self.lomuser)

    def check_ilo_settings(self):
        """Method: Check ilo setting agaist standards"""
        log_my_msg("(HpeiloActions) check_ilo_settings")
        log_my_msg("checking license and updating if needed")
        lic_type = check_ilo_license_type(self.lom, self.sessobj)
        if lic_type == "Unlicensed":
            log_my_msg("unlicensed ilo applying license")
            item = "#HpeiLOLicense"
            post_to_api(
                self.lom,
                self.sessobj,
                self.ilo_endpoints[item],
                self.ilo_standard[item],
            )
            log_my_msg(f"license type now => {check_ilo_license_type(self.lom, self.sessobj)}")
        elif lic_type == "Perpetual":
            log_my_msg(f"pass: license type => {lic_type}")
        else:
            log_my_msg(f"unknown license type => {lic_type}")

        iloresult = {}
        for key, val in self.ilo_endpoints.items():
            log_my_msg(f"ilo stanza: {key}")
            if "Bios" in key:
                continue
            if "ManagerAccount" in key:
                continue
            if "SecureBoot" in key:
                log_my_msg("*NOTE* skipping secureboot stanza this is by design!")
                continue
            server_data = get_from_api(self.lom, self.sessobj, val)
            standard_data = self.ilo_standard[key]
            # result = compare_two_dict(server_data, standard_data)
            result = compare_two_dict(standard_data, server_data)
            iloresult.update({key.split("#")[1]: result})
        ilocheck = {}
        if "fail" in iloresult.values():
            ilocheck.update({"ilo_check": "fail", "ilo_check_detail": iloresult})
            # log_my_msg({"ilo_check": "fail", "ilo_check_detail": iloresult})
        else:
            ilocheck.update({"ilo_check": "pass", "ilo_check_detail": iloresult})
            test_ad = ("null", "null")
            if "hp" in self.hardware:
                test_ad = chk_ad(self.lom, self.sessobj, self.hardware)
                if test_ad[0] == "Fail":
                    log_my_msg(" - FAIL: Active Directory test failed")
                    log_my_msg(f"{test_ad[1]}")
                else:
                    log_my_msg(f" - PASS: Active Directory test passed")
                    log_my_msg(f"{test_ad[1]}")
        return ilocheck

    def apply_standard_ilo_setting(
        self,
        AccountService=True,
        EthernetInterface=True,
        HpeESKM=True,
        HpeiLODateTime=True,
        HpeiLOLicense=True,
        HpeiLOSSO=True,
        Manager=True,
        ManagerNetworkProtocol=True,
    ):
        """Method: Apply standard ilo setting based on HPE standard
        {
            "#AccountService": "/redfish/v1/AccountService/",
            "#Bios": "/redfish/v1/systems/1/bios/settings/",
            "#EthernetInterface": "/redfish/v1/Managers/1/EthernetInterfaces/1/",
            "#HpeESKM": "/redfish/v1/Managers/1/SecurityService/ESKM/",
            "#HpeiLODateTime": "/redfish/v1/Managers/1/DateTime/",
            "#HpeiLOLicense": "/redfish/v1/Managers/1/LicenseService/",
            "#HpeiLOSSO": "/redfish/v1/Managers/1/SecurityService/SSO/",
            "#Manager": "/redfish/v1/Managers/1/",
            "#ManagerAccount": "/redfish/v1/AccountService/Accounts/",
            "#ManagerNetworkProtocol": "/redfish/v1/Managers/1/NetworkProtocol/"
        }

        helpers_bios.post_api_hpe(LOM, SESSION, '/redfish/v1/Managers/1/LicenseService/', ilo_license_payload)
        helpers_bios.post_api_hpe(LOM, SESSION, '/redfish/v1/AccountService/Accounts', ilo_account_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/AccountService/', ilo_ad_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/Managers/1/SecurityService/SSO/', ilo_sso_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/Managers/1/', ilo_manager_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/Managers/1/NetworkProtocol/', ilo_networkprotocol_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/Managers/1/EthernetInterfaces/1/', ilo_dns_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/Managers/1/SecurityService/ESKM/', ilo_eskm_payload)
        helpers_bios.patch_api_hpe(LOM, SESSION, '/redfish/v1/managers/1/datetime', ilo_sntp_payload)
        """
        log_my_msg("(HpeiloActions) apply_standard_ilo_setting")

        item = "#AccountService"
        if self.hardware == "hpe":
            if AccountService:
                log_my_msg(f" - {item} applying")
                patch_to_api(
                    self.lom,
                    self.sessobj,
                    self.ilo_endpoints[item],
                    self.ilo_standard[item],
                )
            else:
                log_my_msg(f" - {item} skipping")

        item = "#EthernetInterface"
        if EthernetInterface:
            log_my_msg(f" - {item} applying")
            patch_to_api(
                self.lom,
                self.sessobj,
                self.ilo_endpoints[item],
                self.ilo_standard[item],
            )
        else:
            log_my_msg(f" - {item} skipping")

        item = "#HpeESKM"
        if HpeESKM:
            log_my_msg(f" - {item} applying")
            try:
                patch_to_api(
                    self.lom,
                    self.sessobj,
                    self.ilo_endpoints[item],
                    self.ilo_standard[item],
                )
            except Exception:
                if self.hardware == "hp":
                    raise HpGen9ilo4EskmBug
        else:
            log_my_msg(f" - {item} skipping")

        item = "#HpeiLOSSO"
        if HpeiLOSSO:
            log_my_msg(f" - {item} applying")
            patch_to_api(
                self.lom,
                self.sessobj,
                self.ilo_endpoints[item],
                self.ilo_standard[item],
            )
        else:
            log_my_msg(f" - {item} skipping")

        item = "#HpeiLODateTime"
        if HpeiLODateTime:
            log_my_msg(f" - {item} applying")
            patch_to_api(
                self.lom,
                self.sessobj,
                self.ilo_endpoints[item],
                self.ilo_standard[item],
            )
        else:
            log_my_msg(f" - {item} skipping")

        item = "#ManagerNetworkProtocol"
        if ManagerNetworkProtocol:
            log_my_msg(f" - {item} applying")
            patch_to_api(
                self.lom,
                self.sessobj,
                self.ilo_endpoints[item],
                self.ilo_standard[item],
            )
        else:
            log_my_msg(f" - {item} skipping")

        item = "#Manager"
        if Manager:
            log_my_msg(f" - {item} applying")
            patch_to_api(
                self.lom,
                self.sessobj,
                self.ilo_endpoints[item],
                self.ilo_standard[item],
            )
        else:
            log_my_msg(f" - {item} skipping")
        return

    def chk_ad(self):
        """Method: Check AD"""
        return chk_ad(self.lom, self.sessobj, self.hardware)

    def reset_ilo(self):
        """Method: Reset ilo"""
        reset_ilo(self.lom, self.sessobj)

    def eskm_test(self):
        """Method: test eskm acceesibility"""
        return ilo_eskm_test(self.lom, self.sessobj)

    def all_ilo_firmware(self):
        return get_all_firmware(self.lom, self.sessobj)

    def update_ilo_firmware(self):
        """Method: update ilo firmware"""
        log_my_msg("(HpeiloActions) update_ilo_firmware")
        ilo_fw_ver = get_ilo_version(self.lom, self.hardware)
        if self.standard_firmware_version > ilo_fw_ver:
            log_my_msg(
                f"updating ilo firmware from {ilo_fw_ver} to {self.standard_firmware_version}, this will take a few minutes..."
            )
            update_ilo_version(self.lom, self.sessobj, self.hardware, self.firmware_url)
            update_firmware_ver = get_ilo_version(self.lom, self.hardware)
            if self.standard_firmware_version == update_firmware_ver:
                return {
                    "ilo_firmware_check": "pass",
                    "ilo_firmware_version": get_ilo_version(self.lom, self.hardware),
                    "standard_firmware_version": self.standard_firmware_version,
                }
            else:
                log_my_msg("fail: ilo firmware failed to update!")
                return {
                    "ilo_firmware_check": "fail",
                    "ilo_firmware_version": update_firmware_ver,
                    "standard_firmware_version": self.standard_firmware_version,
                }
        else:
            log_my_msg("pass: ilo firmware is current or newer")
            return {
                "ilo_firmware_check": "pass",
                "ilo_firmware_version": ilo_fw_ver,
                "standard_firmware_version": self.standard_firmware_version,
            }

    def check_ilo_firmware(self):
        """Method: update ilo firmware"""
        log_my_msg("(HpeiloActions) check_ilo_firmware")
        ilo_fw_ver = get_ilo_version(self.lom, self.hardware)
        if self.standard_firmware_version > float(ilo_fw_ver):
            return {
                "ilo_firmware_check": "fail",
                "ilo_firmware_version": ilo_fw_ver,
                "standard_firmware_version": self.standard_firmware_version,
            }
        else:
            return {
                "ilo_firmware_check": "pass",
                "ilo_firmware_version": ilo_fw_ver,
                "standard_firmware_version": self.standard_firmware_version,
            }

    def clear_iml_log(self):
        """Method: clear IML log from ilo"""
        return clear_iml_log(self.lom, self.sessobj)

    def check_n_fix_user_previleges(self, username):
        """Method: Check user previledge and fix if needed"""
        log_my_msg("(HpeiloActions) check_n_fix_user_previleges")
        resp = check_user_previleges(self.lom, self.sessobj, username)
        log_my_msg(f"{username} with user id {resp[0]}")
        if resp[1]:
            log_my_msg(f"Fixing this previledges: {resp[1]}")
            apply_user_prev(self.lom, self.sessobj, resp[0])
        else:
            log_my_msg(f"{username} user previledge is ok")
        return


###
# Helper Functions
###


def get_from_api(lom, session, url):
    """Fn: GET from any api"""
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    return data


def patch_to_api(lom, session, url, payload):
    """Fn: PATCH to any API"""
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("pass: patch accepted successful")


def post_to_api(lom, session, url, payload):
    """Fn: POST to any api"""
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("pass: post accepted successful")


def flatten_dict(ddict, separator="_", prefix=""):
    """Fn: flattens a nested dictionary"""
    return (
        {
            prefix + separator + k if prefix else k: v
            for kk, vv in ddict.items()
            for k, v in flatten_dict(vv, separator, kk).items()
        }
        if isinstance(ddict, dict)
        else {prefix: ddict}
    )


def compare_two_dict(dict1, dict2):
    """Fn: Compare two dictionary key and values"""
    ignore_keys = ("LocalRole", "Status", "LicenseKey", "KeyManagerConfig_LoginName", "KeyManagerConfig_Password")
    dict_f2 = flatten_dict(dict1, separator="_", prefix="")  ##host info
    dict_f1 = flatten_dict(dict2, separator="_", prefix="")  ##STANADRD
    log_my_msg("{:=<120}".format(""))
    log_my_msg("{:<57}{:10}{:<25}{:<25}".format("Attributes", "Results", "Current Value", "Expected Value"))
    log_my_msg("{:=<120}".format(""))
    settings_check = ()
    chk_result = "pass"
    for key, value in dict_f2.items():
        if isinstance(value, list):
            if isinstance(value[0], dict):
                if compare_dict_items(dict_f1.get(key, {}), value, ignore_keys) == "fail":
                    chk_result = "fail"
            else:
                chk_result = compare_list(dict_f1.get(key, []), value)
        elif not isinstance(value, (list, dict)) and key not in ignore_keys:
            s2 = str(dict_f1.get(key, ""))  ## HOST DICT
            s1 = str(value)  ## STANADRD DICT
            chk_result = compare_strings(s1, s2)
        else:
            continue
        settings_check += (chk_result,)
        log_my_msg(
            "{:<57}{:10}{:<25}{:<25}".format(
                str(key), str(chk_result), str(dict_f1.get(key, "")), str(dict_f2.get(key, ""))
            )
        )
    if "fail" in settings_check:
        return "fail"
    return "pass"


###
### HPE ilo functions
###


def compare_strings(s1, s2):
    if s1.strip() != s2.strip():
        return "fail"
    else:
        return "pass"


def compare_list(l1, l2):
    if set(l1) == set(l2):
        return "pass"
    else:
        return "fail"


def compare_dict_items(d1, d2, ignore_keys):
    if not d1 or not d2 or len(d1) != len(d2):
        return "fail"
    for a, b in zip(d1, d2):
        for key, value in a.items():
            b_value = b.get(key, "null")
            if key not in ignore_keys:
                if str(b_value) == "null" or str(value) != str(b_value):
                    return "fail"
            else:
                continue
    return "pass"


def get_standard_hpe_json(networkdata, standard_url):
    """Fn: get_standard_hpe_json"""
    logging.info("Fn: get_standard_hpe_json")
    log_my_msg(standard_url)
    resp = no_token_sessobj.get(f"{standard_url}")
    standard = resp.text
    standard_data = (
        standard.replace("<DNS1>", networkdata["DNS1"])
        .replace("<DNS2>", networkdata["DNS2"])
        .replace("<DNS3>", networkdata["DNS3"])
        .replace("<eskm_pri>", networkdata["ESKM_PRI"])
        .replace("<eskm_secondary>", networkdata["ESKM_SECONDARY"])
        .replace("<timezone>", networkdata["TIMEZONE"])
        .replace("<eskm_group>", networkdata["ESKM_GROUP"])
        .replace("<eskm_key>", networkdata["ESKM_KEY"])
        .replace("<time1>", networkdata["TIME1"])
        .replace("<time2>", networkdata["TIME2"])
        .replace("<eskm_loginname>", networkdata["ESKMUSER"])
        .replace("<eskm_password>", networkdata["ESKMPASS"])
        .replace("<hostname>", networkdata["LOM"])
        .replace("<fqdn>", networkdata["LOM_FQDN"])
        .replace("<domainname>", networkdata["DOMAIN"])
        .replace("LegacyBios", "Uefi")
        .replace('"RequireHostAuthentication": true', '"RequireHostAuthentication": false')
        .replace("\n", "")
    )
    data = json.loads(standard_data)
    ilo_endpoints = {}
    ilo_standard = {}

    for item in data.items():
        topic = item[0].split(".")[0]
        if topic == "Comments":
            continue
        if isinstance(item[1], dict):
            mydict = item[1]
            for key, val in mydict.items():
                if key == "/redfish/v1/AccountService/Accounts/1/":
                    key = "/redfish/v1/AccountService/Accounts/"
                ilo_endpoints.update({topic: key})
                ilo_standard.update({topic: val})
        else:
            log_my_msg("not a valid dict")
    return ilo_endpoints, ilo_standard


# @retry(exceptions=Exception, delay=4, tries=7, backoff=4)
def check_api(lom):
    """Fn: Check if API is available"""
    status = None
    url = "/redfish/v1/"
    log_my_msg("Fn: check_api - redfish api availability")
    try:
        result = no_token_sessobj.get(f"https://{lom}{url}")
        result.json()
        status = result.status_code
        if status != 200:
            log_my_msg("API response failed")
            return False
        else:
            log_my_msg("API appears to be ready")
            return True
    except Exception:
        log_my_msg(f"Waiting on api response")
        raise


def reset_ilo(lom, session):
    """Fn: Reset HPE ilo"""
    log_my_msg("Fn: reset_ilo")
    url = "/redfish/v1/Managers/1/Actions/Manager.Reset"
    payload = {}
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("ILO has been reset, checking API in 30 seconds.")
    time.sleep(30)
    check_api(lom)
    time.sleep(10)


def ilo_eskm_test(lom, session):
    """Fn: ilo eskm test"""
    log_my_msg("Fn: ilo_eskm_test")
    url = "/redfish/v1/Managers/1/SecurityService/ESKM/Actions/HpeESKM.TestESKMConnections/"
    payload = {}
    resp = session.post(f"https://{lom}{url}", payload)
    if_resp_not_ok(resp)
    text = resp.json()["error"]["@Message.ExtendedInfo"][0]["MessageId"]
    if "PrimarySecondaryESKMServersAccessible" in text:
        return f"pass: {text}"
    else:
        return f"warning: {text}"


def get_ilo_version(lom, hardware):
    """Fn: get_ilo_version"""
    log_my_msg("Fn: get_ilo_version")
    url = "/redfish/v1/"
    resp = no_token_sessobj.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()["Oem"][hardware.capitalize()]["Manager"][0]
    return float(data["ManagerFirmwareVersion"])


def update_ilo_version(lom, session, hardware, fw_url):
    """Fn: update_ilo_version"""
    log_my_msg("Fn: update_ilo_version")
    url = "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate/"
    payload = {"ImageURI": fw_url}
    if hardware == "hp":
        url = "/redfish/v1/Managers/1/UpdateService/Actions/HpiLOFirmwareUpdate.InstallFromURI/"
        payload = {"FirmwareURI": fw_url, "TPMOverrideFlag": True}
    log_my_msg(payload)
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    data = json.loads(resp.text)
    log_my_msg("ilo firmware updating, checking status in 3 minutes...")
    time.sleep(180)
    check_api(lom)
    time.sleep(30)
    return data


def get_all_firmware(lom, session):
    """Fn: Get all firmware versions"""
    url = "/redfish/v1/Systems/1/FirmwareInventory/"
    resp = session.get(f"https://{lom}{url}")
    data = resp.json()
    fw_dict = {}
    for i in data["Current"]:
        for x in data["Current"][i]:
            if x is not None:
                fw_dict[x["Name"]] = x["VersionString"]
    return fw_dict


def check_ilo_license_type(lom, session):
    url = "/redfish/v1/Managers/1/LicenseService/1"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    return data["LicenseType"]


def chk_ad(lom, session, hardware):
    """Fn: chk_ad_account"""
    log_my_msg("Fn: chk_ad_account")
    user_pass = get_lom_creds()["hp"]["maas_oob@example.com"]
    if hardware == "hpe":
        start_url = "/redfish/v1/AccountService/DirectoryTest/Actions/HpeDirectoryTest.StartTest/"
        payload = json.dumps({"TestUserName": "maas_oob@example.com", "TestUserPassword": user_pass})
        start_resp = session.post(f"https://{lom}{start_url}", data=payload)
        if_resp_not_ok(start_resp)
        time.sleep(30)
        stop_url = "/redfish/v1/AccountService/DirectoryTest/Actions/HpeDirectoryTest.StopTest/"
        stop_resp = session.post(f"https://{lom}{stop_url}", data={})
        if_resp_not_ok(stop_resp)
        time.sleep(30)
        chk_url = "/redfish/v1/AccountService/DirectoryTest/"
        resp = session.get(f"https://{lom}{chk_url}")
        data = resp.json()
        if_resp_not_ok(resp)
        ad_status = data.get("OverallStatus", "null")
        ad_info = data.get("TestResults", "null")
        return (ad_status, ad_info)
    elif hardware == "hp":
        status = chk_ad_ilo4_account(lom, "maas_oob@example.com", user_pass)
        return (status, "ilo4 check")
    else:
        return ("Unknown hardware", f"AD cannont check Unknown hardware = {hardware}")


def chk_ad_ilo4_account(lom, lomuser, lompass):
    """Fn: ilo4 chk_ad_account"""
    log_my_msg("Fn: ilo4 chk_ad_account")
    url = f"https://{lom}/redfish/v1/Systems/"
    resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
    if resp.ok:
        log_my_msg("PASS: AD account working.")
        return "pass"
    else:
        log_my_msg("WARNING: AD account not working.")
        return "fail"


def clear_iml_log(lom, session):
    """Fn: Clear IML log messages"""
    log_my_msg("Fn: clear_iml_log")
    body = {}
    url = f"https://{lom}/redfish/v1/Systems/1/LogServices/IML/Actions/LogService.ClearLog/"
    resp = session.post(url, data=json.dumps(body))
    if_resp_not_ok(resp)
    log_my_msg("pass: clear iml log")


def check_user_previleges(lom, session, lomuser_to_check):
    """Fn: Check user have previledges or not"""
    log_my_msg(f"Fn: Checking user previledges for {lomuser_to_check}")
    url = f"https://{lom}/redfish/v1/AccountService/Accounts"
    resp = session.get(url)
    if_resp_not_ok(resp)
    resp = resp.json()
    false_prev_list = []
    userid = ""
    if "Items" in resp.keys():
        for user in resp["Items"]:
            userid = user["Id"]
            prev = user["Oem"]["Hp"]["Privileges"]
            false_prev_list.extend(k for k, v in prev.items() if v == False and k != "SystemRecoveryConfigPriv")
    else:
        for user in resp["Members"]:
            url = f"https://{lom}{user['@odata.id']}"
            id_resp = session.get(url)
            if_resp_not_ok(id_resp)
            id_resp = id_resp.json()
            if id_resp["UserName"] == lomuser_to_check:
                userid = id_resp["Id"]
                prev = id_resp["Oem"]["Hpe"]["Privileges"]
                false_prev_list.extend(k for k, v in prev.items() if v == False and k != "SystemRecoveryConfigPriv")
    return userid, false_prev_list


def apply_user_prev(lom, session, userid):
    """Fn: apply user previledge"""
    log_my_msg("Fn: Applying user previledges")
    payload = {
        "Oem": {
            "Hpe": {
                "Privileges": {
                    "HostBIOSConfigPriv": True,
                    "HostNICConfigPriv": True,
                    "HostStorageConfigPriv": True,
                    "LoginPriv": True,
                    "RemoteConsolePriv": True,
                    "UserConfigPriv": True,
                    "VirtualMediaPriv": True,
                    "VirtualPowerAndResetPriv": True,
                }
            }
        }
    }
    url = f"https://{lom}/redfish/v1/AccountService/Accounts/{userid}"
    resp = session.patch(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg("pass: applied successfully")
    return
