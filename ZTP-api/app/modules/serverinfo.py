# -*- coding: utf-8 -*-

"""serverinfo
- Get server information from /Systems
"""

import asyncio
import logging
import os
import sys
import time

import aiohttp
from ldap3.utils.conv import escape_filter_chars

from app.modules._helper import BuildStatuses, cleanup_my_dict, set_min_networkdata
from app.modules.cache import CREDS

logger = logging.getLogger(__name__)


async def serverinfo(servername):
    """Fn: create async task for serverinfo"""
    task = asyncio.create_task(fetch_server_info(servername))
    return await task


# async def get_serverinfo(servername):
#     """Fn: get serverinfo with redfish data from server"""
#     servername = servername.lower()
#     server_info = {}
#     try:
#         server_info = await set_min_networkdata(servername)
#         server_info.update(await get_server_rfdata(server_info))
#         server_info.update(STATUS=BuildStatuses.SUCCESS.value)
#     except Exception as err:
#         server_info.update(SERVERNAME=servername)
#         server_info.update(STATUS=BuildStatuses.ERROR.value)
#         exc_type, exc_obj, exc_tb = sys.exc_info()
#         fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
#         server_info.update(ERROR_DETAIL=f"Error: {exc_obj} {exc_type}  {fname} {exc_tb.tb_lineno}")
#         logger.info(f"error: {err} {sys.exc_info()}")
#     finally:
#         server_info.update(TIME=time.strftime("%x %X %Z"))
#         data = {k.upper(): v for k, v in server_info.items()}
#     return data


# async def get_server_rfdata(server_info):
#     """Fn: Get redfish data from server from /systems"""
#     system_rfdata = {}
#     creds = {}
#     if "hp" in server_info["HARDWARE"]:
#         url = escape_filter_chars(f"https://{server_info['LOMIP']}/redfish/v1/Systems/1")
#         creds = CREDS["hp"]
#     if server_info["HARDWARE"] == "dell":
#         url = escape_filter_chars(f"https://{server_info['LOMIP']}/redfish/v1/Systems/System.Embedded.1")
#         creds = CREDS["dell"]
#     if server_info["HARDWARE"] == "quanta":
#         url = escape_filter_chars(f"https://{server_info['LOMIP']}/redfish/v1/Systems/1")
#         creds = CREDS["quanta"]
#     key_list = [
#         "AssetTag",
#         "BiosVersion",
#         "Manufacturer",
#         "MemorySummary",
#         "Model",
#         "PowerState",
#         "ProcessorSummary",
#         "SerialNumber",
#         "SystemType",
#         "TrustedModules",
#     ]
#     good_creds = False
#     for lomuser, lompass in creds.items():
#         try:
#             async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
#                 async with session.get(url, auth=aiohttp.BasicAuth(lomuser, lompass)) as resp:
#                     data = await resp.json()
#         except Exception:
#             msg = f"SI3 Error connecting to redfish endpoint {url}"
#             await raise_exception(msg)
#         if resp.status == 200:
#             good_creds = True
#             system_rfdata.update(LOMUSER=lomuser)
#             for key in key_list:
#                 findme = {k: v for k, v in data.items() if k == key}
#                 if not bool(findme):
#                     findme = {key: "NOT FOUND"}
#                 system_rfdata.update(findme)
#             TotalCores = 0
#             TotalThreads = 0
#             proc_url = f"{url}/Processors"
#             async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
#                 async with session.get(proc_url, auth=aiohttp.BasicAuth(lomuser, lompass)) as resp:
#                     data = await resp.json()
#             if resp.status == 200:
#                 for item in data["Members"]:
#                     url = escape_filter_chars(f"https://{server_info['LOMIP']}{item['@odata.id']}")
#                     async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
#                         async with session.get(url, auth=aiohttp.BasicAuth(lomuser, lompass)) as resp:
#                             data = await resp.json()
#                     if resp.status == 200:
#                         TotalCores += data["TotalCores"]
#                         TotalThreads += data["TotalThreads"]
#                 system_rfdata["ProcessorSummary"].update({"Physicalcores": TotalCores, "Logicalcores": TotalThreads})
#             break

#     if good_creds is False:
#         msg = "SI4 No valid lom creditials found"
#         logger.info(msg)
#         await raise_exception(msg)

#     if not system_rfdata:
#         msg = "SI5 Fail to fetch data from server"
#         logger.info(msg)
#         await raise_exception(msg)
#     server_info = cleanup_my_dict(system_rfdata)
#     return server_info


async def fetch_server_info(servername):
    """Fn: Fetch server information with redfish data"""
    servername = servername.lower()
    server_info = {}
    try:
        # Set minimal network data
        server_info = await set_min_networkdata(servername)
        # Determine hardware type and set URL/credentials
        hardware = server_info.get("HARDWARE", "").lower()
        lomip = server_info.get("LOMIP", "")
        creds = CREDS.get(hardware, {})
        # Fetch redfish data
        key_list = [
            "AssetTag",
            "BiosVersion",
            "Manufacturer",
            "MemorySummary",
            "Model",
            "PowerState",
            "ProcessorSummary",
            "SerialNumber",
            "SystemType",
            "TrustedModules",
        ]
        if hardware in ["hpe", "hp", "quanta"]:
            url = escape_filter_chars(f"https://{lomip}/redfish/v1/Systems/1")
        elif hardware == "dell":
            url = escape_filter_chars(f"https://{lomip}/redfish/v1/Systems/System.Embedded.1")
            # ["Oem"]["Dell"]["ChassisServiceTag"] = server_info.get("ServiceTag", "NOT FOUND")
        else:
            raise ValueError(f"Unsupported hardware type: {hardware}")
        system_rfdata = {}
        good_creds = False
        for lomuser, lompass in creds.items():
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
                    async with session.get(url, auth=aiohttp.BasicAuth(lomuser, lompass)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            good_creds = True
                            system_rfdata.update(LOMUSER=lomuser)
                            for key in key_list:
                                system_rfdata[key] = data.get(key, "NOT FOUND")
                            if hardware == "dell":
                                system_rfdata["ServiceTag"] = (
                                    data.get("Oem", {})
                                    .get("Dell", {})
                                    .get("DellSystem", {})
                                    .get("ChassisServiceTag", "NOT FOUND")
                                )
                                system_rfdata["SerialNumber"] = system_rfdata["ServiceTag"]
                            break
            except Exception:
                logger.info(f"Error connecting to redfish endpoint {url}")
                continue

        if not good_creds:
            raise ValueError("No valid LOM credentials found")

        # Fetch processor data
        TotalCores, TotalThreads = 0, 0
        proc_url = f"{url}/Processors"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
            async with session.get(proc_url, auth=aiohttp.BasicAuth(lomuser, lompass)) as resp:
                if resp.status == 200:
                    proc_data = await resp.json()
                    for item in proc_data.get("Members", []):
                        item_url = escape_filter_chars(f"https://{lomip}{item['@odata.id']}")
                        async with session.get(item_url, auth=aiohttp.BasicAuth(lomuser, lompass)) as item_resp:
                            if item_resp.status == 200:
                                item_data = await item_resp.json()
                                TotalCores += item_data.get("TotalCores", 0)
                                TotalThreads += item_data.get("TotalThreads", 0)
        if "ProcessorSummary" in system_rfdata:
            system_rfdata["ProcessorSummary"].update({"Physicalcores": TotalCores, "Logicalcores": TotalThreads})

        # Clean up and finalize server info
        server_info.update(cleanup_my_dict(system_rfdata))
        server_info.update(STATUS=BuildStatuses.SUCCESS.value)
    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        server_info.update(
            SERVERNAME=servername,
            STATUS=BuildStatuses.ERROR.value,
            ERROR_DETAIL=f"Error: {exc_obj} {exc_type} {fname} {exc_tb.tb_lineno}",
        )
        logger.info(f"Error: {err} {sys.exc_info()}")
    finally:
        server_info.update(TIME=time.strftime("%x %X %Z"))
        return {k.upper(): v for k, v in server_info.items()}
