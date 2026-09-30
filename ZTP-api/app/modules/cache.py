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
    raise Exception("setup CHAVI variable for local creds data")


def get_cache(file_path: str) -> dict:
    """Fetch and cache data from a file or URL, always returning a dictionary."""
    file_name = os.path.basename(file_path)
    is_new_lom = file_name == "new_lom.json"

    # Step 1: Read data (either from file or URL)
    if os.path.exists(file_path):
        logger.info(f"- caching with {file_path} mount")
        with open(file_path, "r", encoding="utf-8") as file:
            if is_new_lom:
                # For new_lom.json, read as a string for decryption
                data = file.read().strip()
            else:
                # For other files, directly load as JSON
                return json.load(file)
    else:
        # Try fetching from prod, then stage if prod fails
        for env in ["prod", "stage"]:
            url = f"http://bmi-{env}.example.com{file_path}"
            logger.info(f"- caching with {env} {url}")
            try:
                resp = requests.get(url=url)
                if resp.status_code == 200:
                    break
            except Exception as err:
                logger.info(f"Exception fetching from {env} {url}: {err}")
                if env == "stage":  # If stage also fails, raise exception
                    raise Exception(f"Failed to fetch {file_path}: {err}")
        if not resp.ok:
            raise Exception(f"Failed fetching {file_path}, response code {resp.status_code} Error: {resp.text}")

        # Step 2: Handle the response content
        if is_new_lom:
            # For new_lom.json, get content as bytes for decryption
            data = resp.content
        else:
            # For other files, parse JSON directly from response
            return resp.json()

    # Step 3: Handle new_lom.json (decrypt and parse)
    if is_new_lom:
        logger.info("(decrypting creds)")
        try:
            f_key = Fernet(key)
            # Ensure data is in bytes for decryption
            if isinstance(data, str):
                data = data.encode("utf-8")
            decrypted_data = f_key.decrypt(data)
            return json.loads(decrypted_data.decode("utf-8"))
        except Exception as err:
            raise Exception(f"Failed to decrypt and parse {file_path}: {err}")


# Load the cache
CREDS = get_cache("/pub/tools/build_files/new_lom.json")
# logger.info(CREDS)
GEN9_FULL = get_cache("/pub/tools/github/standards/HPE-Standard/json/gen9_full.json")
GEN10_FULL = get_cache("/pub/tools/github/standards/HPE-Standard/json/gen10_full.json")
GEN11_FULL = get_cache("/pub/tools/github/standards/HPE-Standard/json/gen11_full.json")
HPE_VARIABLES = get_cache("/pub/tools/github/standards/HPE-Standard/json/hpe_variables.json")

# Print status
logger.info("CREDS:", "Pass" if isinstance(CREDS, dict) else "Fail")
logger.info("GEN9_FULL:", "Pass" if isinstance(GEN9_FULL, dict) else "Fail")
logger.info("GEN10_FULL:", "Pass" if isinstance(GEN10_FULL, dict) else "Fail")
logger.info("GEN11_FULL:", "Pass" if isinstance(GEN11_FULL, dict) else "Fail")
logger.info("HPE_VARIABLES:", "Pass" if isinstance(HPE_VARIABLES, dict) else "Fail")
