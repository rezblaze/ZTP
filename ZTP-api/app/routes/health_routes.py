import logging
import os
import subprocess

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health():
    if not os.path.exists("/usr/bin/systemctl"):
        raise HTTPException(status_code=404, detail="Systemctl not installed")
    bmi_api_status = {}
    bmi_builder_status = {}
    kafka_status = {}
    nginx_status = {}
    result = {}
    # see if bmi-service running
    if os.system("systemctl status bmi-service") == 0:
        BMIAPI_VERSION = None
        if os.path.exists("/opt/bmi/bmi-service/version.text"):
            f = open("/opt/bmi/bmi-service/version.text", "r")
            BMIAPI_VERSION = f.read().split("=")[1].strip()
            f.close()
            BMIAPI_BRANCH = os.popen("cd /opt/bmi/bmi-service; git branch --show-current").read()
            bmi_api_status = {
                "status": "up",
                "detail": {"version": BMIAPI_VERSION.strip(), "branch": BMIAPI_BRANCH.strip()},
            }
    else:
        bmi_api_status = {"status": "down"}

    # see if bmi-builder running
    if os.system("systemctl status bmi-builder") == 0:
        BMIBUILDER_VERSION = None
        if os.path.exists("/opt/bmi/bmi-builder/version.text"):
            f = open("/opt/bmi/bmi-builder/version.text", "r")
            BMIBUILDER_VERSION = f.read().split("=")[1].strip()
            f.close()
            BMIBUILDER_BRANCH = os.popen("cd /opt/bmi/bmi-builder; git branch --show-current").read()
            bmi_builder_status = {
                "status": "up",
                "detail": {"version": BMIBUILDER_VERSION.strip(), "branch": BMIBUILDER_BRANCH.strip()},
            }
    else:
        bmi_builder_status = {"status": "down"}

    # see if kafka running
    check = 1
    if os.path.exists("/usr/bin/podman"):
        check = os.system("podman ps | grep kafka")
    if os.path.exists("/usr/bin/docker"):
        check = os.system("sudo docker ps | grep kafka")
    if check == 0:
        kafka_status = {"status": "up"}
    else:
        kafka_status = {"status": "down"}

    if os.system("systemctl status nginx") == 0:
        nginx_status = {"status": "up"}
    else:
        nginx_status = {"status": "down"}
    if (
        bmi_api_status["status"] == "up"
        and bmi_builder_status["status"] == "up"
        and kafka_status["status"] == "up"
        and nginx_status["status"] == "up"
    ):
        result = {"health": "ok"}
    else:
        result = {"health": "degraded"}
    result.update(
        {
            "bmi api": bmi_api_status,
            "bmi builder": bmi_builder_status,
            "kafka": kafka_status,
            "nginx": nginx_status,
        }
    )
    return result


@router.get("/monit", tags=["Health"])
async def monit():
    if not os.path.exists("/usr/bin/monit"):
        raise HTTPException(status_code=404, detail="Monit not installed")
    try:
        subprocess.run(["which", "monit"], check=True)
        result = subprocess.run(["sudo", "monit", "summary"], capture_output=True, text=True)
        op = result.stdout
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Split the summary into lines
    monit_summary = op.strip().split("\n")
    # Extract the header and data lines
    header_line = monit_summary[1]
    data_lines = monit_summary[2:]

    # Extract the column names from the header line
    columns = [col.strip() for col in header_line.split() if col.strip()]
    columns.remove("Name")
    # Extract the data rows
    data_rows = []
    for line in data_lines:
        row = [col.strip() for col in line.split() if col.strip()]
        data_rows.append(row)

    # Convert the data to a list of dictionaries
    data_dicts = [dict(zip(columns, row)) for row in data_rows]

    return data_dicts
