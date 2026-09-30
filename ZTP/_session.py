# -*- coding: utf-8 -*-

""" session.py
"""

__author__ = "David Blasing, Chirag Patel"
__email__ = "david_m_blasing@example.com, chirag_patel@example.com"

import json
import logging

import requests
import urllib3

from ._common import if_resp_not_ok

logger = logging.getLogger(__name__)
DEFAULT_ALLOWED_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "PATCH"])


def get_xauth_token(lom, lomuser, lompass):
    """Fn: Get xauth token"""
    end_point = "/redfish/v1/SessionService/Sessions"
    payload = {"UserName": f"{lomuser}", "Password": f"{lompass}"}
    headers = {"content-type": "application/json"}
    resp = requests.post(
        f"https://{lom}{end_point}",
        data=json.dumps(payload),
        headers=headers,
        verify=False,
    )
    if_resp_not_ok(resp)
    # xlocation = response.headers.__getitem__('Location')
    return resp.headers.__getitem__("X-Auth-Token")


def create_requests_retry_session(lom, lomuser, lompass):
    """Fn: create request retry session"""
    x_auth_token = get_xauth_token(lom, lomuser, lompass)
    session = requests.Session()
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
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"X-Auth-Token": f"{x_auth_token}", "content-type": "application/json"})
    session.verify = False
    return session


def create_requests_retry_no_token_auth():
    """Fn: create request retry session no auth"""
    no_token_session = requests.Session()
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
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    no_token_session.mount("http://", adapter)
    no_token_session.mount("https://", adapter)
    no_token_session.headers.update({"content-type": "application/json"})
    no_token_session.verify = False
    return no_token_session
