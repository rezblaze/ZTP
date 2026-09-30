import base64
import logging
from typing import Dict, Optional

import aiohttp
from ldap3.utils.conv import escape_filter_chars

from app.modules._session import create_requests_retry_session, delete_session
from app.modules.cache import CREDS

logger = logging.getLogger(__name__)


class InvalidCredentialsError(Exception):
    """Exception raised for invalid credentials."""


async def get_gen(host, lomuser, lompass):
    """Get system model"""
    host = host.replace("\n", "").replace("\r", "")
    url = escape_filter_chars(f"https://{host}/redfish/v1/Systems/1")
    auth = aiohttp.BasicAuth(lomuser, lompass)
    async with aiohttp.ClientSession(auth=auth) as session:
        async with session.get(url, ssl=CREDS["verify"]) as resp:
            response_data = await resp.json()
            if resp.status != 200:
                logger.error(
                    f"HOST: {host} - Failed to get system model. Status code: {resp.status}, Response: {response_data}"
                )
                return "Gen not found"
            model = response_data.get("Model", "Model not found")
            match = re.search(r"Gen\d+", model)
            if match:
                return match.group()
            else:
                return "Gen not found"


async def fetch_data(session: aiohttp.ClientSession, host: str, endpoint: str) -> dict:
    """Fetch data from a given endpoint using the authenticated session."""
    host = host.replace("\n", "").replace("\r", "")
    url = escape_filter_chars(f"https://{host}{endpoint}")
    async with session.get(url, ssl=CREDS["verify"], timeout=aiohttp.ClientTimeout(total=10)) as resp:
        response_data = await resp.json()
        if resp.status != 200:
            logger.error(f"Failed to fetch data from {endpoint}. Status: {resp.status}, Response: {response_data}")
            return {"error": f"Failed to fetch data from {endpoint}"}
        logger.info(f"Fetched data from {endpoint}: {response_data}")
        return response_data


async def fetch_nested_data(session: aiohttp.ClientSession, host: str, endpoint: str) -> dict:
    """Fetch nested data from endpoints with members."""
    data = await fetch_data(session, host, endpoint)
    if "Members" in data:
        nested_data = {}
        for member in data["Members"]:
            member_data = await fetch_data(session, host, member["@odata.id"])
            # Remove @odata items from member data
            member_data_cleaned = {k: v for k, v in member_data.items() if not k.startswith("@odata")}
            nested_data[member["@odata.id"]] = member_data_cleaned
        return nested_data
    return data


async def gather_all_data(host: str, session: aiohttp.ClientSession, endpoints: Dict[str, bool]) -> dict:
    """Gather data from all specified endpoints using the same authenticated session."""
    all_endpoints = {
        "AccountService": "/redfish/v1/AccountService/",
        "Bios": "/redfish/v1/systems/1/bios/settings/",
        "EthernetInterface": "/redfish/v1/Managers/1/EthernetInterfaces/1/",
        "HpeESKM": "/redfish/v1/Managers/1/SecurityService/ESKM/",
        "HpeiLODateTime": "/redfish/v1/Managers/1/DateTime/",
        "HpeiLOLicense": "/redfish/v1/Managers/1/LicenseService/",
        "HpeiLOSSO": "/redfish/v1/Managers/1/SecurityService/SSO/",
        "Manager": "/redfish/v1/Managers/1/",
        "ManagerAccount": "/redfish/v1/AccountService/Accounts/",
        "ManagerNetworkProtocol": "/redfish/v1/Managers/1/NetworkProtocol/",
        "EthernetInterfaces": "/redfish/v1/Systems/1/EthernetInterfaces/",
        "Storage": "/redfish/v1/Systems/1/Storage/",
        "Memory": "/redfish/v1/Systems/1/Memory/",
        "Processors": "/redfish/v1/Systems/1/Processors/",
    }

    data = {}
    for name, endpoint in all_endpoints.items():
        if endpoints.get(name, True):
            data[name] = await fetch_data(session, host, endpoint)

    # Fetch nested firmware and software inventory data if requested
    if endpoints.get("FirmwareInventory", True):
        firmware_data = await fetch_nested_data(session, host, "/redfish/v1/UpdateService/FirmwareInventory")
        data["FirmwareInventory"] = firmware_data

    if endpoints.get("SoftwareInventory", True):
        software_data = await fetch_nested_data(session, host, "/redfish/v1/UpdateService/SoftwareInventory")
        data["SoftwareInventory"] = software_data

    # Fetch nested EthernetInterfaces data
    if endpoints.get("EthernetInterfaces", True):
        ethernet_data = await fetch_nested_data(session, host, "/redfish/v1/Systems/1/EthernetInterfaces")
        data["EthernetInterfaces"] = ethernet_data

    # Fetch nested Storage data
    if endpoints.get("Storage", True):
        storage_data = await fetch_nested_data(session, host, "/redfish/v1/Systems/1/Storage")
        data["Storage"] = storage_data

    # Fetch nested Memory data
    if endpoints.get("Memory", True):
        memory_data = await fetch_nested_data(session, host, "/redfish/v1/Systems/1/Memory")
        data["Memory"] = memory_data

    # Fetch nested Processors data
    if endpoints.get("Processors", True):
        processors_data = await fetch_nested_data(session, host, "/redfish/v1/Systems/1/Processors")
        data["Processors"] = processors_data

    return data


async def fetch_endpoint_data(
    host: str, endpoints: Dict[str, bool], username: Optional[str] = None, password: Optional[str] = None
) -> dict:
    """Fetch endpoint data by creating and closing session using _session.py module."""
    session = None
    status_detail = ""
    metadata = {}
    gen = None  # Initialize gen to a default value
    host = host.replace("\n", "").replace("\r", "")
    try:
        lom_ip = escape_filter_chars(host)
        # Decode base64 credentials if provided
        try:
            lomuser = base64.b64decode(username).decode("utf-8") if username else None
            lompass = base64.b64decode(password).decode("utf-8") if password else None
        except Exception as e:
            logger.error(f"Error decoding base64 credentials: {e}")
            lomuser = username
            lompass = password

        # Use AdminLO user by default if only password is provided
        if lompass and not lomuser:
            lomuser = "AdminLO"

        # Validate credentials and get system generation
        default_credentials = [
            ("AdminLO", CREDS["hpe"]["AdminLO"]),
            ("maas_oob@example.com", CREDS["hpe"]["maas_oob@example.com"]),
        ]
        credentials = [(lomuser, lompass)] if lomuser or lompass else default_credentials
        requestor = lomuser
        for user, pwd in credentials:
            requestor = user
            try:
                session = await create_requests_retry_session(lom_ip, user, pwd)
                if not session:
                    continue
                gen = await get_gen(lom_ip, user, pwd)
                if "Error" not in gen:
                    break
            except Exception as e:
                status_detail = str(e)
                logger.error(f"Unexpected error: {status_detail}")
                break
        else:
            session = None
            status_detail = "Credential validation failed"

        if not session:
            return {
                "status": "ERROR",
                "status_detail": status_detail,
                "host": host,
                "requestor": requestor,
                "metadata": metadata,
            }

        # Gather all data from specified endpoints
        data = await gather_all_data(host, session, endpoints)
        return {"data": data, "session_id": session.headers.get("X-Auth-Token")}

    except Exception as e:
        logger.error(f"Error in fetching endpoint data for host {host}: {e}")
        return {"error": f"Error in fetching endpoint data for host {host}: {str(e)}"}
    finally:
        if session:
            await delete_session(session)
