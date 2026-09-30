import asyncio
import socket

import aiohttp
import validators
from fastapi import HTTPException
from ldap3.utils.conv import escape_filter_chars

from app.common.domain.build_statuses import BuildStatuses
from app.modules.cache import CREDS


async def isloname(host):
    return host.split(".")[0][-2:] == "lo"


async def check_dns(host):
    try:
        socket.gethostbyname(host)
        exist = True
    except Exception:
        exist = False
    return exist


async def sanity_check(host):
    hostname = host.lower().strip()
    islo = await isloname(hostname)
    if islo is True:
        raise HTTPException(status_code=405, detail="Not Allowed, host name provided appears to be lom/management name")
    exist = await check_dns(hostname)
    if exist is False:
        raise HTTPException(status_code=412, detail="Host is not in corporate DNS")
    return hostname


async def check_power(serverinfo):
    if serverinfo["STATUS"] == BuildStatuses.ERROR.value:
        raise HTTPException(status_code=424, detail=f"Error received from /serverinfo: {serverinfo['ERROR_DETAIL']}")
    if serverinfo["POWERSTATE"].lower() == "on":
        raise HTTPException(
            status_code=424, detail="Power requirement failed! Server power status is ON. Power it OFF and retry!"
        )


async def check_api_endpoint(lom):
    url = escape_filter_chars(f"https://{lom}/redfish/v1/")
    timeout = aiohttp.ClientTimeout(total=2)  # Set a timeout of 2 seconds
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, ssl=CREDS["verify"]) as response:
                if response.status == 200:
                    data = await response.json()
                    vendor = data.get("Vendor", "Unknown")

                    if vendor != "Unknown" and "hp" not in vendor.lower():
                        return {"error": f"Not a valid iLO - Vendor shows {vendor}"}

                    oem_data_hpe = data.get("Oem", {}).get("Hpe", {})
                    oem_data_hp = data.get("Oem", {}).get("Hp", {})

                    manager_list_hpe = oem_data_hpe.get("Manager", [])
                    manager_list_hp = oem_data_hp.get("Manager", [])

                    if manager_list_hpe:
                        manager_type = manager_list_hpe[0].get("ManagerType", "Unknown")
                    elif manager_list_hp:
                        manager_type = manager_list_hp[0].get("ManagerType", "Unknown")
                    else:
                        return {"error": "No valid iLO found - Manager list is empty"}

                    if "iLO" not in manager_type:
                        return {"error": "Not a valid iLO - Invalid Manager Type"}

                    return {"ilo_version": manager_type}
                elif response.status == 404:
                    return {"error": f"API endpoint not found for iLO {lom}"}
                else:
                    return {"error": f"API endpoint returned status code {response.status}"}
        except asyncio.TimeoutError:
            return {"error": "iLO not reachable after timeout"}


async def is_valid_hostname_or_ip(host):
    if validators.ipv4(host):
        return host
    elif validators.domain(host):
        try:
            loop = asyncio.get_event_loop()
            ip_address = await loop.run_in_executor(None, socket.gethostbyname, host)
            return ip_address
        except socket.error as e:
            raise HTTPException(status_code=412, detail=f"Failed to get IP for {host} exception: {e}")
    else:
        raise HTTPException(status_code=412, detail=f"Invalid hostname or IP: {host}")


# async def ilo_sanity_check(lom):
#     lom_ip = await is_valid_hostname_or_ip(lom)
#     api_status = await check_api_endpoint(lom)
#     if "error" in api_status:
#         raise HTTPException(status_code=400, detail=api_status["error"])
#     return [lom_ip, api_status]
