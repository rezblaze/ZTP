# -*- coding: utf-8 -*-
"""_cache.py"""

import json
import logging
import os

import requests
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)
CACHE = {}

key = os.getenv("CHAVI")
if not key:
    raise Exception("Environment variable 'CHAVI' must be set for local credentials decryption.")


def get_cache(file_path: str) -> dict:
    """Fetch and cache data from a file or URL, always returning a dictionary."""
    file_name = os.path.basename(file_path)
    is_new_lom = file_name == "new_lom.json"

    # Step 1: Read from local file if available
    if os.path.exists(file_path):
        print(f"- Caching from local file: {file_path}")
        with open(file_path, "r", encoding="utf-8") as file:
            if is_new_lom:
                data = file.read().strip()
            else:
                return json.load(file)
    else:
        # Step 2: Attempt to fetch from remote (prod, then stage)
        for env in ["prod", "stage"]:
            url = f"http://bmi-{env}.example.com{file_path}"
            print(f"- Attempting to cache from {env.upper()} URL: {url}")
            try:
                resp = requests.get(url=url)
                if resp.status_code == 200:
                    break
            except Exception as err:
                print(f"Exception fetching from {env.upper()} URL: {err}")
                if env == "stage":
                    raise Exception(f"Failed to fetch {file_path} from both prod and stage: {err}")
        else:
            raise Exception(f"Failed fetching {file_path}, response code {resp.status_code}, Error: {resp.text}")

        if is_new_lom:
            data = resp.content
        else:
            return resp.json()

    # Step 3: Decrypt new_lom.json
    if is_new_lom:
        print("- Decrypting credentials...")
        try:
            f_key = Fernet(key)
            if isinstance(data, str):
                data = data.encode("utf-8")
            decrypted_data = f_key.decrypt(data)
            return json.loads(decrypted_data.decode("utf-8"))
        except Exception as err:
            raise Exception(f"Failed to decrypt and parse {file_path}: {err}")


# Load the cache
CREDS = get_cache("/pub/tools/build_files/new_lom.json")
GEN9_FULL = get_cache("/pub/tools/github/standards/HPE-Standard/json/gen9_full.json")
GEN10_FULL = get_cache("/pub/tools/github/standards/HPE-Standard/json/gen10_full.json")
GEN11_FULL = get_cache("/pub/tools/github/standards/HPE-Standard/json/gen11_full.json")
HPE_VARIABLES = get_cache("/pub/tools/github/standards/HPE-Standard/json/hpe_variables.json")

# Dell BIOS standards
R740XD_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R740XD.BIOS.json")
# R740_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R740.BIOS.json")
R6515_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R6515.bios.standard.json")
R7525_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R7525.bios.standard.json")
R750_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R750.bios.standard.json")
R760_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R760.bios.standard.json")
R6615_BIOS = get_cache("/pub/tools/github/standards/Dell_Standards/json/R6615.bios.standard.json")
R740XD_BIOS_SECUREBOOT = get_cache("/pub/tools/github/standards/Dell_Standards/json/R740XD.BIOS.SecureBoot.json")
SED_KEY_PERC = get_cache("/pub/tools/github/standards/Dell_Standards/json/SedKey.json")
SED_KEY_BOSS = get_cache("/pub/tools/github/standards/Dell_Standards/json/sed_key_boss.json")

WINDOWS_BUILD = get_cache("/pub/tools/github/standards/company-bmi-infra/scripts/powershell/windows_base.json")


# Print status
def print_status(name, obj):
    print(f"{name}: {'Pass' if isinstance(obj, dict) else 'Fail'}")


# CREDs
print_status("CREDS", CREDS)
# HPE Standards
print_status("GEN9_FULL", GEN9_FULL)
print_status("GEN10_FULL", GEN10_FULL)
print_status("GEN11_FULL", GEN11_FULL)
print_status("HPE_VARIABLES", HPE_VARIABLES)
# Dell Standards
print_status("R740XD_BIOS", R740XD_BIOS)
print_status("R6515_BIOS", R6515_BIOS)
print_status("R7525_BIOS", R7525_BIOS)
print_status("R750_BIOS", R750_BIOS)
print_status("R760_BIOS", R760_BIOS)
print_status("R6615_BIOS", R6615_BIOS)
print_status("R740XD_BIOS_SECUREBOOT", R740XD_BIOS_SECUREBOOT)
print_status("SED_KEY_PERC", SED_KEY_PERC)
print_status("SED_KEY_BOSS", SED_KEY_BOSS)

print_status("WINDOWS_BUILD", WINDOWS_BUILD)
