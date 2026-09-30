# -*- coding: utf-8 -*-
"""adminlo.py
- Admin routes for sync and login

Author: Chirag Patel
"""

import asyncio
import base64
import logging
from datetime import datetime
from enum import Enum

import aiohttp
from ldap3.utils.conv import escape_filter_chars
from pydantic import BaseModel

from app import logger
from app.modules.cache import CREDS

from ._helper import get_redfish_v1, raise_exception
from ._session import create_requests_retry_session, delete_session


class Statuses(str, Enum):
    ERROR = "ERROR"
    PASS = "PASS"
    FAIL = "FAIL"
    SUCCESS = "SUCCESS"
    NONE = "NONE"


class StatusResponse(BaseModel):
    status: Statuses = Statuses.NONE.value
    host: str = ""
    status_detail: str = ""
    requestor: str = ""
    metadata: dict = {}
    time: str = ""


logger = logging.getLogger(__name__)


class AdminLOManager:
    def __init__(self):
        self.adminlo_user = "AdminLO"
        self.adminlo_creds = CREDS["hpe"]["AdminLO"]
        self.bmi_user = "maas_oob@example.com"
        self.bmi_user_creds = CREDS["hpe"][self.bmi_user]

    ###
    ### Check AdminLO account
    ###

    async def check_adminlo_creds(self, hostname):
        """Check AdminLO account credentials."""
        curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            resp = await self._check_login(hostname, self.adminlo_user, self.adminlo_creds)
            if resp == "pass":
                return StatusResponse(
                    status=Statuses.PASS.value,
                    status_detail="AdminLO password is current.",
                    host=hostname,
                    requestor=self.adminlo_user,
                    time=curr_time,
                )
            elif resp == "fail":
                return StatusResponse(
                    status=Statuses.FAIL.value,
                    status_detail="AdminLO password is NOT current, failed to login.",
                    host=hostname,
                    requestor=self.adminlo_user,
                    time=curr_time,
                )
        except Exception as err:
            logger.error(f"Error: {err}")
            return StatusResponse(
                status=Statuses.ERROR.value,
                status_detail=f"Exception: {err}",
                host=hostname,
                requestor=self.adminlo_user,
                time=curr_time,
            )

    async def _check_login(self, lom, lomuser, lompass):
        """Test AdminLO account login."""
        url = escape_filter_chars(f"https://{lom}/redfish/v1/Managers/")
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
                async with session.get(url, auth=aiohttp.BasicAuth(lomuser, lompass)) as resp:
                    return self._map_response_status(resp.status)
        except aiohttp.ClientResponseError as err:
            await raise_exception(f"Client Response Error: {err}")
        except aiohttp.ClientConnectorError as err:
            await raise_exception(f"DNS Error: {err}")
        except asyncio.TimeoutError as err:
            await raise_exception(f"Timeout Error: {err}")
        except Exception as err:
            await raise_exception(f"Generic Exception: {err}")

    ###
    ### Patch for AdminLO account
    ###

    async def patch_creds(self, lom, username=None, password=None):
        """Patch AdminLO account credentials."""
        curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lomuser, lompass = self._decode_credentials(username, password)
        try:
            session = await create_requests_retry_session(lom, lomuser, lompass)
        except Exception as err:
            return StatusResponse(
                status=Statuses.ERROR.value,
                host=lom,
                status_detail=f"Exception: {err}",
                requestor=lomuser,
                time=curr_time,
            )
        return await self._patch_adminlo_account(lom, session, lomuser, curr_time)

    async def _patch_adminlo_account(self, lom, session, lomuser, curr_time):
        """Helper to patch AdminLO account."""
        url = escape_filter_chars(f"https://{lom}/redfish/v1/AccountService/Accounts/")
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data["Members"]:
                        user_ep = item["@odata.id"]
                        if await self._update_adminlo_password(lom, session, user_ep):
                            return StatusResponse(
                                status=Statuses.SUCCESS.value,
                                host=lom,
                                status_detail="AdminLO account patched",
                                requestor=lomuser,
                                time=curr_time,
                            )
            return StatusResponse(
                status=Statuses.FAIL.value,
                host=lom,
                status_detail="AdminLO account not found",
                requestor=lomuser,
                time=curr_time,
            )
        finally:
            if session:
                await delete_session(session)

    async def _update_adminlo_password(self, lom, session, user_ep):
        """Update AdminLO password."""
        url = escape_filter_chars(f"https://{lom}{user_ep}")
        async with session.get(url) as resp:
            if resp.status == 200:
                data_user = await resp.json()
                if data_user["UserName"] == "AdminLO":
                    async with session.patch(url, json={"Password": self.adminlo_creds}) as patch_resp:
                        return patch_resp.status == 200
        return False

    ###
    ### Add AdminLO account
    ###

    async def add_adminlo_account(self, lom, username=None, password=None):
        """Add AdminLO account."""
        adminlo_found = False
        session = None
        lomuser, lompass = self._decode_credentials(username, password)
        curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            session = await create_requests_retry_session(lom, lomuser, lompass)
            url = escape_filter_chars(f"https://{lom}/redfish/v1/AccountService/Accounts/")
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data["Members"]:
                        user_ep = item["@odata.id"]
                        async with session.get(escape_filter_chars(f"https://{lom}{user_ep}")) as user_resp:
                            if user_resp.status == 200:
                                user_data = await user_resp.json()
                                if user_data["UserName"] == "AdminLO":
                                    adminlo_found = True
                                    resp = await self.check_adminlo_creds(lom)
                                    if resp.status == Statuses.PASS.value:
                                        return StatusResponse(
                                            status=Statuses.PASS.value,
                                            host=lom,
                                            status_detail="AdminLO account already exists and password is current",
                                            requestor=lomuser,
                                            time=curr_time,
                                        )
                                    else:
                                        return StatusResponse(
                                            status=Statuses.FAIL.value,
                                            host=lom,
                                            status_detail="AdminLO account already exists but password is not current",
                                            requestor=lomuser,
                                            time=curr_time,
                                        )
        except Exception as err:
            return StatusResponse(
                status=Statuses.ERROR.value,
                host=lom,
                status_detail=f"Exception: {err}",
                requestor=lomuser,
                time=curr_time,
            )
        finally:
            if session:
                await delete_session(session)

        if not adminlo_found:
            try:
                resp = await self._add_adminlo_account(lom, lomuser, lompass)
                return self._generate_status_response(
                    resp, lom, lomuser, curr_time, success_msg="AdminLO account added"
                )
            except Exception as err:
                return StatusResponse(
                    status=Statuses.ERROR.value,
                    host=lom,
                    status_detail=f"Exception: {err}",
                    requestor=lomuser,
                    time=curr_time,
                )

    async def _add_adminlo_account(self, lom, lomuser, lompass):
        """Helper to add AdminLO account."""
        data = await get_redfish_v1(lom)
        vendor = next(iter(data["Oem"])).lower()
        payload = self._generate_payload(vendor)
        if "hp" in vendor:
            url = escape_filter_chars(f"https://{lom}/redfish/v1/AccountService/Accounts/")
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
                    async with session.post(url, auth=aiohttp.BasicAuth(lomuser, lompass), json=payload) as resp:
                        return self._map_response_status(resp.status)
            except Exception as err:
                await raise_exception(f"Error creating user AdminLO {url} {err}")
        if vendor == "dell":
            url = escape_filter_chars(f"https://{lom}/redfish/v1/Managers/iDRAC.Embedded.1/Accounts/2")
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=CREDS["verify"])) as session:
                    async with session.patch(url, auth=aiohttp.BasicAuth(lomuser, lompass), json=payload) as resp:
                        return self._map_response_status(resp.status)
            except Exception as err:
                await raise_exception(f"Error creating user AdminLO {url} {err}")

    def _generate_payload(self, vendor):
        """Generate payload based on vendor."""
        if "hp" in vendor:
            if vendor == "hpe":
                return {
                    "Oem": {"Hpe": {"LoginName": "AdminLO"}},
                    "Password": self.adminlo_creds,
                    "RoleId": "Administrator",
                    "UserName": "AdminLO",
                }
            if vendor == "hp":
                return {
                    "Oem": {
                        "Hp": {
                            "LoginName": "AdminLO",
                            "Privileges": {
                                "LoginPriv": True,
                                "RemoteConsolePriv": True,
                                "UserConfigPriv": True,
                                "VirtualMediaPriv": True,
                                "VirtualPowerAndResetPriv": True,
                                "iLOConfigPriv": True,
                            },
                        }
                    },
                    "Password": self.adminlo_creds,
                    "UserName": "AdminLO",
                }
        elif vendor == "dell":
            return {"UserName": "AdminLO", "Password": self.adminlo_creds, "RoleId": "Administrator", "Enabled": True}

    ###
    ### Remove CompanyLO account
    ###

    async def remove_companylo_account(self, lom, username=None, password=None):
        """Remove CompanyLO account."""
        lomuser, lompass = self._decode_credentials(username, password)
        curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            session = await create_requests_retry_session(lom, lomuser, lompass)
        except Exception as err:
            return StatusResponse(
                status=Statuses.ERROR.value,
                host=lom,
                status_detail=f"Exception: {err}",
                requestor=lomuser,
                time=curr_time,
            )
        return await self._delete_companylo_account(lom, session, lomuser, curr_time)

    async def _delete_companylo_account(self, lom, session, lomuser, curr_time):
        """Helper to delete CompanyLO account."""
        data = await get_redfish_v1(lom)
        vendor = next(iter(data["Oem"])).lower()
        if vendor == "dell":
            url = escape_filter_chars(f"https://{lom}/redfish/v1/Managers/iDRAC.Embedded.1/Accounts/")
        else:
            url = escape_filter_chars(f"https://{lom}/redfish/v1/AccountService/Accounts/")
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data["Members"]:
                        user_ep = item["@odata.id"]
                        if await self._delete_user_if_companylo(lom, session, user_ep, vendor):
                            return StatusResponse(
                                status=Statuses.SUCCESS.value,
                                host=lom,
                                status_detail="CompanyLO account removed",
                                requestor=lomuser,
                                time=curr_time,
                            )
            return StatusResponse(
                status=Statuses.FAIL.value,
                host=lom,
                status_detail="CompanyLO account not found",
                requestor=lomuser,
                time=curr_time,
            )
        finally:
            if session:
                await delete_session(session)

    async def _delete_user_if_companylo(self, lom, session, user_ep, vendor):
        """Delete user if it is CompanyLO."""
        url = escape_filter_chars(f"https://{lom}{user_ep}")
        async with session.get(url) as resp:
            if resp.status == 200:
                data_user = await resp.json()
                if data_user["UserName"] == "CompanyLO" or data_user["UserName"] == "companylo":
                    if vendor == "dell":
                        url = escape_filter_chars(
                            f"https://{lom}/redfish/v1/Managers/iDRAC.Embedded.1/Oem/Dell/DellAttributes/iDRAC.Embedded.1"
                        )
                        payload = {
                            "Attributes": {
                                "Users.%s.UserName" % data_user["Id"]: "",
                                "Users.%s.Privilege" % data_user["Id"]: 0,
                                "Users.%s.Enable" % data_user["Id"]: "Disabled",
                                "Users.%s.IPMIKey" % data_user["Id"]: "",
                                "Users.%s.MD5v3Key" % data_user["Id"]: "",
                                "Users.%s.SHA1v3Key" % data_user["Id"]: "",
                                "Users.%s.SHA256PasswordSalt" % data_user["Id"]: "",
                            }
                        }
                        async with session.patch(url, json=payload) as delete_resp:
                            return delete_resp.status == 200
                    else:
                        async with session.delete(url) as delete_resp:
                            return delete_resp.status == 200
        return False

    ###
    ### Helper functions
    ###

    def _decode_credentials(self, username, password):
        """Decode credentials if provided, else use default."""
        if username and password:
            try:
                return base64.b64decode(username).decode("utf-8"), base64.b64decode(password).decode("utf-8")
            except:
                logger.warning(
                    "Warning: base64 decoding username or password failed so assuming credentials are coming from swagger as string"
                )
        return self.bmi_user, self.bmi_user_creds

    def _map_response_status(self, status):
        """Map HTTP status to response."""
        if status == 200:
            return "pass"
        elif status == 201:
            return "pass"
        elif status == 401:
            return "fail"
        return "error"

    def _generate_status_response(self, resp, host, requestor, curr_time, success_msg="Operation successful"):
        """Generate a status response based on the result."""
        if resp == "pass":
            return StatusResponse(
                status=Statuses.SUCCESS.value,
                status_detail=success_msg,
                host=host,
                requestor=requestor,
                time=curr_time,
            )
        elif resp == "fail":
            return StatusResponse(
                status=Statuses.FAIL.value,
                status_detail="Operation failed",
                host=host,
                requestor=requestor,
                time=curr_time,
            )
        else:
            return StatusResponse(
                status=Statuses.ERROR.value,
                status_detail=f"Error: {resp}",
                host=host,
                requestor=requestor,
                time=curr_time,
            )


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
