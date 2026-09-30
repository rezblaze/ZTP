# -*- coding: utf-8 -*-

"""sync_mod.py
- sync standards repo and postbuild ansible playbook and chef cookbooks
- url: https://github.example.com/example-org/ztp-infra/blob/master/bmi_content_sync.json
Author: Chirag Patel
"""

import logging
import os
import subprocess
import tarfile

from fastapi import HTTPException

from app.config import config
from app.service.mail_service import send_email

settings = config.get_setting()

logger = logging.getLogger(__name__)


data = {
    "standards": {
        "hpe-standard": "https://github.com/company-org/HPE-Standard.git",
        "dell-standard": "https://github.com/company-org/Dell_Standards.git",
        "bmi-infra": "https://github.example.com/example-org/ztp-infra.git",
    },
    "postbuild": {
        "ansible": "https://github.com/company-org/company-ansible.git",
        "compliance_make_backup": "https://github.com/company-org/compliance_make_backup.git",
        "doesapi_client_handler": "https://github.com/company-org/doesapi_client_handler.git",
        "company_compliance_standard_baseline": "https://github.com/company-org/company_compliance_standard_baseline.git",
        "company_patch_utils": "https://github.com/company-org/company_patch_utils.git",
        "company_rhel_qas": "https://github.com/company-org/company_rhel_qas.git",
        "company_rhel_standard": "https://github.com/company-org/company_rhel_standard.git",
        "company_rsyslog_config": "https://github.com/company-org/company_rsyslog_config.git",
        "line": "https://github.com/company-org/line.git",
        "company_satellite_reg": "https://github.com/company-org/company_satellite_reg.git",
    },
}

standards_repo = data["standards"]
postbuild_repo = data["postbuild"]


async def setup_sync_dir():
    if settings.bmi_env == "local":
        homedir = os.getenv("HOME")
        sync_dir = f"{homedir}/github/"
    else:
        sync_dir = "/pub/tools/github/"
    return sync_dir


async def clone_repo(repo_url):
    repo_name = repo_url.split("/")[-1].split(".")[0]
    uri = repo_url.split("//")[1]
    result = {"repo_name": repo_name, "url": uri}
    logger.info(result)
    if os.path.isdir(repo_name):
        logger.info("repo directory exist, attempting git pull")
        os.chdir(repo_name)
        commit_output = subprocess.check_output("git show | awk '/commit/ {print $2}'", shell=True)
        commit = commit_output.decode("utf-8").rstrip("\n")
        result["commit"] = commit
        output = subprocess.check_output("git pull", shell=True, encoding="utf-8").rstrip("\n")
        logger.info(output)
        if output.lower() == "already up to date.":
            logger.info(f"{repo_name} already up to date.")
            result["updated"] = False
        else:
            result["updated"] = True
        os.chdir("..")
    else:
        logger.info("repo directory not exist, attempting git clone")
        user_token = os.getenv("GITHUB_USER_TOKEN")
        clone_str = f"git clone https://{user_token}@{uri}"
        os.system(clone_str)
        os.chdir(repo_name)
        output = subprocess.check_output("git show | awk '/commit/ {print $2}'", shell=True)
        logger.info(output)
        new_commit = output.decode("utf-8").rstrip("\n")
        result = {"commit": new_commit}
    return result


async def sync_standards():
    logger.info("Fn: syncing standards & infra repo")
    try:
        final_resp = {}
        sync_dir = await setup_sync_dir()
        for k, v in standards_repo.items():
            standards_dir = f"{sync_dir}/standards"
            if not os.path.isdir(standards_dir):
                os.mkdir(standards_dir)
            os.chdir(standards_dir)
            final_resp[k] = await clone_repo(v)
        return final_resp
    except Exception as e:
        msg = f"Failed to sync standards: {e}"
        logger.error(msg)
        body = f"<html><body style='color:red;'>{msg}</body></html>"
        send_email("chirag_patel@example.com", "BMI API - Failed to sync standards repo", body)
        send_email("david_m_blasing@example.com", "BMI API - Failed to sync standards ", body)
        send_email("ops-notify@example.com", "BMI API - Failed to sync standards repo", body)
        raise HTTPException(status_code=400, detail=msg)


async def sync_postbuild():
    try:
        logger.info("Fn: syncing postbuild cookbooks")
        final_resp = {}
        sync_dir = await setup_sync_dir()
        for k, v in postbuild_repo.items():
            postbuild_dir = f"{sync_dir}/postbuild"
            if not os.path.isdir(postbuild_dir):
                os.mkdir(postbuild_dir)
            os.chdir(postbuild_dir)
            final_resp[k] = await clone_repo(v)
        # create tar file from postbuild items
        os.chdir(postbuild_dir)
        with tarfile.open("postbuild.tar", "w:gz") as tar:
            source_dir = f"{sync_dir}/postbuild"
            tar.add(source_dir, arcname=os.path.basename(source_dir))
        return final_resp
    except Exception as e:
        msg = f"Failed to sync standards: {e}"
        logger.error(msg)
        body = f"<html><body style='color:red;'>{msg}</body></html>"
        send_email("chirag_patel@example.com", "BMI API - Failed to sync postbuild repo", body)
        send_email("david_m_blasing@example.com", "BMI API - Failed to sync postbuild repo", body)
        raise HTTPException(status_code=400, detail=msg)
