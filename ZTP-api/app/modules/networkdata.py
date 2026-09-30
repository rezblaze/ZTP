import asyncio
import ipaddress
import json
import logging
import os
import socket
import sys
import time

import aiohttp
from ldap3.utils.conv import escape_filter_chars

from app.modules._helper import BuildStatuses, raise_exception, set_min_networkdata
from app.modules.cache import CREDS, HPE_VARIABLES

logger = logging.getLogger(__name__)


async def networkdata(servername):
    """Fn: create async task for networkdata"""
    task = asyncio.create_task(get_networkdata(servername))
    return await task


async def get_networkdata(servername):
    """Fn: get networkdata for server"""
    servername = servername.lower()
    networkdata = {}
    try:
        networkdata = await set_min_networkdata(servername)
        networkdata.update(await get_bu(networkdata))
        networkdata.update(await get_infra_data(networkdata))
        networkdata.update(STATUS=BuildStatuses.SUCCESS.value)
    except Exception as err:
        networkdata.update(SERVERNAME=servername)
        networkdata.update(STATUS=BuildStatuses.ERROR.value)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        networkdata.update(ERROR_DETAIL=f"Error: {exc_obj} {exc_type}  {fname} {exc_tb.tb_lineno}")
        logger.info(f"error: {err} {sys.exc_info()}")
    finally:
        networkdata.update(TIME=time.strftime("%x %X %Z"))
    return dict((k.upper(), v) for k, v in networkdata.items())


async def get_infra_data(networkdata):
    if isinstance(networkdata, dict):
        server_ip = networkdata["IP"]
    else:
        server_ip = networkdata
    try:
        ipaddress.ip_address(server_ip)
    except ValueError:
        raise ValueError(f"Invalid IP address: {server_ip}")
    try:
        url = escape_filter_chars(
            f"http://it-capacity-ws.example.com/HardwareReadinessService/Hardware.svc/v1/ipam/GetIpInfo/ip={server_ip}"
        )
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                if isinstance(data, str):
                    data = json.loads(data)
    except Exception as err:
        msg = f"Exception connecting {url} {err}"
        await raise_exception(msg)
    if resp.status != 200:
        msg = f"fail response from {url} response_code: {resp.status} resp_text: {await resp.text()}"
        await raise_exception(msg)
    ip_data = next(iter(data))
    infra_data = {
        "SOURCE1": "http://it-capacity-ws.example.com",
        "it-capacity-ws": ip_data,
    }
    infra_data["SUBNET"] = ip_data["Subnet"]
    infra_data["SITECODE"] = ip_data["SiteCode"]
    infra_data["DC"] = "SITE_B"
    if infra_data["SITECODE"].lower() == "site_a":
        infra_data["DC"] = "SITE_A"
    infra_data["GATEWAY"] = ip_data["Gateway"]
    infra_data["NETMASK"] = ip_data["Mask"]
    infra_data["CIDR"] = ip_data["CIDR"]

    logger.info(f"fn:get_infra_data {url}")
    infra_data["SOURCE2"] = "https://hardwareautomation.example.com"
    try:
        url = escape_filter_chars(
            f"https://hardwareautomation.example.com/api/v1/network/getnetworksdataforip/{server_ip}"
        )
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                if isinstance(data, str):
                    data = json.loads(data)
                print(f"data: {data}")
                print(type(data))
    except Exception as err:
        msg = f"Exception connecting {url} {err}"
        # await raise_exception(msg)
        logger.error(msg)
    if resp.status == 200 and isinstance(data, dict) and data != "Subnet not found":
        logger.info(f"fn:get_infra_data {url}")
        infra_data["hardwareautomation"] = data
        infra_data["VLANID"] = data["IP_VLAN"]
        infra_data["DC"] = data["DataCenterCode"].split("-")[1]
        infra_data["ZONE"] = data["NetworkZoneCode"]
    else:
        msg = f"url: {resp.url}\nresponse: {await resp.text()} \nnote: Assuming zone NZ-INTRA since we cannot retrieve data"
        logger.warning(msg)
        infra_data["ZONE"] = "NZ-INTRA"
        data = {"error": f"{await resp.text()} - Assuming NZ-INTRA zone"}
        infra_data["hardwareautomation"] = data

    if infra_data["ZONE"] == "NZ-INTER":
        infra_data.update(HPE_VARIABLES["DMZ"])
    elif infra_data["DC"] == "SITE_A":
        infra_data.update(HPE_VARIABLES["SITE_A"])
    else:
        infra_data.update(HPE_VARIABLES["SITE_B"])

    # update spp

    return infra_data


async def get_bu(networkdata):
    """Fn: get server backup(bu) interface data"""
    bu = {}
    bu_servername = f"{networkdata['SHORT_NAME']}bu.{networkdata['DOMAIN']}"
    try:
        bu_ip = socket.gethostbyname(bu_servername)
        exist = True
    except Exception:
        exist = False
    if exist:
        try:
            url = f"http://it-capacity-ws.example.com/HardwareReadinessService/Hardware.svc/v1/ipam/GetIpInfo/ip={bu_ip}"
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    if isinstance(data, str):
                        data = json.loads(data)
        except Exception as err:
            msg = f"Exception connecting {url} {err}"
            await raise_exception(msg)
        if resp.status != 200:
            msg = f"fail response from {url} response_code: {resp.status} resp_text: {await resp.text()}"
            await raise_exception(msg)
        ip_data = next(iter(data))
        bu["BU_SERVERNAME"] = bu_servername
        bu["BU_IP"] = bu_ip
        bu["BU_NETMASK"] = ip_data["Mask"]
        bu["BU_GATEWAY"] = ip_data["Gateway"]
    else:
        bu["BU_NONE"] = "No backup interface"
    return bu
