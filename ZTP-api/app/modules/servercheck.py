# -*- coding: utf-8 -*-

"""servercheck.py
    This module is used to check the ilo against the standard.
    - Check the ilo firmware version
    - Check license status
    # Redfish API endpoints for iLO
    REDFISH_ENDPOINTS = {
        "AccountService": "/redfish/v1/AccountService/",
        "Bios": "/redfish/v1/systems/1/bios/settings/",
        "EthernetInterface": "/redfish/v1/Managers/1/EthernetInterfaces/1/",
        "HpeESKM": "/redfish/v1/Managers/1/SecurityService/ESKM/",
        "HpeiLODateTime": "/redfish/v1/Managers/1/DateTime/",
        "HpeiLOLicense": "/redfish/v1/Managers/1/LicenseService/",
        "HpeiLOSSO": "/redfish/v1/Managers/1/SecurityService/SSO/",
        "Manager": "/redfish/v1/Managers/1/",
        "ManagerAccount": "/redfish/v1/AccountService/Accounts/",
        "ManagerNetworkProtocol": "/redfish/v1/Managers/1/NetworkProtocol/"
    }
"""


import socket
from enum import Enum

import requests
import urllib3
from fastapi.responses import JSONResponse
from ldap3.utils.conv import escape_filter_chars
from requests.auth import HTTPBasicAuth

from app.modules.cache import CREDS
from app.modules._helper import set_min_networkdata

# Disable urllib3 warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Statuses(str, Enum):
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


async def get_oneview_server(ilo: str, username: str = "", password: str = ""):
    """Check if iLO SSO is enabled and return the server name."""
    # Check if iLO is an IP address or a string
    if ilo.replace(".", "").isdigit():
        pass
    else:
        pass
        # Check if it's an FQDN
        if "." in ilo:
            hostname = ilo.split(".")[0]
            if not hostname.endswith("lo"):
                e = f"iLO {ilo} name is not a valid FQDN ending with 'lo'."
                return JSONResponse(status_code=400, content={"status": Statuses.ERROR.value, "error_detail": str(e)})
        else:
            if not ilo.endswith("lo"):
                e = f"iLO {ilo} name is not a valid with 'lo' suffix"
                return JSONResponse(status_code=400, content={"status": Statuses.ERROR.value, "error_detail": str(e)})

    # Check if iLO is resolvable in DNS
    try:
        socket.gethostbyname(ilo)
    except socket.gaierror:
        raise Exception(f"iLO {ilo} is not resolvable in DNS.")

    if not username or not password:
        username, password = "AdminLO", CREDS["hpe"]["AdminLO"]

    try:
        response = await get_ilo_sso_servername(ilo, username, password)
        # return JSONResponse(status_code=200, content={"status": Statuses.SUCCESS.value, "detail": response})
        return {"status": Statuses.SUCCESS.value, "detail": response}
    except Exception as e:
        # return JSONResponse(status_code=400, content={"status": Statuses.ERROR.value, "error_detail": str(e)})
        return {"status": Statuses.ERROR.value, "error_detail": str(e)}


async def get_ilo_sso_servername(ilo, username="", password=""):
    """Retrieve the OneView server name from iLO configuration.

    When a server is monitored by OneView, iLO is configured with SNMPv3 settings,
    Remote Support settings, and SSO Trusted Certificates. This function extracts
    the server name from these configurations via the Redfish API.
    """

    headers = {"Content-Type": "application/json"}
    url = escape_filter_chars(f"https://{ilo}/redfish/v1/Managers/1/SnmpService/SNMPUsers/")
    try:
        response = requests.get(
            url, headers=headers, auth=HTTPBasicAuth(username, password), verify=CREDS["verify"], timeout=10
        )
    except Exception as e:
        raise Exception(f"Error connecting to iLO {ilo}: {str(e)}")
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve SNMP user: {response.status_code} - {response.text}")

    data = response.json()
    # Extract the Members' "@odata.id" values
    members = data.get("Members", [])
    if not members:
        raise Exception("No SNMP users found.")

    # Retrieve the first member's "@odata.id"
    memberid = members[0].get("@odata.id")
    if not memberid:
        raise Exception("SNMP user '@odata.id' not found.")
    url = escape_filter_chars(f"https://{ilo}{memberid}")
    try:
        response = requests.get(
            url, headers=headers, auth=HTTPBasicAuth(username, password), verify=CREDS["verify"], timeout=10
        )
    except Exception as e:
        raise Exception(f"Error connecting to iLO {ilo}: {str(e)}")
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve SNMP user details: {response.status_code} - {response.text}")
    data = response.json()
    # Check if SecurityName exists and starts with "oneview"
    security_name = data.get("SecurityName")
    if not security_name or not security_name.startswith("oneview_"):
        raise Exception("SecurityName is missing or does not start with 'oneview'.")

    url = escape_filter_chars(f"https://{ilo}/redfish/v1/Managers/1/SecurityService/sso/")
    try:
        response = requests.get(
            url, headers=headers, auth=HTTPBasicAuth(username, password), verify=CREDS["verify"], timeout=10
        )
    except Exception as e:
        raise Exception(f"Error connecting to iLO {ilo}: {str(e)}")
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve SSO status: {response.status_code} - {response.text}")
    data = response.json()
    manager_trusted_certificates = data.get("ManagerTrustedCertificates")
    if isinstance(manager_trusted_certificates, list) and manager_trusted_certificates:
        first_item = manager_trusted_certificates[0]
        if first_item.get("Status") == "OK":
            return {
                "SecurityName": security_name,
                "ServerName": first_item.get("ServerName", "Unknown"),
            }
    raise Exception(f"SSO is not enabled or no valid server name found")



### check TPM setting if its visble or not

async def check_ilo_tpm_visibility(host, username="AdminLO", password=CREDS["hpe"]["AdminLO"]):
    """Retrieve the TPM visibility setting from iLO BIOS configuration.

    This function checks if the TPM setting is visible in the iLO Redfish API.
    
    Args:
        ilo: iLO hostname or IP address
        username: iLO username (default: "")
        password: iLO password (default: "")
    
    Returns:
        dict: TPM visibility status and current setting
    """
    networkdata = await set_min_networkdata(host)
    ilo = networkdata.get("LOMIP", "")
    if not ilo:
        raise Exception(f"iLO IP address not found for host {host}")
    headers = {"Content-Type": "application/json"}
    
    # Use the same BIOS endpoint for both generations
    bios_ep = "/redfish/v1/systems/1/bios/settings"
    url = escape_filter_chars(f"https://{ilo}{bios_ep}")
    
    try:
        response = requests.get(
            url, headers=headers, auth=HTTPBasicAuth(username, password), verify=CREDS["verify"], timeout=10
        )
    except Exception as e:
        raise Exception(f"Error connecting to iLO {ilo}: {str(e)}")
    
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve BIOS settings: {response.status_code} - {response.text}")

    data = response.json()
    
    # Check TPM visibility based on generation
    if networkdata.get("GENERATION") == "gen9":
        tpm_visibility = data.get("TpmVisibility", "Unknown")
    else:
        tpm_visibility = data.get("Attributes", {}).get("TpmVisibility", "Unknown")
    
    return {
        "host": host,
        "generation": networkdata.get("GENERATION"),
        "TpmVisibility": tpm_visibility,
    }
