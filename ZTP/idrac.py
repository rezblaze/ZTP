# -*- coding: utf-8 -*-

""" Management module provide with configuration for ilo/iDrac
"""

import logging

from ._common import if_resp_not_ok, log_my_msg
from ._session import create_requests_retry_no_token_auth, create_requests_retry_session

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)

no_token_sessobj = create_requests_retry_no_token_auth()
###
### Dell iDRAC class
###


class DellidracActions:
    """Class: Dell iDrac Action"""

    def __init__(self, serverdata, lomuser="", lompass=""):
        """DellidracActions class & associate method

        Args:
            serverdata (dict): serverdata from NetworkData
            lomuser (str): lights out management user
            lompass (str): lights out management passwd
        """
        log_my_msg("*** ZTP DellidracActions module ***")
        self.serverdata = serverdata
        self.lom = serverdata["LOMIP"]
        self.lomuser = lomuser
        self.lompass = lompass
        self.sessobj = create_requests_retry_session(self.lom, lomuser, lompass)

    def check_idrac(self):
        """Method: Check idrac setting against standard"""
        server_config = get_idrac_settings(self.lom, self.sessobj)
        standard_config = get_idrac_standard()
        return compare_two_simple_dict(server_config, standard_config)


###
### Helper Functions
###


def get_idrac_standard():
    """Fn: Get standard for idrac setting from github
    http://bmi-prod.example.com/pub/tools/build_files/R740XD_iDRAC.json
    """
    log_my_msg("Fn: get_idrac_standard")
    url = "http://bmi-prod.example.com/pub/tools/build_files/R740XD_iDRAC.json"
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    return data["Attributes"]


def get_idrac_settings(lom, session):
    """Fn: Get current idrac settig from server

    Args:
        lom ([type]): [description]
        session ([type]): [description]
    """
    log_my_msg("Fn: get_idrac_settings")
    end_point = "/redfish/v1/Managers/iDRAC.Embedded.1/Attributes"
    resp = session.get(f"https://{lom}{end_point}")
    if_resp_not_ok(resp)
    data = resp.json()
    return data["Attributes"]


def compare_two_simple_dict(dict1, dict2):
    """Compare two dictionary"""
    settings_check = "pass"
    log_my_msg("{:=<170}".format(""))
    log_my_msg("{:<80}{:<30}{:<30}".format("Attributes", "Current Value", "Expected Value"))
    log_my_msg("{:=<170}".format(""))
    for key in dict1.keys() & dict2.keys():
        if dict1[key] == dict2[key]:
            log_my_msg("{:<80}{:<30}{:<30}".format(str(key), str(dict1[key]), str(dict2[key])))
        else:
            log_my_msg("{:<80}{:<30}{:<30}{:<2}".format(str(key), str(dict1[key]), str(dict2[key]), "XXX"))
            settings_check = "fail"
    log_my_msg("{:=<170}".format(""))
    result = {"idrac_check": settings_check}
    log_my_msg(result)
    return result
