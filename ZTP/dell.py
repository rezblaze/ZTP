# -*- coding: utf-8 -*-

""" Dell module provide with configuration for PowerEdge R740xd/R7525/R6515
"""
import datetime
import json
import logging
import os
import re
import time

from ._common import if_resp_not_ok, log_my_msg
from ._healthcheck import check_host_port, check_http_iso
from ._session import create_requests_retry_no_token_auth, create_requests_retry_session
from .exception import PrimaryNetworkGWUnreachable

no_token_sessobj = create_requests_retry_no_token_auth()

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)


class DellServer:
    """Class: Dell deployment functionality"""

    def __init__(self, lom, lomuser, lompass):
        """DellServer class & associate method

        Args:
            lom (str): lights out management ip address
            lomuser (str): lights out management user
            lompass (str): lights out management passwd
        """
        log_my_msg("*** ZTP DellServer module ***")
        self.lom = lom
        self.lomuser = lomuser
        self.lompass = lompass
        self.sessobj = create_requests_retry_session(lom, lomuser, lompass)

    def __repr__(self):
        return f"DellServer ({self.sessobj})"

    def get_power_status(self):
        """Method: return power status"""
        return get_power_status(self.lom, self.sessobj)

    def set_power_off(self):
        """Method: set power off"""
        return set_power_off(self.lom, self.sessobj)

    def set_power_on(self):
        """Method: set power on"""
        return set_power_on(self.lom, self.sessobj)

    def check_virtual_media_connect(self):
        return check_virtual_media_connect(self.lom, self.sessobj)

    def odi_preztp(self):
        """Method: ODI Dell server configuration method"""
        log_my_msg("(DellServer) odi_preztp")

        log_my_msg("(*) deleting job queue")
        delete_job_queue(self.lom, self.sessobj)
        time.sleep(10)

        log_my_msg("(*) apply standard bios attributes")

        dell_bios = {
            "R740XD": "http://bmi-prod.example.com/pub/tools/build_files/R740XD.BIOS.json",
            "R740": "http://bmi-prod.example.com/pub/tools/build_files/R740XD.BIOS.json",
            "R6515": "http://bmi-prod.example.com/pub/tools/build_files/R6515.bios.standard.json",
            "R7525": "http://bmi-prod.example.com/pub/tools/build_files/R7525.bios.standard.json",
            "R750": "http://bmi-prod.example.com/pub/tools/build_files/R750.bios.standard.json",
        }
        model = get_dell_model(self.lom, self.sessobj)
        dellbiosurl = dell_bios[model]
        log_my_msg(f"Dell model {model} found!")

        # if "R740" in model:
        if dellbiosurl == "":
            raise Exception(f" fail: bios url is not available for dell model {model}")
        log_my_msg(dellbiosurl)

        set_bios_attributes(self.lom, self.sessobj, dellbiosurl)
        bios_jobid = create_bios_config_job(self.lom, self.sessobj)

        log_my_msg("(*) raid 1 for os drives")
        ctlr, ctlr_ep = get_root_ctlr_ctle_ep(self.lom, self.sessobj)
        log_my_msg(f"ctlr = {ctlr}  ctlr_ep = {ctlr_ep}")
        encryption_status(self.lom, self.sessobj, ctlr)
        make_os_install_raid1(self.lom, self.sessobj, ctlr, ctlr_ep)
        encrypt_root_drive(self.lom, self.sessobj, ctlr)

        log_my_msg("(*) bios check")
        loop_job_status(self.lom, self.sessobj, bios_jobid)
        server_bios = get_bios_attributes(self.lom, self.sessobj)
        standard_bios = payload_from_jsonfile(dellbiosurl)
        compare_two_dict(server_bios, standard_bios["Attributes"])

        log_my_msg("(*) poweroff server")
        time.sleep(10)
        set_power_off(self.lom, self.sessobj)

    def odi_deploy_esxi(self, hostiso):
        """Method: ODI dell server ESXi deployment method"""
        log_my_msg("(DellServer) odi_deploy_esxi")
        log_my_msg("(*) check iso uri, eject, insert, set onetime boot to virual media")
        check_http_iso(hostiso)
        eject_media(self.lom, self.sessobj)
        time.sleep(5)
        insert_media(self.lom, self.sessobj, hostiso)
        time.sleep(5)
        attach_virtulmedia_idrac(self.lom, self.sessobj)
        time.sleep(5)
        set_next_onetime_boot_device_virtual_media(self.lom, self.sessobj)
        time.sleep(5)
        set_power_on(self.lom, self.sessobj)
        time.sleep(120)
        log_my_msg("(*) wait for os load ")
        wait_for_os_load(self.lom, self.sessobj, hostiso)
        time.sleep(180)

    ### DELL ###

    def deploy_rhel(self, hostiso):
        """Method: ODI dell server rhel deployment method"""
        log_my_msg("(DellServer) odi_deploy_rhel")
        deploy_rhel_dict = {}
        eject_media(self.lom, self.sessobj)
        check_http_iso(hostiso)
        insert_media(self.lom, self.sessobj, hostiso)
        time.sleep(5)
        attach_virtulmedia_idrac(self.lom, self.sessobj)
        time.sleep(5)
        set_next_onetime_boot_device_virtual_media(self.lom, self.sessobj)
        time.sleep(5)
        set_power_on(self.lom, self.sessobj)
        time.sleep(5)
        resp_bool, msg_received = check_dell_work_note(self.lom, self.sessobj, "ZTP:KS:Pre_primary_network_check_")
        if msg_received.split("_")[4] == "FAIL":
            deploy_rhel_dict.update({"primary network check": "fail"})
            raise PrimaryNetworkGWUnreachable
        if msg_received.split("_")[4] == "PASS":
            log_my_msg(" pass: primary network adapter check successful")
            deploy_rhel_dict.update({"primary network check": "pass"})
        log_my_msg(check_dell_work_note(self.lom, self.sessobj, "ZTP:KS:Postkickstart_completed")[0])
        if check_dell_work_note(self.lom, self.sessobj, "ZTP:KS:Postkickstart_completed")[0]:
            deploy_rhel_dict.update({"post kickstart": "completed"})
        log_my_msg(" pass: os deployment completed")
        deploy_rhel_dict.update({"os": "deployed"})
        return deploy_rhel_dict

    def rhel_post_provisioning_dell(self):
        """Method: RHEL post provising
        Ref: https://github.example.com/BareMetal/Standards
        Directories: kickstart, postbuild
        """
        log_my_msg("(DellServer) rhel_post_provisioning")
        post_prov_dict = {}
        if check_dell_work_note(self.lom, self.sessobj, "ZTP:POSTBUILD:Postbuild_scripts_starting")[0]:
            pass
        if check_dell_work_note(
            self.lom,
            self.sessobj,
            "ZTP:POSTBUILD:Server_installation_and_postbuild_completed",
        )[0]:
            pass
        if check_dell_work_note(
            self.lom,
            self.sessobj,
            "ZTP:BUILDCOMPLETED:Server_installation_and_postbuild_completed",
        )[0]:
            pass
        post_prov_dict.update({"post provisioning": "completed"})
        log_my_msg(" pass: post provisioning completed!")
        return post_prov_dict

    def odi_apply_secureboot(self):
        """ODI dell server Secureboot method"""
        log_my_msg("(DellServer) odi_apply_secureboot")
        biosurl = (
            "http://bmi-prod.example.com/pub/tools/build_files/R740XD.BIOS.SecureBoot.json"
        )
        log_my_msg("(*) Apply secureboot bios setting")
        log_my_msg("Checking idrac is online")
        check_host_port(self.lom, 443, 10)
        time.sleep(30)
        wait_for_api_status_ready(self.lom, self.sessobj)
        time.sleep(10)
        set_bios_attributes(self.lom, self.sessobj, biosurl)
        jobid = create_bios_config_job(self.lom, self.sessobj)
        time.sleep(10)
        get_job_status(self.lom, self.sessobj, jobid)
        graceful_reboot(self.lom, self.sessobj)
        loop_job_status(self.lom, self.sessobj, jobid)
        time.sleep(10)
        server_bios = get_bios_attributes(self.lom, self.sessobj)
        standard_bios = payload_from_jsonfile(biosurl)
        compare_two_dict(server_bios, standard_bios["Attributes"])

    def reset_idrac_and_wait(self):
        """Method: Reset idrac and wait until health ok or exit after 5min"""
        return reset_idrac_and_wait(self.lom, self.sessobj)

    def get_remote_service_api_status(self):
        """Method: Get remote service API status"""
        return get_remote_service_api_status(self.lom, self.sessobj)

    def del_work_notes(self):
        """Method: delete work notes from idrac"""
        return del_work_notes(self.lom, self.sessobj)

    def make_os_raid1(self):
        """Method: make raid1 for os drives"""
        log_my_msg("(*) raid 1 for os drives")
        ctlr, ctlr_ep = get_root_ctlr_ctle_ep(self.lom, self.sessobj)
        log_my_msg(f"ctlr = {ctlr}  ctlr_ep = {ctlr_ep}")
        make_os_install_raid1(self.lom, self.sessobj, ctlr, ctlr_ep)
        return

    def delete_job_queue(self):
        """Method: delete job queue"""
        return delete_job_queue(self.lom, self.sessobj)


###
###  Helper Functions
###


def get_dell_model(lom, session):
    """fn: get dell model"""
    log_my_msg("Fn: Getting dell model")
    url = "/redfish/v1/Systems/System.Embedded.1"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    model = data["Model"].split()[1]
    return model.upper()


def check_virtual_media_connect(lom, session):
    """Fn: check_virtual_media_connect"""
    log_my_msg("Fn: Checking virtualmedia connect status")
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    return bool(data["Inserted"])


def get_power_status(lom, session):
    """Fn: get_power_status"""
    url = "/redfish/v1/Systems/System.Embedded.1"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    return data["PowerState"].lower()


def set_power_off(lom, session):
    """Fn: set_power_off - Power OFF server"""
    log_my_msg("Fn: set_power_off")
    power = get_power_status(lom, session)
    if power == "off":
        log_my_msg(" pass: power state is off")
        return
    payload = {"ResetType": "ForceOff"}
    log_my_msg(payload)
    url = "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset/"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "off":
            log_my_msg(" pass: power state is off")
            break
        elif time.time() > timeout:
            log_my_msg(" - 5 min since waiting server status should be poweroff")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(" - waiting for power off")


def set_power_on(lom, session):
    """Fn: set_power_on - Power ON server"""
    log_my_msg("Fn: set_power_on")
    payload = {"ResetType": "On"}
    log_my_msg(payload)
    url = "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset/"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "on":
            log_my_msg(" pass: Power state is on")
            break
        elif time.time() > timeout:
            log_my_msg(" - 5 min since waiting server status should be poweron")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(" - waiting for power on")


def set_force_restart(lom, session):
    """Fn: set_force_restart - ForceRestart server"""
    log_my_msg("Fn: set_force_restart")
    payload = {"ResetType": "ForceRestart"}
    log_my_msg(payload)
    url = "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset/"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: Power ForceRestart command successful")


def graceful_shutdown(lom, session):
    """Fn: graceful_shutdown - Gracefully shutdown server"""
    log_my_msg("Fn: graceful_shutdown")
    payload = {"ResetType": "GracefulShutdown"}
    log_my_msg(payload)
    url = "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset/"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    timeout = time.time() + 5 * 60
    while True:
        time.sleep(5)
        power = get_power_status(lom, session)
        if power == "off":
            log_my_msg(" pass: power state is off")
            break
        elif time.time() > timeout:
            log_my_msg(" - 5 min since waiting server status should be poweroff")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()
        else:
            log_my_msg(" - waiting for power off")


def graceful_reboot(lom, session):
    """Fn: graceful_reboot - Gracefully reboot server"""
    log_my_msg("Fn: graceful_reboot")
    power = get_power_status(lom, session)
    if power == "off":
        log_my_msg(" - server is powered off right now...powering back on")
        set_power_on(lom, session)
    elif power == "on":
        log_my_msg(" - Server is powered on right now...gracefully powering on")
        graceful_shutdown(lom, session)
        time.sleep(60)
        set_power_on(lom, session)


def set_bios_attributes(lom, session, url):
    """Fn: set_bios_attributes - Set BIOS attributes for dell"""
    log_my_msg("Fn: set_bios_attributes")
    resp = no_token_sessobj.get(url, verify=False, timeout=10)
    if_resp_not_ok(resp)
    payload = resp.json()
    log_my_msg(" - Applying BIOS")
    adapters = get_all_networkadapters(lom, session)
    if len(adapters) == 1 and adapters[0].split("/")[-1] == "NIC.Embedded.1":
        attrs = payload["Attributes"]
        if "EmbNic1Nic2" in attrs.keys():
            attrs["EmbNic1Nic2"] = "Enabled"
            payload = {"Attributes": attrs}
            log_my_msg("Enabling Embedded NIC since its only avaialable")
    log_my_msg(payload)
    url = "/redfish/v1/Systems/System.Embedded.1/Bios/Settings"
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: BIOS attribute set successfully")


def create_bios_config_job(lom, session):
    """Fn: create_bios_config_job - Create BIOS config job on idrac"""
    log_my_msg("Fn: create_bios_config_job")
    payload = {"TargetSettingsURI": "/redfish/v1/Systems/System.Embedded.1/Bios/Settings"}
    log_my_msg(payload)
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/Jobs"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: bios config job created")
    respdict = resp.headers
    try:
        job_id_endpoint = respdict["location"]
    except Exception as error:
        log_my_msg(error)
        raise
    job_id = os.path.basename(job_id_endpoint)

    return job_id


def reset_bios_defaults(lom, session):
    """Fn: reset_bios_defaults - Reset BIOS defaults attributes"""
    log_my_msg("Fn: reset_bios_defaults")
    url = "/redfish/v1/Systems/System.Embedded.1/Bios/Actions/Bios.ResetBios"
    payload = {}
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    data = resp.__dict__
    message_search = str(data["_content"])
    if "BIOSRTDRequested value is modified successfully" in message_search:
        log_my_msg(
            f" pass: status code {resp.status_code} returned for post command to reset bios to default settings."
        )


def get_job_status(lom, session, job_id):
    """Fn: get_job_status - Get Job Status"""
    log_my_msg("Fn: get_job_status")
    url = f"/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/{job_id}"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    status = data["JobState"]
    log_my_msg(f" - Current JobState is: {status}")


def loop_job_status(lom, session, job_id):
    """Fn: loop_job_status - Loop through Job status until completed"""
    log_my_msg(f"Fn: loop_job_status {job_id}")
    url = f"/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/{job_id}"
    timeout = time.time() + 30 * 60
    while True:
        resp = session.get(f"https://{lom}{url}")
        data = resp.json()
        stat = data["JobState"]
        log_my_msg(f" - {job_id} current status {stat}")
        if "Completed" in stat:
            log_my_msg(f" - {job_id} completed successfully")
            break
        if time.time() > timeout:
            log_my_msg(" - 30 minutes waitting!")
            log_my_msg(" fail: not sure what caused, time to make call!")
            raise Exception()
        time.sleep(60)


def get_bios_attributes(lom, session):
    """Fn: get_bios_attributes - Get BIOS attributes from server"""
    log_my_msg("Fn: get_bios_attributes")
    url = "/redfish/v1/Systems/System.Embedded.1/Bios"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    return data["Attributes"]


def delete_job_queue_restart_lifecycle(lom, session):
    """Fn: delete_job_queue_restart_lifecycle - Delete job queue and restart lifecycle service"""
    log_my_msg("Fn: Deleting job queue and restarting Lifecycle Controller services")
    url = "/redfish/v1/Dell/Managers/iDRAC.Embedded.1/DellJobService/Actions/DellJobService.DeleteJobQueue"
    payload = {"JobID": "JID_CLEARALL_FORCE"}
    log_my_msg(payload)
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: DeleteJobQueue action passed.")
    log_my_msg(" - lifecycle controller services restarted, please wait")
    timeout = time.time() + 10 * 60
    while True:
        log_my_msg(" - watiting to be ready")
        time.sleep(30)
        data = get_remote_service_api_status(lom, session)
        lc_status = data["LCStatus"]
        server_status = data["Status"]
        if lc_status == "Ready" and server_status == "Ready":
            log_my_msg(" pass: lifecycle controller services are ready!")
            break
        if time.time() > timeout:
            log_my_msg(" - 10 minutes waitting!")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()


def delete_job_queue(lom, session):
    """Fn: delete_job_queue - Delete job queue"""
    log_my_msg("Fn: delete_job_queue")
    url = "/redfish/v1/Dell/Managers/iDRAC.Embedded.1/DellJobService/Actions/DellJobService.DeleteJobQueue"
    payload = {"JobID": "JID_CLEARALL"}
    log_my_msg(payload)
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: delete job queue")


def get_remote_service_api_status(lom, session):
    """Fn: get_remote_service_api_status - Get remote service API status"""
    url = "/redfish/v1/Dell/Managers/iDRAC.Embedded.1/DellLCService/Actions/DellLCService.GetRemoteServicesAPIStatus"
    payload = {}
    status_dict = {}
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    data = resp.json()
    for i in data.items():
        if i[0] == "@Message.ExtendedInfo":
            pass
        else:
            status_dict.update({i[0]: i[1]})
    return status_dict


def wait_for_api_status_ready(lom, session):
    """Fn: wait_for_api_status_ready - Wait for API status to be ready"""
    timeout = time.time() + 5 * 60
    while True:
        data = get_remote_service_api_status(lom, session)
        if (
            "OutOfPOST" in data["ServerStatus"]
            and "Ready" in data["LCStatus"]
            and "Ready" in data["RTStatus"]
            and "Ready" in data["Status"]
        ):
            log_my_msg(" pass: server api status ready and verified")
            return
        elif time.time() > timeout:
            log_my_msg(" - 5 min in get_os_from_idrac function")
            raise Exception()
        else:
            time.sleep(3)


def compare_two_dict(dict1, dict2):
    """Fn: compare_two_dict - Compare two dictionary"""
    log_my_msg("{:=<90}".format(""))
    log_my_msg("{:<30}{:<30}{:<30}".format("Attributes", "Current Value", "Expected Value"))
    log_my_msg("{:=<90}".format(""))
    for key in dict1.keys() & dict2.keys():
        if dict1[key] == dict2[key]:
            log_my_msg("{:<30}{:<30}{:<30}".format(str(key), str(dict1[key]), str(dict2[key])))
        else:
            log_my_msg("{:<30}{:<30}{:<28}{:<2}".format(str(key), str(dict1[key]), str(dict2[key]), "fail"))
    log_my_msg("{:=<90}".format(""))


def payload_from_jsonfile(url):
    """Fn: payload_from_jsonfile - payload from json file"""
    resp = no_token_sessobj.get(url, verify=False, timeout=10)
    if_resp_not_ok(resp)
    data = resp.json()
    return data


def set_bios_attributes_onetimeboot(lom, session):
    """Fn: Setting onetimeboot virtual media with bios"""
    log_my_msg("fn: set_bios_attributes_onetimeboot")
    payload = {
        "Attributes": {
            "OneTimeBootMode": "OneTimeUefiBootSeq",
            "OneTimeUefiBootSeqDev": "Optical.iDRACVirtual.1-1",
            "SecureBoot": "Disabled",
        }
    }
    log_my_msg(payload)
    url = "/redfish/v1/Systems/System.Embedded.1/Bios/Settings"
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: BIOS onetimeboot attribute set successfully")


def insert_media(lom, session, iso):
    """Fn: Insert virtualmedia"""
    log_my_msg("Fn: insert_media")
    payload = {"Image": iso, "Inserted": True, "WriteProtected": True}
    log_my_msg(payload)
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia/"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: insert virtual media sucessfully completed")
    time.sleep(5)
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    attach_status = data["Inserted"]
    if attach_status:
        log_my_msg(f" pass: {iso} virtualmedia successfully inserted! attached status: {attach_status}")
    else:
        log_my_msg(f" fail: url={url} \n response code = {resp.status_code} \n response text = {resp.text}")
        raise Exception


def eject_media(lom, session):
    """Fn: eject_media"""
    log_my_msg("Fn: Eject virtualmedia")
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    if "NotConnected" in data["ConnectedVia"]:  # and data[u'Image'] is None:
        log_my_msg(" - no virtual media connected")
    else:
        url = "/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia"
        payload = {}
        resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
        if_resp_not_ok(resp)
        log_my_msg(" pass: post accepted, eject virtualmediaa sucessfully completed")
        time.sleep(5)


def get_os_from_idrac(lom, session):
    """Fn: get_os_from_idrac"""
    os_name = ""
    url = "/redfish/v1/Managers/System.Embedded.1/Attributes"
    timeout = time.time() + 5 * 60
    while True:
        resp = session.get(f"https://{lom}{url}")
        if resp.ok:
            data = resp.json()
            os_name = data["Attributes"]["ServerOS.1.OSName"]
            break
        elif time.time() > timeout:
            raise Exception(" - 5 min in get_os_from_idrac function")
        else:
            time.sleep(10)
    return os_name


def attach_virtulmedia_idrac(lom, session):
    """Fn:  Attach virtualmedia to iDRAC"""
    log_my_msg("Fn: attach_virtulmedia_idrac")
    payload = {
        "Attributes": {
            "VirtualMedia.1.Attached": "Attached",
            "VirtualMedia.1.BootOnce": "Enabled",
            "VirtualMedia.1.Enable": "Enabled",
            "VirtualMedia.1.EncryptEnable": "Enabled",
        }
    }
    log_my_msg(payload)
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/Attributes/Settings"
    resp = session.patch(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: command sucessfully completed")


def get_firmware(lom, session):
    """Fn: get_firmware"""
    log_my_msg("Fn: get_firmware")
    url = "/redfish/v1/UpdateService/FirmwareInventory/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    resp_dict = resp.json()
    mem_list = resp_dict["Members"]
    fw_dict = {}
    for i in mem_list:
        url = i["@odata.id"]
        resp = session.get(f"https://{lom}{url}")
        resp_dict = resp.json()
        key = resp_dict["Name"]
        value = resp_dict["Version"]
        fw_dict.update({key: value})
    return fw_dict


def reset_idrac_and_wait(lom, session):
    """Fn: reset_idrac_and_wait"""
    log_my_msg("Fn: reset_idrac_and_wait - resetting idrac and waitting for idrac to be healthy ")
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Manager.Reset/"
    payload = {"ResetType": "GracefulRestart"}
    log_my_msg(payload)
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    log_my_msg(" pass: reset idrac")
    log_my_msg(" warning: idrac will now reset and should be back online in few minutes")
    check_host_port(lom, 443, 180)
    timeout = time.time() + 5 * 60
    url = "/redfish/v1/Managers/iDRAC.Embedded.1"
    while True:
        resp = session.get(f"https://{lom}{url}")
        if resp.ok:
            resp_dict = resp.json()
            health = resp_dict["Status"]["Health"]
            log_my_msg(f" - Current idrac Health: {health}")
            break
        if time.time() > timeout:
            log_my_msg(" - 5 min since waiting for idrac to be healthy. check console please!")
            raise Exception()
        time.sleep(5)


def del_work_notes(lom, session):
    """Fn: del_work_notes"""
    log_my_msg("Fn: del_work_notes")
    payload = {"Component": ["LCData"]}
    url = "/redfish/v1/Dell/Managers/iDRAC.Embedded.1/DellLCService/Actions/DellLCService.SystemErase"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    job_location = resp.headers
    job_id = get_job_id(job_location)
    monitor_job_id(lom, session, job_id)
    return


def check_idrac_health(lom, session):
    """Fn: check_idrac_health"""
    url = "/redfish/v1/Managers/iDRAC.Embedded.1"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    return data["Status"]["Health"]


def set_next_onetime_boot_device_virtual_media(lom, session):
    """Fn: set_next_onetime_boot_device_virtual_media"""
    log_my_msg("Fn: set_next_onetime_boot_device_virtual_media")
    payload = {
        "ShareParameters": {"Target": "ALL"},
        "ImportBuffer": '<SystemConfiguration><Component FQDD="iDRAC.Embedded.1"><Attribute Name="ServerBoot.1#BootOnce">Enabled</Attribute><Attribute Name="ServerBoot.1#FirstBootDevice">VCD-DVD</Attribute></Component></SystemConfiguration>',
    }
    log_my_msg(payload)
    url = "/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    resp_dict = str(resp.__dict__)
    try:
        job_id_search = re.search("JID_.+?,", resp_dict).group()
    except Exception as err:
        msg = f" - detailed error information: {resp_dict}"
        raise Exception(msg) from err
    job_id = re.sub("[,']", "", job_id_search)
    while True:
        url = f"/redfish/v1/TaskService/Tasks/{job_id}"
        resp = session.get(f"https://{lom}{url}")
        data = resp.json()
        if_resp_not_ok(resp)
        time.sleep(3)
        if (
            "failed" in data["Oem"]["Dell"]["Message"]
            or "completed with errors" in data["Oem"]["Dell"]["Message"]
            or "Not one" in data["Oem"]["Dell"]["Message"]
            or "not compliant" in data["Oem"]["Dell"]["Message"]
            or "Unable" in data["Oem"]["Dell"]["Message"]
            or "The system could not be shut down" in data["Oem"]["Dell"]["Message"]
            or "timed out" in data["Oem"]["Dell"]["Message"]
        ):
            jobstate = data["Oem"]["Dell"]["JobState"]

            log_my_msg(
                f" - fail: job id {job_id} marked as {jobstate} but detected issue(s). \
                    See detailed job results below for more information on failure"
            )
            log_my_msg(f" - detailed job results for job id {job_id}")
            for i in data["Oem"]["Dell"].items():
                log_my_msg("%s: %s" % (i[0], i[1]))
            log_my_msg(f" - config results for job ID {job_id}\n")
            for i in data["Messages"]:
                for ii in i.items():
                    if ii[0] == "Oem":
                        log_my_msg("-" * 80)
                        for iii in ii[1]["Dell"].items():
                            log_my_msg("%s: %s" % (iii[0], iii[1]))
                    else:
                        pass
        elif "No changes" in data["Oem"]["Dell"]["Message"]:
            log_my_msg(" warning, next onetime boot device already set to virtual cd, no changes applied")
            break
        elif (
            "Successfully imported" in data["Oem"]["Dell"]["Message"]
            or "completed with errors" in data["Oem"]["Dell"]["Message"]
            or "Successfully imported" in data["Oem"]["Dell"]["Message"]
        ):
            log_my_msg(" pass:, successfully set next onetime boot device to virtual cd")
            break
        else:
            time.sleep(1)
            continue


def lc_wipe(lom, session):
    """Fn: lc_wipe - lifecycle service wipe"""
    url = "/redfish/v1/Dell/Managers/iDRAC.Embedded.1/DellLCService/Actions/DellLCService.LCWipe"
    method = "LCWipe"
    payload = {}
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    data = resp.json()
    log_my_msg(f" pass: post accepted for {method}")
    for i in data.items():
        if i[0] == "@Message.ExtendedInfo":
            pass
        else:
            log_my_msg(f"{i[0]}: {i[1]}")
    log_my_msg(
        " warning, idrac will now reset to start LCWipe operation.\
script will wait 5 minutes"
    )
    time.sleep(300)


def get_lifecycle_version(lom, session):
    """Fn: get_lifecycle_version"""
    log_my_msg("Fn: get_lifecycle_version")
    url = "/redfish/v1/UpdateService/FirmwareInventory/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    resp_dict = resp.json()
    try:
        mem_list = resp_dict["Members"]
    except KeyError as error:
        msg = f" fail: key {error} not found!"
        raise Exception(msg) from error
    else:
        log_my_msg(f" fail: get_lifecycle_version response code {resp.status_code}")
    for member in mem_list:
        url = member["@odata.id"]
        resp = session.get(f"https://{lom}{url}")
        resp_dict = resp.json()
        key = resp_dict["Name"]
        if "Lifecycle" in key:
            value = resp_dict["Version"]
    return value


def wait_for_os_load(lom, session, iso):
    """Fn: wait_for_os_load"""
    log_my_msg("(*) check server api status and installation progress looking at idrac attributes")
    timeout = time.time() + 60 * 60
    while True:
        data = get_remote_service_api_status(lom, session)
        if (
            "OutOfPOST" in data["ServerStatus"]
            and "Ready" in data["LCStatus"]
            and "Ready" in data["RTStatus"]
            and "Ready" in data["Status"]
        ):
            log_my_msg(" pass: api statuses ready")
            if check_virtual_media_connect(lom, session):
                log_my_msg(" pass: iso is still connnected after power on.")
            else:
                log_my_msg(" fail: iso is not connnected after power on")
                log_my_msg(" === SELF HEALING ===")
                insert_media(lom, session, iso)
                time.sleep(5)
                attach_virtulmedia_idrac(lom, session)
                time.sleep(5)
                set_next_onetime_boot_device_virtual_media(lom, session)
                time.sleep(5)
            break
        elif time.time() > timeout:
            raise Exception(" - 60 min since waiting for server api status")
        else:
            time.sleep(5)
    log_my_msg("(*) fetching osname in idrac attributes...it will take sometime")
    while True:
        os_name = get_os_from_idrac(lom, session)
        if len(os_name) > 1:
            log_my_msg(
                f" pass: osname < {os_name} > in idrac attributes...\
installation must have begun...please be patient it will take sometime"
            )
            break
        elif time.time() > timeout:
            raise Exception(
                " - 60 min since waiting osname attribute in idrac \
OS installation may be having issue"
            )
        else:
            time.sleep(5)
    while True:
        os_name = get_os_from_idrac(lom, session)
        if len(os_name) < 1:
            log_my_msg(
                " pass: osname disappeared from idrac attribute, assuming os installation completed \
and server is rebooting. please wait..."
            )
            eject_media(lom, session)
            break
        elif time.time() > timeout:
            raise Exception(
                " - 60 min since osname appeared in idrac and assuming installation started \
but installation doesn't seem to be completed"
            )
        else:
            time.sleep(5)


###
###  STORAGE FUNCTIONS
###


def get_controller_type(lom, session):
    """Fn: get_controller_type"""
    log_my_msg("Fn: get_controller_type")
    ctlr_dict = {}
    url = "/redfish/v1/Systems/System.Embedded.1/Storage/"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = resp.json()
    data["Members@odata.count"]
    if data["Members@odata.count"] == 0:
        controllers = data.get("Members", "null")
        log_my_msg(f"error: No storage controllers found {controllers}")
        raise Exception()
    for item in data["Members"]:
        ctrl = item["@odata.id"].split("/")[-1]
        if ctrl.startswith("RAID."):
            ctlr_dict.update({os.path.basename(item["@odata.id"]): item["@odata.id"]})
    key_list = list(ctlr_dict.keys())
    count_controllers = [idx for idx in key_list if idx[0] if "RAID" in idx]
    if len(count_controllers) != 1:
        log_my_msg("error: unable to determine storage controller")
        log_my_msg(f"error: looking for one RAID controller, found {key_list}")
        raise Exception()
    log_my_msg(f"info: found controller {ctlr_dict}")
    return ctlr_dict


def get_controller_disks(lom, session, ctlr_ep):
    """Fn: get_controller_disks"""
    log_my_msg("Fn: get_controller_disks")
    drv_dict = {}
    url = f"{ctlr_ep}"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    drvs = json.loads(resp.text)
    for item in drvs["Drives"]:
        drv_dict.update({os.path.basename(item["@odata.id"]): item["@odata.id"]})
    return drv_dict


def clear_raid_controller(lom, session):
    """Fn: clear_raid_controller"""
    log_my_msg("Fn: clear_raid_controller")
    raid_ctlr = get_controller_type(lom, session)
    ((ctlr, ctlr_ep),) = raid_ctlr.items()
    log_my_msg(f" - clearing controller {ctlr_ep}")
    clear_jobid = clr_ctlr_config(lom, session, ctlr)
    monitor_job_id(lom, session, clear_jobid)


def get_job_id(job_location):
    """Fn:get_job_id"""
    log_my_msg("Fn: get_job_id")
    job_id = None
    job_id = json.dumps(dict(job_location)["Location"])
    if job_id is None:
        log_my_msg(" fail: Unable to find JOB_ID")
        raise Exception()
    log_my_msg(f" - Job_id: {job_id}")
    return job_id


def get_vd_info(lom, session, ctlr):
    """Fn: get_vd_info - Get virtual disk information"""
    log_my_msg("Fn: get_vd_info")
    vd_dict = {}
    url = f"/redfish/v1/Systems/System.Embedded.1/Storage/{ctlr}/Volumes"
    resp = session.get(f"https://{lom}{url}")
    if_resp_not_ok(resp)
    data = json.loads(resp.text)
    vd_list = []
    for item in data["Members"]:
        vd_ep = item["@odata.id"].lstrip()
        vd_list.append(vd_ep)
    for item in vd_list:
        vd_resp = session.get(f"https://{lom}{vd_ep}")
        if_resp_not_ok(resp)
        vd_data = vd_resp.json()
        my_list = ["VolumeType", "CapacityBytes", "Encrypted"]
        for key, val in vd_data.items():
            if "Id" == key:
                vd_id = val
        vd_dict = {vd_id: {}}
        for key, val in vd_data.items():
            if key in my_list:
                data = {key: val}
                vd_dict[vd_id].update(data)
    log_my_msg(vd_dict)
    return vd_dict


def monitor_job_id(lom, session, job_id):
    """Fn: monitor_job_id"""
    log_my_msg(f"Fn: monitor_job_id {job_id}")
    job_done = None
    count = 0
    jobid = os.path.basename(job_id).strip('"')
    while job_done != "Completed":
        url = str(job_id).strip('"')
        resp = session.get(f"https://{lom}{url}")
        if_resp_not_ok(resp)
        job_stat = json.loads(resp.text)
        if "Task" in str(job_id):
            job_done = job_stat["TaskState"]
        if "Jobs" in str(job_id):
            job_done = job_stat["JobState"]
        log_my_msg(f" - {jobid} current state is {job_done}")
        time.sleep(30)
        count = count + 1
        if count == 20 and job_done != "Completed":
            log_my_msg("=== SELF HEALING ===")
            log_my_msg(" - 10 minutes since monitoring job and still not Completed")
            log_my_msg(" - Trying force reboot to recover")
            set_force_restart(lom, session)
        if count > 60:
            log_my_msg(" - over 20 minutes since SELF HEALING was tried")
            log_my_msg(" fail: not sure what caused it not work, time to make call!")
            raise Exception()


def clr_ctlr_config(lom, session, ctlr):
    """Fn: clr_ctlr_config - clear controller"""
    log_my_msg("Fn: clr_ctlr_config")
    log_my_msg(" - Clearing controller at path " + str(ctlr))
    payload = {"TargetFQDD": ctlr}
    log_my_msg(payload)
    url = "/redfish/v1/Dell/Systems/System.Embedded.1/DellRaidService/Actions/DellRaidService.ResetConfig"
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    job_location = resp.headers
    job_id = get_job_id(job_location)
    return job_id


def make_raid1(lom, session, ctlr, dsk0_ep, dsk1_ep, raid1_name="raid1-root"):
    """Fn: make_raid1 - Make RAID1 on two disks assigned"""
    log_my_msg("Fn: make_raid1")
    url = f"/redfish/v1/Systems/System.Embedded.1/Storage/{ctlr}/Volumes/"
    payload = {
        "VolumeType": "Mirrored",
        "Name": raid1_name,
        "Drives": [{"@odata.id": str(dsk0_ep)}, {"@odata.id": str(dsk1_ep)}],
    }
    log_my_msg(payload)
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    job_location = resp.headers
    job_id = get_job_id(job_location)
    log_my_msg(f"job created: {job_id}")
    return job_id


def get_controller_encryption_status(lom, session, ctlr):
    """Fn: get_controller_encryption_status"""
    log_my_msg("Fn: get_controller_encryption_status")
    url = f"https://{lom}/redfish/v1/Systems/System.Embedded.1/Storage/{ctlr}"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    encrypt_status = data["Oem"]["Dell"]["DellController"]["SecurityStatus"]
    return encrypt_status


def enable_ctlr_encryption(lom, session, ctlr):
    """Fn: enable_ctlr_encryption"""
    log_my_msg("Fn: enable_ctlr_encryption")
    url = "http://bmi-prod.example.com/pub/tools/build_files/SedKey.json"
    resp = session.get(url)
    if_resp_not_ok(resp)
    payload = resp.json()
    payload["TargetFQDD"] = ctlr
    log_my_msg(payload)
    url = f"https://{lom}/redfish/v1/Dell/Systems/System.Embedded.1/DellRaidService/Actions/DellRaidService.EnableControllerEncryption"
    resp = session.post(url, data=json.dumps(payload))
    if_resp_not_ok(resp)
    job_location = resp.headers
    job_id = get_job_id(job_location)
    return job_id


def lock_virtualdisk(lom, session, ctlr_lock):
    """Fn: lock_virtualdisk"""
    log_my_msg("Fn: lock_virtualdisk")
    url = "/redfish/v1/Dell/Systems/System.Embedded.1/DellRaidService/Actions/DellRaidService.LockVirtualDisk"
    payload = {"TargetFQDD": ctlr_lock}
    log_my_msg(f"Fn: lock_virtualdisk payload = {payload}")
    resp = session.post(f"https://{lom}{url}", data=json.dumps(payload))
    if_resp_not_ok(resp)
    job_location = resp.headers
    job_id = get_job_id(job_location)
    return job_id


def encrypt_root_drive(lom, session, ctlr):
    """Fn: encrypt_root_drive"""
    log_my_msg("Fn: encrypt_root_drive")
    vd_data = get_vd_info(lom, session, ctlr)
    virtualdisk = next(iter(vd_data.keys()))
    encypt_capability = get_controller_encryption_status(lom, session, ctlr)
    if encypt_capability == "EncryptionNotCapable":
        log_my_msg(f" info, controller found to be {encypt_capability}")
        return
    elif encypt_capability == "EncryptionCapable":
        job_id = enable_ctlr_encryption(lom, session, ctlr)
        monitor_job_id(lom, session, job_id)
        job_id = lock_virtualdisk(lom, session, virtualdisk)
        monitor_job_id(lom, session, job_id)
    elif encypt_capability == "SecurityKeyAssigned":
        job_id = lock_virtualdisk(lom, session, virtualdisk)
        monitor_job_id(lom, session, job_id)
    else:
        log_my_msg(f"- unknown encryption option found {encypt_capability}")
        raise Exception()
    log_my_msg(" - checking volume is encrypted properly")
    vd_data = get_vd_info(lom, session, ctlr)
    data = vd_data[virtualdisk]
    if data["Encrypted"]:
        log_my_msg(f"  pass: encryption enabled\n {json.dumps(vd_data, indent=4)}")
    else:
        msg = f" fail: volume not encrypted\n {vd_data}"
        raise Exception(msg)


def encryption_status(lom, session, ctlr):
    """Fn: encryption_status"""
    log_my_msg("Fn: encryption_status")
    url = f"https://{lom}/redfish/v1/Systems/System.Embedded.1/Storage/{ctlr}"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    values = {
        "EncryptionMode": f"{data['Oem']['Dell']['DellController']['EncryptionMode']}",
        "EncryptionCapability": f"{data['Oem']['Dell']['DellController']['EncryptionCapability']}",
        "SecurityStatus": f"{data['Oem']['Dell']['DellController']['SecurityStatus']}",
    }
    return values


def get_root_ctlr_ctle_ep(lom, session):
    """Fn: get_root_ctlr_ctle_ep"""
    raid_ctlr = get_controller_type(lom, session)
    for item in raid_ctlr:
        # if item.startswith("RAID.Slot.") or item.startswith("RAID.SL."):
        if item.startswith("RAID."):
            log_my_msg(f" - using controller {item}")
            ctlr = item
            ctlr_ep = raid_ctlr[item]
    return ctlr, ctlr_ep


def make_os_install_raid1(lom, session, ctlr, ctlr_ep):
    """Fn: make_os_install_raid1 - Making OS install RAID1"""
    log_my_msg("Fn: make_os_install_raid1")
    log_my_msg(" - getting disks for os raid 1")
    dsk = get_controller_disks(lom, session, ctlr_ep)
    dsk0 = list(dsk.values())[0]
    dsk1 = list(dsk.values())[1]
    log_my_msg(f" - controller: \n{ctlr_ep}")
    log_my_msg(f" - drives:\ndisk0: {dsk0}\ndisk1: {dsk1}")
    clear_jobid = clr_ctlr_config(lom, session, ctlr)
    monitor_job_id(lom, session, clear_jobid)
    make_jobid = make_raid1(lom, session, ctlr, dsk0, dsk1)
    monitor_job_id(lom, session, make_jobid)
    vd_data = get_vd_info(lom, session, ctlr)
    return f"{json.dumps(vd_data, indent=4)}"


def get_dell_system_time(lom, session):
    """Fn: Get Dell System Time"""
    url = f"https://{lom}/redfish/v1/Managers/iDRAC.Embedded.1"
    resp = session.get(url)
    if_resp_not_ok(resp)
    system_date_time = resp.json()["DateTime"]
    system_date = system_date_time.split("T", 1)[0]
    system_time = system_date_time.split("T", 1)[1].split("-", 1)[0]
    return [system_date, system_time]


def get_dell_work_note(lom, session):
    """Fn: Get Dell Work Notes"""
    now = datetime.datetime.now()
    system_date_time = get_dell_system_time(lom, session)
    start_time = now.replace(
        hour=int(system_date_time[1].split(":", 2)[0]),
        minute=int(system_date_time[1].split(":", 2)[1]),
        second=int(system_date_time[1].split(":", 2)[2]),
    )
    wn_list = []
    url = f"https://{lom}/redfish/v1/Managers/iDRAC.Embedded.1/LogServices/Lclog/Entries"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json().get("Members", {})
    if len(data) == 0:
        log_my_msg(f"Work Notes Members not found returned {data}!")
        raise Exception(f"Work Notes Members not found returned {data}!")
    else:
        for index in range(len(data)):
            for val in data[index].values():
                if "WRK0001" in str(val):
                    message_date = data[index]["Created"].split("T", 1)[0]
                    message_time = data[index]["Created"].split("T", 1)[1].split("-", 1)[0]
                    wrk_msg_time = now.replace(
                        hour=int(message_time.split(":", 2)[0]),
                        minute=int(message_time.split(":", 2)[1]),
                        second=int(message_time.split(":", 2)[2]),
                    )
                    if message_date == system_date_time[0] and wrk_msg_time <= start_time:
                        wn_list.append(data[index])
    return wn_list


def check_dell_work_note(lom, session, msg):
    """Fn: Check Dell Work Notes"""
    system_time = get_dell_system_time(lom, session)
    log_my_msg(f"Fn: check_dell_work_note - Starting at {system_time}, looking for this message: {msg}")
    timeout = time.time() + 30 * 60
    while True:
        time.sleep(20)
        message = get_dell_work_note(lom, session)
        msg_received = False
        for index in range(len(message)):
            if msg in str(message[index]):
                msg_received = True
                return [msg_received, str(message[index])]
            if time.time() > timeout:
                log_my_msg(f" critical: 30 min since waiting, {msg} did not received!")
                raise Exception(f" critical: 30 min since waiting, {msg} did not received!")


###
### Network
###


def get_all_networkadapters(lom, session):
    """Fn: get_all_networkadapters"""
    log_my_msg("Fn: get_all_networkadapters")
    url = f"https://{lom}/redfish/v1/Chassis/System.Embedded.1/NetworkAdapters/"
    resp = session.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    if data["Members@odata.count"] == 0:
        raise Exception(f"No Network adpater found")
    nw_adapters = []
    for adapters in data["Members"]:
        nw_adapters.append(adapters["@odata.id"])
    log_my_msg(nw_adapters)
    return nw_adapters
