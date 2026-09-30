import json
import logging

import requests

from app.build_service.cache import CREDS

logger = logging.getLogger(__name__)

splunk_collector = "https://phi-dmz-hec-splunk.example.com/services/collector"


def send_to_splunk(build, status, status_detail):
    logger.info(f"fn:send_to_splunk: {status} {status_detail}")
    build_dict_splunk = build
    status_dict = {
        "status": status,
        "status_detail": status_detail,
    }
    stoken = CREDS["splunk"]["token"]
    build_dict_splunk.update(status_dict)
    if build_dict_splunk.get("host") is not None:
        del build_dict_splunk["host"]
    splunk_headers = {"Authorization": f"Splunk {stoken}"}
    data = {"sourcetype": build["bmi_env"], "event": build_dict_splunk}
    try:
        requests.post(
            f"{splunk_collector}",
            headers=splunk_headers,
            data=json.dumps(data),
            verify=CREDS["verify"],
        )
    except Exception as err:
        logger.warning(f"Exception: {err}")
