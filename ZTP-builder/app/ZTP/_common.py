# -*- coding: utf-8 -*-

"""_common.py"""

__author__ = "David Blasing, Chirag Patel"
__email__ = "david_m_blasing@example.com, chirag_patel@example.com"

import logging

logger = logging.getLogger(__name__)


def if_resp_not_ok(resp):
    "Fn: if response from api not ok raise Exception"
    if not resp.ok:
        msg = f" fail: url= {resp.url} \n response_code = {resp.status_code} \n response_text = {resp.text}"
        logger.critical(msg)
        raise Exception("if_resp_not_ok: " + msg)


def log_my_msg(msg):
    """Fn: log my message"""
    logger.info(msg)
