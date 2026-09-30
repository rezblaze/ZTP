import asyncio
import json
import logging
import time

import httpx
import schedule

from app.config import config
from app.modules.cache import CREDS
from app.modules.sync_mod import sync_postbuild, sync_standards
from app.service.mail_service import send_email

logger = logging.getLogger(__name__)

splunk_collector = "https://phi-dmz-hec-splunk.example.com/services/collector?"

settings = config.get_setting()


def get_api_log_data():  # sourcery skip: low-code-quality
    logger.info("Fn: get api log data from bmi_api_app.log")
    get_count = post_count = serverinfo_count = networkdata_count = build_status_count = build_events_count = (
        build_linux
    ) = build_windows = build_esxi = baseline_hpe_ilo = baseline_hpe_bios = baseline_hpe_prep = baseline_hp_spp = (
        baseline_dell_idrac
    ) = ilo_eskm_count = lom_adminlo_count = 0
    with open(f"{settings.log_dir}/bmi_api_app.log", "r") as f:
        for line in f:
            if "GET:" in line:
                get_count += 1
                if line.__contains__("/serverinfo/"):
                    serverinfo_count += 1
                if line.__contains__("/builds/status/"):
                    build_status_count += 1
                if line.__contains__("/builds/events/"):
                    build_events_count += 1
                if line.__contains__("/networkdata/"):
                    networkdata_count += 1
            if "POST:" in line:
                post_count += 1
                if line.__contains__("/builds/linux"):
                    build_linux += 1
                if line.__contains__("/builds/windows"):
                    build_windows += 1
                if line.__contains__("/builds/esxi"):
                    build_esxi += 1
                if line.__contains__("/baseline/hpe/ilo"):
                    baseline_hpe_ilo += 1
                if line.__contains__("/baseline/hpe/bios"):
                    baseline_hpe_bios += 1
                if line.__contains__("/baseline/hpe/prep"):
                    baseline_hpe_prep += 1
                if line.__contains__("/baseline/hp/spp"):
                    baseline_hp_spp += 1
                if line.__contains__("/baseline/dell/idrac"):
                    baseline_dell_idrac += 1
                if line.__contains__("/ilo/ESKM"):
                    ilo_eskm_count += 1
                if line.__contains__("/lom/adminlo"):
                    lom_adminlo_count += 1

    resp = {
        "GET": get_count,
        "POST": post_count,
        "/serverinfo/": serverinfo_count,
        "/networkdata/": networkdata_count,
        "/builds/linux": build_linux,
        "/builds/windows": build_windows,
        "/builds/esxi": build_esxi,
        "/baseline/hpe/ilo": baseline_hpe_ilo,
        "/baseline/hpe/bios": baseline_hpe_bios,
        "/baseline/hpe/prep": baseline_hpe_prep,
        "/baseline/hp/spp": baseline_hp_spp,
        "/builds/dell/idrac": baseline_dell_idrac,
        "/builds/status/": build_status_count,
        "/builds/events/": build_events_count,
        "/ilo/ESKM": ilo_eskm_count,
        "/lom/adminlo": lom_adminlo_count,
    }
    f.close()
    logger.info(json.dumps(resp, indent=4))
    return resp


def send_to_splunk(payload):
    logger.info("Fn: send data to splunk")
    stoken = CREDS["splunk"]["token"]
    splunk_collector = "https://phi-dmz-hec-splunk.example.com/services/collector"
    splunk_headers = {"Authorization": f"Splunk {stoken}"}
    data = {"sourcetype": settings.bmi_env, "event": payload}
    try:
        httpx.post(
            splunk_collector,
            headers=splunk_headers,
            data=json.dumps(data),
            verify=CREDS["verify"],
        )
    except Exception as err:
        logger.warning(f"Exception: {err}")


def job():
    logger.info(
        "Fn: starting job for sending data to splunk for api calls everyday also to sync postbuild script if this is prod"
    )
    try:
        payload = get_api_log_data()
        send_to_splunk(payload)
        if settings.bmi_env == "bmi-prod.example.com":
            asyncio.run(sync_postbuild())
            asyncio.run(sync_standards())
    except Exception as err:
        msg = f"Fn:job Exception occured while executing schedule job at midnight(23:55): {err}"
        logger.error(msg)
        body = f"<html><body style='color:red;'>{msg}</body></html>"
        send_email("chirag_patel@example.com", "BMI API - Failed to sync postbuild repo", body)
        send_email("david_m_blasing@example.com", "BMI API - Failed to sync postbuild repo", body)


def api_data_to_spunk():
    logger.info("fn:api_data_to_spunk scheduler for api data to splunk starting")
    # schedule.every(2).seconds.do(job)
    schedule.every().day.at("23:55").do(job)
    while True:
        schedule.run_pending()
        time.sleep(5)
