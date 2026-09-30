# -*- coding: utf-8 -*-
"""eskm.py - ESKM operations
Author: David Blasing
"""

import base64
import logging
import re
from datetime import datetime

import aiohttp
from ldap3.utils.conv import escape_filter_chars

from app.common.domain.build_statuses import BuildStatuses
from app.common.service.sanity import is_valid_hostname_or_ip
from app.dto.status_response import StatusResponse
from app.modules._session import create_requests_retry_session
from app.modules.cache import CREDS, HPE_VARIABLES
from app.modules.networkdata import get_infra_data

logger = logging.getLogger(__name__)


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


async def create_payload(dc, gen):
    """Create ESKM payload"""
    account_group = HPE_VARIABLES[gen.lower()]["eskm_group"]
    if dc not in HPE_VARIABLES:
        dc = "SITE_B"

    primary_key_server_address = HPE_VARIABLES[dc]["eskm_pri"]
    secondary_key_server_address = HPE_VARIABLES[dc]["eskm_secondary"]

    update_payload = {
        "PrimaryKeyServerAddress": primary_key_server_address,
        "PrimaryKeyServerPort": 9000,
        "KeyManagerConfig": {
            "ESKMLocalCACertificateName": "company-eskm-local-ca-2035",
            "AccountGroup": account_group,
            "LoginName": HPE_VARIABLES["Global"]["EskmUser"],
            "Password": HPE_VARIABLES["Global"]["EskmPass"],
        },
        "KeyServerRedundancyReq": True,
        "SecondaryKeyServerPort": 9000,
        "SecondaryKeyServerAddress": secondary_key_server_address,
    }
    return update_payload


async def get_eskm_config(session, host):
    """Get current ESKM configuration"""
    logger.info("fn: - get_eskm_config")
    host = host.replace("\n", "").replace("\r", "")
    url = escape_filter_chars(f"https://{host}/redfish/v1/Managers/1/SecurityService/ESKM")
    async with session.get(url, ssl=CREDS["verify"]) as resp:
        response_data = await resp.json()
        if resp.status != 200:
            logger.error(
                f"HOST: {host} - Failed to get ESKM config. Status code: {resp.status}, Response: {response_data}"
            )
        return response_data


def compare_payloads(updated_payload, current_config):
    """Compare updated payload with current ESKM configuration"""
    differences = {}
    for key in updated_payload:
        if key in current_config and updated_payload[key] != current_config[key]:
            if key == "KeyManagerConfig":
                for sub_key in updated_payload[key]:
                    if sub_key not in ["LoginName", "Password"] and updated_payload[key][sub_key] != current_config[
                        key
                    ].get(sub_key):
                        differences[f"{key}.{sub_key}"] = {
                            "standard": updated_payload[key][sub_key],
                            "current": current_config[key].get(sub_key),
                        }
            else:
                differences[key] = {"standard": updated_payload[key], "current": current_config[key]}
    return differences


def print_differences(differences):
    """Print differences in a readable format"""
    if not differences:
        logger.info("Values up to date")
    else:
        logger.info("Differences found:")
        for key, value in differences.items():
            logger.info(f"{key}:")
            logger.info(f"  Standard: {value['standard']}")
            logger.info(f"  Current: {value['current']}")


async def patch_eskm_config(session, host, updated_payload):
    """Patch ESKM configuration"""
    host = host.replace("\n", "").replace("\r", "")
    url = escape_filter_chars(f"https://{host}/redfish/v1/Managers/1/SecurityService/ESKM/")
    async with session.patch(url, json=updated_payload, ssl=CREDS["verify"]) as resp:
        response_data = await resp.json()
        if resp.status == 200:
            logger.info(f"HOST: {host} - Successfully patched ESKM config.")
            filtered_payload = filter_sensitive_info(updated_payload)
            return {"status": "success", "status_detail": str(filtered_payload)}
        else:
            logger.error(
                f"HOST: {host} - Failed to patch ESKM config. Status code: {resp.status}, Response: {response_data}"
            )
            return {
                "status": "error",
                "status_detail": f"Failed to patch ESKM config. Status code: {resp.status}, Response: {response_data}",
            }


async def clear_eskm_log(session, host):
    """Clear ESKM log"""
    logger.info("fn: - clear_eskm_log")
    host = host.replace("\n", "").replace("\r", "")
    url = escape_filter_chars(
        f"https://{host}/redfish/v1/Managers/1/SecurityService/ESKM/Actions/HpeESKM.ClearESKMLog/"
    )
    async with session.post(url, json={}, ssl=CREDS["verify"]) as resp:
        response_data = await resp.json()
        if resp.status != 200:
            logger.error(
                f"HOST: {host} - ESKM - Failed to clear ESKM log. Status code: {resp.status}, Response: {response_data}"
            )
        return response_data


def filter_sensitive_info(payload):
    """Remove sensitive information from the payload"""
    if "KeyManagerConfig" in payload:
        payload["KeyManagerConfig"].pop("Password", None)
        payload["KeyManagerConfig"].pop("LoginName", None)
    return payload


async def eskm_main(host, username=None, password=None, operation="get"):
    """Main function to handle ESKM operations"""
    logger.info("Fn: eskm_main")
    session = None
    # requestor = username if username else "AdminLO"
    status_detail = ""
    metadata = {}
    gen = None  # Initialize gen to a default value

    try:
        lom_ip = await is_valid_hostname_or_ip(host)
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
                # requestor = session.headers.get("User", user)
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
            return StatusResponse(
                status=BuildStatuses.ERROR,
                status_detail=status_detail,
                host=host,
                requestor=requestor,
                time=datetime.utcnow().isoformat(),
                metadata=metadata,
            )

        network_data = await get_infra_data(lom_ip)
        dc = network_data["DC"]
        payload = await create_payload(dc, gen)
        current_config = await get_eskm_config(session, lom_ip)
        differences = compare_payloads(payload, current_config)

        if differences:
            if operation == "get":
                status_detail = "Differences found, configuration is not up to date."
                metadata = differences
                return StatusResponse(
                    status=BuildStatuses.WARNING,
                    status_detail=status_detail,
                    host=host,
                    requestor=requestor,
                    time=datetime.utcnow().isoformat(),
                    metadata=metadata,
                )
            else:
                logger.info(f"Current ESKM Config: {current_config}")
                await clear_eskm_log(session, lom_ip)
                patch_response = await patch_eskm_config(session, lom_ip, payload)
                if patch_response["status"] == "error":
                    status_detail = patch_response["status_detail"]
                    return StatusResponse(
                        status=BuildStatuses.ERROR,
                        status_detail=status_detail,
                        host=host,
                        requestor=requestor,
                        time=datetime.utcnow().isoformat(),
                        metadata=metadata,
                    )
                status_detail = patch_response["status_detail"]
        else:
            status_detail = "No differences found, configuration is up to date."
            return StatusResponse(
                status=BuildStatuses.UNCHANGED,
                status_detail=status_detail,
                host=host,
                requestor=requestor,
                time=datetime.utcnow().isoformat(),
                metadata=metadata,
            )

        return StatusResponse(
            status=BuildStatuses.SUCCESS,
            status_detail=status_detail,
            host=host,
            requestor=requestor,
            time=datetime.utcnow().isoformat(),
            metadata=metadata,
        )
    except Exception as e:
        status_detail = str(e)
        logger.error(f"Unexpected error: {status_detail}")
    finally:
        if session:
            await session.close()

    return StatusResponse(
        status=BuildStatuses.ERROR,
        status_detail=status_detail,
        host=host,
        requestor=requestor,
        time=datetime.utcnow().isoformat(),
        metadata=metadata,
    )
