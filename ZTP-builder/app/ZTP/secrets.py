# -*- coding: utf-8 -*-

"""
secrets.py - gets secrets from encrypted file
"""

__author__ = "David Blasing, Chirag Patel"
__email__ = "support@example.com"

import json
import logging
import time

from cryptography.fernet import Fernet

import app.build_service.cache as cache

from ._common import if_resp_not_ok, log_my_msg
from ._session import create_requests_retry_no_token_auth

no_token_sessobj = create_requests_retry_no_token_auth()

logger = logging.getLogger(__name__)


def check_idrac_creds(lom, user_dict) -> list:
    """Fn: check_idrac_creds"""
    log_my_msg("Fn: check_idrac_creds")
    creds_list = []
    url = f"https://{lom}/redfish/v1/Systems/"
    for lomuser, lompass in user_dict.items():
        time.sleep(1)
        resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
        if resp.ok:
            log_my_msg(f"valid lom creditials found => {lomuser}")
            creds_list = [lomuser, lompass]
            return creds_list
    if len(creds_list) == 0:
        log_my_msg(" fail: no valid lom creditials found!")
        raise Exception("No valid lom creditials found!")


def chk_for_login_delay(lom) -> int:
    """Fn: chk_for_login_delay"""
    url = f"https://{lom}/redfish/v1/"
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    vendor = next(iter(resp.json()["Oem"])).lower()
    if vendor == "dell":
        return 0
    if vendor == "hpe":
        return resp.json()["Oem"]["Hpe"]["Sessions"]["LoginFailureDelay"]
    if vendor == "hp":
        return resp.json()["Oem"]["Hp"]["Sessions"]["LoginFailureDelay"]


def check_ilo_creds(lom, user_dict) -> list:
    """Fn: check_ilo_creds"""
    log_my_msg("Fn: check_ilo_creds")
    creds_list = []
    default_admin_user = "AdminLO"
    log_my_msg(f"Checking user {default_admin_user}")
    url = f"https://{lom}/redfish/v1/Systems/"
    resp = no_token_sessobj.get(url, auth=(default_admin_user, user_dict[default_admin_user]))
    if resp.ok:
        return [default_admin_user.lower(), user_dict[default_admin_user]]
    else:
        del user_dict[default_admin_user]
    for lomuser, lompass in user_dict.items():
        log_my_msg(f"Checking user {lomuser}")
        login_delay = chk_for_login_delay(lom)
        log_my_msg(f"Checking login delay, waiting {login_delay} to check.")
        time.sleep(login_delay + 1)
        if "AdminLO_old" in lomuser:
            lomuser = default_admin_user
        # if not isinstance(lompass, list):
        resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
        if resp.ok:
            log_my_msg(f"valid lom creditials found => {lomuser}")
            return [lomuser, lompass]
        # else:
        #     for i in lompass:
        #         login_delay = chk_for_login_delay(lom)
        #         time.sleep(login_delay + 1)
        #         resp = no_token_sessobj.get(url, auth=(default_admin_user, i))
        #         if resp.ok:
        #             log_my_msg(f"valid lom creditials found => {lomuser}")
        #             return [default_admin_user, i]
    if len(creds_list) == 0:
        log_my_msg(" fail: no valid lom creditials found!")
        raise Exception("No valid lom creditials found!")


def decrypt_file(key_file, url):
    """Fn: decrypt_file"""
    resp = no_token_sessobj.get(key_file)
    if_resp_not_ok(resp)
    key = resp.content
    f_key = Fernet(key)
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    data = resp.content
    decrypted_data = f_key.decrypt(data)
    return json.loads(decrypted_data.decode("UTF-8"))


def get_lom_creds() -> dict:
    """Fn: get lom creds"""
    return cache.CREDS


def admin_lom_creds(lom, generation, vendor) -> list:
    """Fn: admin_lom_creds"""
    log_my_msg("Fn: admin_lom_creds")
    dictall = get_lom_creds()
    adminlo_creds = dictall["hpe"]["AdminLO"]
    if vendor == "dell":
        return check_idrac_creds(lom, dictall["dell"])
    if "hp" in vendor:
        working_creds = check_ilo_creds(lom, dictall["hpe"])
        lomuser = working_creds[0]
        lompass = working_creds[1]
        if "adminlo" in working_creds:
            log_my_msg("Pass: AdminLO user found with current creds")
        else:
            users = get_user_accounts(lom, lomuser, lompass)
            if any(x["user"].lower() == "adminlo" for x in users):
                log_my_msg(" - Updating AdminLO creds")
                payload = {"Password": adminlo_creds}
                ep = next(item for item in users if item["user"].lower() == "adminlo")["user_ep"]
                url = f"https://{lom}{ep}"
                resp = no_token_sessobj.patch(url, data=json.dumps(payload), auth=(lomuser, lompass))
                log_my_msg("Pass: Successfully updated AdminLO creds")
            else:
                url = f"https://{lom}/redfish/v1/AccountService/Accounts/"
                hp_user_dict = get_hp_user_standard(generation, adminlo_creds)
                resp = no_token_sessobj.post(url, data=json.dumps(hp_user_dict), auth=(lomuser, lompass))
            if_resp_not_ok(resp)
        return ["AdminLO", adminlo_creds]


def get_hp_user_standard(generation, lompass):
    """Fn: get_hp_user_standard"""
    if generation == "gen10":
        hp_user_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json/gen10_full.json"
    elif generation == "gen11":
        hp_user_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json/gen11_full.json"
    else:
        hp_user_url = "http://bmi-prod.example.com/pub/tools/github/standards/HPE-Standard/json/gen9_full.json"
    user_resp = no_token_sessobj.get(hp_user_url)
    data = user_resp.text
    hp_user_data = data.replace("<adminlo_pw>", lompass).replace("\n", "")
    hp_user_json = json.loads(hp_user_data)["#ManagerAccount.v1_1_3.ManagerAccount"][
        "/redfish/v1/AccountService/Accounts/"
    ]
    return hp_user_json


def del_non_std_ilo_accounts(lom, lomuser, lompass):
    """Fn: setup_standard_ilo_accounts"""
    log_my_msg("Fn: setup_standard_ilo_accounts")
    users = get_user_accounts(lom, lomuser, lompass)
    for user in users:
        log_my_msg(f" - Checking user: {user} ")
        if user["user"].lower() == "adminlo":
            log_my_msg(f" - keeping {user} ")
            continue
        if "_HPOneView" in user["user"]:
            log_my_msg(f" - keeping {user} ")
            continue
        delete_user_accounts(lom, lomuser, lompass, user)
    return


def del_companylo_account(lom, lomuser, lompass):
    """Fn: del_companylo_account"""
    log_my_msg("Fn: del_companylo_account")
    users = get_user_accounts(lom, lomuser, lompass)
    msg = None
    for user in users:
        if user["user"].lower() == "companylo":
            delete_user_accounts(lom, lomuser, lompass, user)
            log_my_msg(" - User companylo removed.")
            msg = " - User companylo removed."
    if msg is None:
        log_my_msg(" - User companylo does not exsist.")


def delete_user_accounts(lom, lomuser, lompass, user):
    """Fn: delete_user_accounts"""
    log_my_msg("Fn: delete_user_accounts")
    log_my_msg(f" - removing user: {user}")
    val = user["user_ep"]
    resp = no_token_sessobj.delete(f"https://{lom}{val}", auth=(lomuser, lompass))
    if_resp_not_ok(resp)


def get_user_accounts(lom, lomuser, lompass):
    """Fn: get_user_accounts"""
    log_my_msg("Fn: get_user_accounts")
    url = "/redfish/v1/AccountService/Accounts/"
    resp = no_token_sessobj.get(f"https://{lom}{url}", auth=(lomuser, lompass))
    user = []
    if_resp_not_ok(resp)
    data = resp.json()
    try:
        accnt = data["Members"]
    except KeyError:
        accnt = data["Items"]
    for mem in accnt:
        user_endpoint = mem["@odata.id"]
        login_delay = chk_for_login_delay(lom)
        time.sleep(login_delay + 1)
        resp = no_token_sessobj.get(f"https://{lom}{user_endpoint}", auth=(lomuser, lompass))
        if_resp_not_ok(resp)
        data = resp.json()
        ilo_user = {"user": data["UserName"], "user_ep": data["@odata.id"]}
        user.append(ilo_user)
        log_my_msg(f" - get user acct info: {user}")
    return user


def get_baseos_creds(vendor):
    """Fn: get_baseos_creds"""
    if vendor == "rhel":
        return cache.CREDS["rhel"]
    if vendor == "esxi":
        return cache.CREDS["esxi"]
