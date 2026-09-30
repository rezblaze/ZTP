import logging

import requests
import urllib3
from ldap3.utils.conv import escape_filter_chars

from app.build_service.cache import CREDS
from app.ZTP._common import if_resp_not_ok, log_my_msg

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "PATCH"])

retry = urllib3.util.retry.Retry(
    total=5,
    read=5,
    connect=5,
    backoff_factor=16,
    status_forcelist=(
        400,
        404,
        500,
        502,
        503,
        504,
        ConnectionError,
        TimeoutError,
        ConnectionResetError,
        RuntimeError,
    ),
    allowed_methods=DEFAULT_ALLOWED_METHODS,
)


class InvalidCredentialsError(Exception):
    """Exception raised for invalid credentials."""


class HostUnreachableError(Exception):
    """Exception raised when the host is unreachable."""


class RequestTimeoutError(Exception):
    """Exception raised when the request times out."""


def create_requests_retry_session(lom, lomuser, lompass):
    """Create request retry session and get xauth token"""
    end_point = "/redfish/v1/SessionService/Sessions"
    payload = {"UserName": lomuser, "Password": lompass}
    headers = {"content-type": "application/json"}
    try:
        resp = requests.post(
            f"https://{escape_filter_chars(lom)}{end_point}",
            json=payload,
            headers=headers,
            verify=CREDS["verify"],
            timeout=10,
        )
        if resp.status_code == 401:
            logger.error("Invalid credentials provided.")
            raise InvalidCredentialsError("Invalid credentials provided.")
        elif resp.status_code not in (200, 201):
            logger.error(f"Failed to get X-Auth-Token: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        x_auth_token = resp.headers["X-Auth-Token"]
        location = resp.headers["Location"]
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(
            {
                "X-Auth-Token": x_auth_token,
                "content-type": "application/json",
                "User": lomuser,
                "Location": (
                    location if location.startswith("https") else f"https://{escape_filter_chars(lom)}{location}"
                ),
            }
        )
        session.verify = False
        return session
    except requests.Timeout as e:
        logger.error(f"Request timed out: {e}")
        raise RequestTimeoutError("Request timed out.")
    except requests.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        raise HostUnreachableError("Host is unreachable.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise Exception(e)


def delete_session(session):
    """Delete session"""
    location = session.headers["Location"]
    try:
        resp = session.delete(
            location,
            verify=CREDS["verify"],
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.error(f"Failed to delete session: {resp.status_code} {resp.text}")
            resp.raise_for_status()
    except requests.Timeout as e:
        logger.error(f"Request timed out: {e}")
        raise RequestTimeoutError("Request timed out.")
    except requests.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        raise HostUnreachableError("Host is unreachable.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise Exception(e)
    finally:
        session.close()


def create_requests_retry_no_token_auth():
    """Fn: create request retry session no auth"""
    no_token_session = requests.Session()
    # retry = urllib3.util.retry.Retry(
    #     total=5,
    #     read=5,
    #     connect=5,
    #     backoff_factor=16,
    #     status_forcelist=(
    #         400,
    #         404,
    #         500,
    #         502,
    #         503,
    #         504,
    #         ConnectionError,
    #         TimeoutError,
    #         ConnectionResetError,
    #         RuntimeError,
    #     ),
    #     allowed_methods=DEFAULT_ALLOWED_METHODS,
    # )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    no_token_session.mount("http://", adapter)
    no_token_session.mount("https://", adapter)
    no_token_session.headers.update({"content-type": "application/json"})
    no_token_session.verify = False
    return no_token_session


def get_hpe_hardware_model(lom, session):
    """Fn: Get hpe mode like proliant dl380 gen9"""
    log_my_msg("Fn: get_hpe_hardware_model")
    url = f"https://{lom}/redfish/v1/Chassis/1"
    resp = session.get(url, verify=CREDS["verify"], timeout=10)
    if_resp_not_ok(resp)
    data = resp.json()
    return data["Model"].lower()
