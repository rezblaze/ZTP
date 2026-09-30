import asyncio
import logging

import aiohttp
from ldap3.utils.conv import escape_filter_chars

from app.modules.cache import CREDS

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "PATCH"])


class InvalidCredentialsError(Exception):
    """Exception raised for invalid credentials."""


class HostUnreachableError(Exception):
    """Exception raised when the host is unreachable."""


class RequestTimeoutError(Exception):
    """Exception raised when the request times out."""


async def create_requests_retry_session(lom, lomuser, lompass):
    """Create request retry session and get xauth token"""
    end_point = "/redfish/v1/SessionService/Sessions"
    payload = {"UserName": lomuser, "Password": lompass}
    headers = {"content-type": "application/json"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"https://{escape_filter_chars(lom)}{end_point}",
                json=payload,
                headers=headers,
                ssl=CREDS["verify"],
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    logger.error("Invalid credentials provided.")
                    raise InvalidCredentialsError("Invalid credentials provided.")
                elif resp.status not in (200, 201):
                    logger.error(f"Failed to get X-Auth-Token: {resp.status} {await resp.text()}")
                    resp.raise_for_status()
                x_auth_token = resp.headers["X-Auth-Token"]
                location = resp.headers["Location"]
            return aiohttp.ClientSession(
                headers={
                    "X-Auth-Token": x_auth_token,
                    "content-type": "application/json",
                    "User": lomuser,
                    "Location": (
                        location if location.startswith("https") else f"https://{escape_filter_chars(lom)}{location}"
                    ),
                },
                connector=aiohttp.TCPConnector(ssl=CREDS["verify"]),
            )
        except asyncio.TimeoutError as e:
            logger.error(f"Request timed out: {e}")
            raise RequestTimeoutError("Request timed out.")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            raise HostUnreachableError("Host is unreachable.")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Exception(e)


async def delete_session(session):
    """Delete session"""
    location = session.headers["Location"]
    try:
        async with session.delete(
            location,
            ssl=CREDS["verify"],
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status not in (200, 201):
                logger.error(f"Failed to delete session: {resp.status} {await resp.text()}")
                resp.raise_for_status()
    except asyncio.TimeoutError as e:
        logger.error(f"Request timed out: {e}")
        raise RequestTimeoutError("Request timed out.")
    except aiohttp.ClientError as e:
        logger.error(f"HTTP request failed: {e}")
        raise HostUnreachableError("Host is unreachable.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise Exception(e)
    finally:
        await session.close()
