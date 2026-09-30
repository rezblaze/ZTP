# -*- coding: utf-8 -*-

"""helper function here serving serverdata and networkdata"""

import logging
import socket
from enum import Enum

import aiohttp
from ldap3.utils.conv import escape_filter_chars

from app.modules.cache import CREDS

logger = logging.getLogger(__name__)


class BuildStatuses(str, Enum):
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


async def raise_exception(msg):
    """Fn: if response from api not ok raise_exception"""
    msg = escape_filter_chars(msg)
    logger.error(msg)
    raise Exception(msg)


def cleanup_my_dict(dict1):
    """Fn: Cleanup dictionary, make keys uppercase & values stripped string"""
    dict2 = {}
    for k, v in dict1.items():
        if isinstance(v, list):
            dict2[k.upper()] = v
            continue
        if isinstance(v, dict):
            dict2[k.upper()] = cleanup_my_dict(dict1[k])
        else:
            dict2[k.upper()] = str(v).strip()
    return dict2


async def find_lom(lom):
    """Fn: Find LOM FQDN since its not alway standard"""
    try:
        socket.gethostbyname(lom)
    except socket.gaierror:
        return False
    return True


async def get_redfish_v1(lom):
    """Fn: get redfish/v1"""
    url = escape_filter_chars(f"https://{lom}/redfish/v1/")
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
            async with session.get(url) as resp:
                return await resp.json()
    except Exception as err:
        msg = f"Error connecting {url} {err}"
        await raise_exception(msg)


async def get_hardware_vendor(lom):
    """Fn: get hardware vendor for lom ip provided"""
    data = await get_redfish_v1(lom)
    try:
        vendor = next(iter(data["Oem"])).lower()
        if "hp" in vendor and "Product" in data:
            vendor = (vendor, data["Product"])
    except Exception:
        if data["Name"].split()[0] == "Quanta":
            vendor = "quanta"
        else:
            msg = "H4 Vendor couldn't be identified"
            await raise_exception(msg)
    return vendor


async def check_if_server_in_dns(servername):
    """Fn: check_if_server_in_dns"""
    try:
        ip = socket.gethostbyname(servername)
        socket.gethostbyaddr(ip)
    except Exception:
        await raise_exception(f"Servername {servername} not in corporate DNS")


async def isloname(servername):
    """Fn: isloname"""
    if servername.split(".")[0][-2:] == "lo":
        await raise_exception(f"Servername {servername} provided appear to be lom/management name!")


async def set_min_networkdata(servername):
    """Fn: Set minimum network information for serverinfo or networkdata function"""
    await isloname(servername)
    await check_if_server_in_dns(servername)
    try:
        dns_name = socket.getfqdn(servername)
    except Exception as err:
        await raise_exception(f"error while getting dns name with socket.getfqdn {err}")
    dns_sort_name = dns_name.split(".")[0]
    servername_sort_name = servername.split(".")[0]
    if dns_sort_name.lower() != servername_sort_name.lower():
        await raise_exception("Servername provided doesn't match with DNS name, please provide fqdn")
    networkdata = {"SERVERNAME": dns_name}
    networkdata["SHORT_NAME"] = networkdata["SERVERNAME"].split(".", 1)[0]
    networkdata["DOMAIN"] = networkdata["SERVERNAME"].split(".", 1)[1]
    networkdata["LOM"] = f"{networkdata['SHORT_NAME']}lo"
    networkdata["LOM_FQDN"] = f"{networkdata['SHORT_NAME']}lo.example.com"

    if await find_lom(networkdata["LOM_FQDN"]):
        pass
    elif await find_lom(networkdata["LOM"] + "." + networkdata["DOMAIN"]):
        networkdata["LOM_FQDN"] = networkdata["LOM"] + "." + networkdata["DOMAIN"]
    else:
        msg = f"Fail to get lom fqdn {networkdata['LOM']}"
        await raise_exception(msg)
    try:
        networkdata["LOMIP"] = socket.gethostbyname(networkdata["LOM_FQDN"])
    except Exception as err:
        await raise_exception(f"Error while socket.gethostname {err}")
    networkdata["IP"] = socket.gethostbyname(networkdata["SERVERNAME"])
    try:
        vendor = await get_hardware_vendor(networkdata["LOMIP"])
    except Exception as err:
        await raise_exception(err)
    if type(vendor) is tuple:
        networkdata["HARDWARE"] = vendor[0].lower()
        networkdata["PRODUCT"] = vendor[1].lower()
        networkdata["GENERATION"] = networkdata["PRODUCT"].split()[2]
        networkdata["MODEL"] = networkdata["PRODUCT"].split()[1]
    else:
        networkdata["HARDWARE"] = vendor
        networkdata["PRODUCT"] = ""
        if vendor == "hp":
            networkdata["GENERATION"] = "gen9"
        else:
            networkdata["GENERATION"] = ""
        networkdata["MODEL"] = ""
    return networkdata
