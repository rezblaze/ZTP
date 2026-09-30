# -*- coding: utf-8 -*-

"""
_healthcheck.py - url, iso , port health checker
"""

__author__ = "David Blasing, Chirag Patel"
__email__ = "support@example.com"

import json
import logging
import socket
import time

import spur

from ._common import if_resp_not_ok, log_my_msg
from ._session import create_requests_retry_no_token_auth

no_token_sessobj = create_requests_retry_no_token_auth()

logger = logging.getLogger(__name__)


def check_http_iso(url):
    """Fn: check_http_iso"""
    log_my_msg("Fn: check_http_iso")
    resp = no_token_sessobj.head(url)
    if_resp_not_ok(resp)
    log_my_msg(f" pass: url appears to be available, url={url}")


def isopen(ipaddr, port):
    """Fn: isopen - Check port is open"""
    timeout = 3
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ipaddr, int(port)))
        sock.shutdown(socket.SHUT_RDWR)
        return True
    except Exception:
        return False
    finally:
        sock.close()


def check_host_port(ipaddr, port=22, initwait=5, maxretry=30, checkdelay=60):
    """Fn: check_host_port - Check host port"""
    log_my_msg(f"Fn: check_host_port - host {ipaddr} port {port}")
    log_my_msg(f" - Waiting {initwait} seconds before start checking, Please wait...")
    time.sleep(initwait)
    attemp = 1
    while True:
        log_my_msg(f" - Checking... Attempt {attemp} of {maxretry}")
        if isopen(ipaddr, port):
            log_my_msg(" - PASS: port is open and responding")
            break
        if attemp == maxretry:
            msg = f" fail: max retries of {maxretry} exceeded, port {port} failed to respond on {ipaddr}"
            raise Exception(msg)
        attemp = attemp + 1
        time.sleep(checkdelay)


def get_rhel_info_with_ssh(server, user, passwd):
    """Fn: get_rhel_info_with_ssh"""
    log_my_msg("Fn: get_rhel_info_with_ssh")
    try:
        shell = spur.SshShell(
            hostname=server,
            username=user,
            password=passwd,
            connect_timeout=10,
            missing_host_key=spur.ssh.MissingHostKey.accept,
        )
        result = shell.run(["cat", "/etc/redhat-release"])
    except Exception as error:
        msg = f" fail: ssh failed with error {error}"
        raise Exception(msg) from error
    info = result.output.strip().decode("utf-8")
    log_my_msg(f" pass: server appears to be up and can be ssh. \n reporting rhel release: {info}")


def get_esxi_info_with_ssh(server, user, passwd):
    """Fn: get_esxi_info_with_ssh"""
    log_my_msg("Fn: get_esxi_info_with_ssh")
    try:
        shell = spur.SshShell(
            hostname=server,
            username=user,
            password=passwd,
            connect_timeout=10,
            missing_host_key=spur.ssh.MissingHostKey.accept,
        )
        uname_status = shell.run(["uname", "-a"])
        ssh_status = shell.run(["chkconfig", "--list", "SSH"])
        ntp_status = shell.run(["ntpq", "-p"])
    except Exception as error:
        msg = f" fail: ssh failed with error {error}"
        raise Exception(msg) from error
    info_uname = uname_status.output.strip().decode("utf-8")
    info_ssh = ssh_status.output.strip().decode("utf-8")
    ntp_chk = ntp_status.output.strip().decode("utf-8")
    info_ntp = (ntp_chk.split("\n", 4)[2], ntp_chk.split("\n", 4)[3])
    info = {"uname -a": info_uname, "chkconfig --list ssh": info_ssh, "ntpq -p": info_ntp}
    log_my_msg(f"{json.dumps(info, indent=4)}")
