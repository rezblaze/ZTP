# -*- coding: utf-8 -*-

"""
sanitycheck.py - DNS check, ping test etc
"""

__author__ = "David Blasing, Chirag Patel"
__email__ = "support@example.com"


import ipaddress
import logging
import os
import socket

from ._common import log_my_msg

logger = logging.getLogger(__name__)


def check_if_host_in_dns(servername):
    """Fn: check_if_host_in_dns"""
    try:
        socket.gethostbyname(servername)
        exist = True
    except:
        exist = False
    finally:
        log_my_msg(f"{servername}: host in corporate dns => {exist}")
    return exist


def check_if_host_ping(ip_addr):
    """Fn: check_if_host_ping:"""
    try:
        ipaddress.ip_address(ip_addr)
        log_my_msg(f"{ip_addr} is valid ip address")
    except ValueError:
        raise Exception(f"input {ip_addr} not valide IP address")
    try:
        resp = os.system(f"ping -c3 -W2 {ip_addr} > /dev/null 2>&1")
        if resp == 0:
            ping = True
        else:
            ping = False
    finally:
        log_my_msg(f"{ip_addr} primary ip address response to ping over network => {ping}")
    return ping
