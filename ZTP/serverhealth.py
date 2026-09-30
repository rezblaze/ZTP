# -*- coding: utf-8 -*-

""" check server health
"""

import logging

from ._common import log_my_msg
from ._healthcheck import (
    check_host_port,
    get_esxi_info_with_ssh,
    get_rhel_info_with_ssh,
)
from .secrets import get_baseos_creds

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)


def esxi_server_health(ip_address, user="", passphrase=""):
    """Fn: esxi_server_health - check ESXi server health function"""
    logger.info("Fn: esxi_server_health")
    check_host_port(ip_address, 22)
    check_host_port(ip_address, 443)
    if user == "" and passphrase == "":
        esxicred = get_baseos_creds("esxi")
        user_pass = next(iter((esxicred.items())))
    get_esxi_info_with_ssh(ip_address, user_pass[0], user_pass[1])


def rhel_server_health(ip_address, user="", passphrase=""):
    """Fn: rhel_server_health - check RHEL server health function"""
    log_my_msg("Fn: rhel_server_health")
    check_host_port(ip_address, 22)
    if user == "" and passphrase == "":
        rhelcreds = get_baseos_creds("rhel")
        user_pass = next(iter((rhelcreds.items())))
    get_rhel_info_with_ssh(ip_address, user_pass[0], user_pass[1])
