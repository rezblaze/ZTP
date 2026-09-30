# -*- coding: utf-8 -*-
"""
_hardware.py -- hardware functions for NetworkData.
"""

import json
import logging
from operator import itemgetter

from ._common import if_resp_not_ok, log_my_msg
from ._session import create_requests_retry_no_token_auth
from .exception import PrimaryMacNotFound
from .secrets import admin_lom_creds

__author__ = "David Blasing, Chirag Patel, Joel Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)
no_token_sessobj = create_requests_retry_no_token_auth()


def get_hardware_vendor(lom):
    """Fn: get_hardware_vendor"""
    url = f"https://{lom}/redfish/v1"
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    return next(iter(data["Oem"])).lower()


def get_dell_lifecycle_version(lom, lomuser, lompass):
    """Fn: get_dell_lifecycle_version"""
    log_my_msg("Fn: get_dell_lifecycle_version")
    url = f"https://{lom}/redfish/v1/UpdateService/FirmwareInventory/"
    resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
    if_resp_not_ok(resp)
    resp_dict = resp.json()
    try:
        mem_list = resp_dict["Members"]
    except KeyError as error:
        log_my_msg(f" - ZTP: FirmwreInventory {error} not found!")
        raise
    for member in mem_list:
        end_point = member["@odata.id"]
        url = f"https://{lom}{end_point}"
        resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
        if_resp_not_ok(resp)
        resp_dict = resp.json()
        key = resp_dict["Name"]
        if "Lifecycle" in key:
            value = resp_dict["Version"]
        return value


def get_dell_model(lom, lomuser, lompass):
    """Fn: get_dell_model"""
    url = f"https://{lom}/redfish/v1/Systems/System.Embedded.1"
    resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
    if resp.ok:
        data = resp.json()
        return data["Model"].split()[1].lower()
    else:
        log_my_msg(f" - FAIL: url={url} \n response code = {resp.status_code} \n response text = {resp.text}")
        raise Exception()


###
###  Get primary mac address function
####


def get_primary_ethernet_mac(vendor, generation, lom, lomuser="", lompass=""):
    """Fn: get_primary_ethernet_mac"""
    if lomuser == "" and lompass == "":
        lomcred = admin_lom_creds(lom, generation, vendor)
        lomuser = lomcred[0]
        lompass = lomcred[1]
    if vendor == "dell":
        mac = get_dell_mac(lom, lomuser, lompass)
    if vendor == "hpe":
        mac = get_hpe_mac(generation, lom, lomuser, lompass)
    if vendor == "hp":
        mac = get_hp_mac(lom, lomuser, lompass)
    if mac is None:
        raise PrimaryMacNotFound
    return mac.lower()


def get_dell_mac(lom, lomuser, lompass):
    """Fn: get_dell_mac"""
    log_my_msg("Fn: get_dell_mac")
    mac = None
    model = get_dell_model(lom, lomuser, lompass)
    if model == "r6515":
        url = f"https://{lom}/redfish/v1/Chassis/System.Embedded.1/NetworkAdapters/NIC.Slot.2/NetworkPorts/NIC.Slot.2-1"
        log_my_msg(f"Dell {model} first trying to get mac from default port at {url}")
        resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
        if resp.status_code == 404:
            url = f"https://{lom}/redfish/v1/Chassis/System.Embedded.1/NetworkAdapters/NIC.Embedded.1/NetworkPorts/NIC.Embedded.1-1"
            log_my_msg(
                f"fail: url not found so trying {url} per https://github.example.com/example-org/ztp/issues/56"
            )
            resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
            if_resp_not_ok(resp)
    else:
        url = f"https://{lom}/redfish/v1/Systems/System.Embedded.1/NetworkAdapters/NIC.Integrated.1/NetworkPorts/NIC.Integrated.1-1"
        resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
        if_resp_not_ok(resp)
    data = resp.json()
    if "AssociatedNetworkAddresses" in data:
        mac = data["AssociatedNetworkAddresses"][0]
    return mac


def get_hpe_model(lom):
    """Fn: get_hpe_model"""
    url = f"https://{lom}/redfish/v1"
    resp = no_token_sessobj.get("%s" % url)
    if_resp_not_ok(resp)
    generation = resp.json()
    if "Product" in generation:
        return resp.json()["Product"].lower()
    elif "iLO 4" in json.dumps(resp.json()["Oem"]["Hp"]["Manager"]):
        return "proliant dl380 gen9"
    else:
        log_my_msg(f" - FAIL: url={url} \nresponse_code = {resp.status_code} \n response text = {resp.text}")
        raise Exception()


###  Gen9 mac address function
def get_hp_mac(lom, lomuser, lompass):
    """Fn: get_hp_mac"""
    log_my_msg("Fn: get_hp_mac")
    mac_list = []
    nics = get_hp_g9_nic(lom, lomuser, lompass)
    log_my_msg(f"Availble NICs: {nics}")
    for key, val in nics.items():
        mac_list.append(val["MacAddress"])
    if len(mac_list) == 0:
        raise PrimaryMacNotFound
    return mac_list[0]


def get_hp_g9_nic(lom, lomuser, lompass):
    """Fn: get_hp_g9_nic"""
    log_my_msg("Fn: get_hp_g9_nic")
    nic_1gb_dict = {}
    nic_dict = {}
    url = f"https://{lom}/redfish/v1/systems/1/NetworkAdapters"
    log_my_msg(f"getting mac from port at {url}")
    resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
    if_resp_not_ok(resp)
    nic_ep_data = resp.json()
    if nic_ep_data["Members@odata.count"] == 0:
        logger.critical(" - CRITICAL: No valid network adapeter found!")
        raise Exception(f" - CRITICAL: No valid network adapeter found! {nic_ep_data}")
    nic_ep = nic_ep_data["Members"]
    nic_ep_list = list(map(itemgetter("@odata.id"), nic_ep))
    log_my_msg(nic_ep_list)
    for i in nic_ep_list:
        resp = no_token_sessobj.get(f"https://{lom}{i}", auth=(lomuser, lompass))
        if_resp_not_ok(resp)
        nic_data = resp.json()["PhysicalPorts"]
        nic_keys = {"MacAddress", "Status", "SpeedMbps"}
        for pos, item in enumerate(nic_data):
            nic_name = resp.json()["Name"] + str(pos)
            if "1Gb" in nic_name:
                nic_1gb_dict_filtered = {key: item[key] for key in item.keys() & nic_keys}
                nic_1gb_dict.update({nic_name: nic_1gb_dict_filtered})
            else:
                nic_dict_filtered = {key: item[key] for key in item.keys() & nic_keys}
                nic_dict.update({nic_name: nic_dict_filtered})
    if len(nic_dict) > 0:
        return nic_dict
    else:
        log_my_msg(json.dumps(nic_dict, indent=4))
        return nic_1gb_dict


###  Gen10 mac address function
def get_hpe_mac(generation, lom, lomuser, lompass):
    """Fn: get_hpe_mac"""
    log_my_msg("Fn: get_hpe_mac")
    nics = get_hpe_g10_nic(generation, lom, lomuser, lompass)
    nic_list = ["640FLR-SFP28", "MCX562A-ACAI"]
    if generation.lower() == "gen10":
        for key, val in nics.items():
            log_my_msg(f"KEY = {key} VAL = {val}")
            if any(x in key for x in nic_list) and key.endswith("0"):
                log_my_msg(f"primary nic info: {key}")
                return val["MacAddress"]
    else:
        nictuple = next(iter(nics.items()))
        nicdict = nictuple[1]
        return nicdict["MACAddress"]


def get_hpe_g10_nic(generation, lom, lomuser, lompass):
    """Fn: get_hpe_g10_nic"""
    log_my_msg("Fn: get_hpe_g10_nic")
    tmp_dict = {}
    nic_dict = {}
    if generation.lower() == "gen11":
        return get_hpe_g11_nic(lom, lomuser, lompass)
    url = f"https://{lom}/redfish/v1/systems/1/BaseNetworkAdapters"
    log_my_msg(f"getting mac from port at {url}")
    resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
    if_resp_not_ok(resp)
    nic_ep = resp.json()["Members"]
    nic_ep_list = list(map(itemgetter("@odata.id"), nic_ep))
    for i in nic_ep_list:
        resp = no_token_sessobj.get(f"https://{lom}{i}", auth=(lomuser, lompass))
        if_resp_not_ok(resp)
        nic_data = resp.json()["PhysicalPorts"]
        nic_keys = {"MacAddress", "LinkStatus", "SpeedMbps"}
        for pos, item in enumerate(nic_data):
            nic_name = resp.json()["Name"] + str(pos)
            tmp_dict.update({nic_name: item})
            nic_dict_filtered = {key: item[key] for key in item.keys() & nic_keys}
            nic_dict.update({nic_name: nic_dict_filtered})
    log_my_msg(json.dumps(nic_dict, indent=4))
    return nic_dict


def get_hpe_g11_nic(lom, lomuser, lompass):
    """Fn: get_hpe_g10_nic"""
    log_my_msg("Fn: get_hpe_g10_nic")
    tmp_dict = {}
    nic_dict = {}
    url = f"https://{lom}/redfish/v1/Systems/1/EthernetInterfaces/"
    log_my_msg(f"getting mac from port at {url}")
    resp = no_token_sessobj.get(url, auth=(lomuser, lompass))
    if_resp_not_ok(resp)
    nic_ep = resp.json()["Members"]
    nic_ep_list = list(map(itemgetter("@odata.id"), nic_ep))
    nic_keys = ["MACAddress", "LinkStatus", "SpeedMbps"]
    for i in nic_ep_list:
        resp = no_token_sessobj.get(f"https://{lom}{i}", auth=(lomuser, lompass))
        if_resp_not_ok(resp)
        nic_data = resp.json()
        nic_name = nic_data["Id"]
        for key in nic_keys:
            tmp_dict.update({nic_name: key})
            nic_dict_filtered = {key: nic_data[key] for key in nic_data.keys() & nic_keys}
            nic_dict.update({nic_name: nic_dict_filtered})
    log_my_msg(json.dumps(nic_dict, indent=4))
    return nic_dict
