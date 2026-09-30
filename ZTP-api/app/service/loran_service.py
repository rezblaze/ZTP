import json
import logging

import requests
from ldap3.utils.conv import escape_filter_chars

from app.modules.cache import CREDS

logger = logging.getLogger(__name__)

loran_namespace = "https://loran-core.example.com/bmiapi"

lcreds = CREDS["loran"]["token"]

headers = {
    "Authorization": f"Basic {lcreds}",
    "Content-Type": "application/json",
}


def get_loran_hostdata(host):
    url = escape_filter_chars(f"{loran_namespace}/{host}")
    headers = {"Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, verify=CREDS["verify"])
    if not resp.ok:
        logger.warning(f"fail: could not retrieve data from loran {url} statuscode {resp.status_code}")
    return resp.json()


def update_loran_hostdata(host, payload):
    url = escape_filter_chars(f"{loran_namespace}/{host}")
    data = get_loran_hostdata(host)
    data.update(payload)
    resp = requests.put(url, headers=headers, data=json.dumps(data), verify=CREDS["verify"])
    if resp.ok:
        logger.info(f"pass: update data to loran {url}")
    else:
        logger.warning(f"fail: update data to loran with statuscode {resp.status_code}\n{payload}")


def add_hostdata_loran(host, payload):
    url = escape_filter_chars(f"{loran_namespace}/{host}")
    resp = requests.put(url, headers=headers, data=json.dumps(payload), verify=CREDS["verify"])
    if resp.ok:
        logger.info(f"pass: add payload to loran {url}")
    else:
        logger.warning(f"fail: add payload to loran with statuscode {resp.status_code}\n {payload}")
