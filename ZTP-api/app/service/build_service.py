import uuid
from datetime import datetime

from fastapi import HTTPException

from app.common.domain.build_statuses import BuildStatuses
from app.common.domain.build_types import BuildTypes
from app.common.domain.server_build import ServerBuild
from app.common.domain.supported_payload import SupportedLinuxOs
from app.common.service import sanity
from app.config import config
from app.dto.status_response import StatusUriResponse
from app.modules.networkdata import networkdata
from app.modules.serverinfo import serverinfo
from app.service import kafka_service, status_service

settings = config.get_setting()

RUNNING_BUILD_STATUSES = [BuildStatuses.QUEUED.value, BuildStatuses.PROCESSING.value, BuildStatuses.ABORTING.value]

DONT_ABORT_STATUSES = [
    BuildStatuses.COMPLETE.value,
    BuildStatuses.ERROR.value,
    BuildStatuses.ABORTING.value,
    BuildStatuses.ABORTED.value,
]

LINUX_CURRENT = [
    SupportedLinuxOs.RHEL810,
    SupportedLinuxOs.ROCKY810,
    SupportedLinuxOs.RHEL96,
    SupportedLinuxOs.ROCKY96,
]


async def validate_build(build: dict):
    host = await sanity.sanity_check(build["host"])
    build["host"] = host
    return build


async def create_build(build_type, build_details, requestor):
    await ok_to_run_build(build_details)
    # get networkdata
    networkdata_resp = await networkdata(build_details["host"])
    if networkdata_resp["STATUS"] == BuildStatuses.ERROR.value:
        msg = f"Error retrieve networkdata! error_detail: {networkdata_resp['ERROR_DETAIL']}"
        raise HTTPException(status_code=424, detail=msg)
    # check if server type is valid for the endpoint
    if (
        build_type
        in (
            BuildTypes.BASELINE_HP_SPP.value,
            BuildTypes.BASELINE_HPE_BIOS.value,
            BuildTypes.BASELNE_HPE_ILO.value,
            BuildTypes.BASELINE_HP_CHECKFIRMWARE.value,
        )
        and networkdata_resp["HARDWARE"].startswith("hp") is False
    ):
        msg = f"host provided {build_details['host']} is {networkdata_resp['HARDWARE']}, wrong server type for this endpoint"
        raise HTTPException(status_code=424, detail=msg)
    if build_type in (BuildTypes.BASELINE_DELL_IDRAC) and networkdata_resp["HARDWARE"].startswith("dell") is False:
        msg = f"host provided {build_details['host']} is {networkdata_resp['HARDWARE']}, wrong server type for this endpoint"
        raise HTTPException(status_code=424, detail=msg)
    if build_type == BuildTypes.BUILDS_WINDOWS.value and networkdata_resp["HARDWARE"].startswith("dell"):
        msg = f"host provided {build_details['host']} is {networkdata_resp['HARDWARE']}, Windows builds are not supported on Dell hardware"
        raise HTTPException(status_code=424, detail=msg)
    # check is requested os is latest or not
    if build_type == BuildTypes.BUILDS_LINUX.value:
        os = build_details["os"]
        override = build_details["override"]
        if os not in LINUX_CURRENT and override.get("legecyos") is not True:
            msg = f"{os.value} requested operating system is not current, still be able to install if override is used. please reach out to BMI team"
            raise HTTPException(status_code=424, detail=msg)
        build_details["isoimage"] = SupportedLinuxOs.get_iso_name(os)
    # get serverinfo
    serverinfo_resp = await serverinfo(build_details["host"])
    if serverinfo_resp["STATUS"] == BuildStatuses.ERROR.value:
        msg = f"Error retrieve serverinfo! error_detail: {networkdata_resp['ERROR_DETAIL']}"
        raise HTTPException(status_code=424, detail=msg)
    # check if TPM exists
    if build_type == BuildTypes.BUILDS_ESXI.value:
        # check esxi image and hardware
        os = build_details["os"].value
        os_image = os.split("-")[-1]
        if os_image.lower() not in networkdata_resp["HARDWARE"]:
            msg = f"{os} is incorrect image, {networkdata_resp['SERVERNAME']} server is {networkdata_resp['HARDWARE']}"
            raise HTTPException(status_code=424, detail=msg)
        tpm = serverinfo_resp["TRUSTEDMODULES"][0]
        try:
            if tpm["InterfaceType"] == None:
                msg = f"issue with the TPM module need to be addressed! {tpm}"
                raise HTTPException(status_code=424, detail=msg)
        except KeyError as err:
            msg = f"issue with the TPM module need to be addressed! KeyError: missing {err}"
            raise HTTPException(status_code=424, detail=msg)
    # check power status
    if build_type not in (
        BuildTypes.BASELNE_HPE_ILO.value,
        BuildTypes.BASELINE_DELL_IDRAC.value,
        BuildTypes.BASELINE_HP_CHECKFIRMWARE.value,
    ):
        if build_type == BuildTypes.BASELINE_HPE_BIOS.value and build_details.get("apply_hpe_bios_baseline") is False:
            print("HPE BIOS baseline not applied, skipping power check")

        else:
            await sanity.check_power(serverinfo_resp)
    build_id = str(uuid.uuid4())
    build_event = {
        "status": BuildStatuses.QUEUED,
        "host": build_details["host"],
        "status_detail": "build is QUEUED, api requested builder service to process build",
        "requestor": requestor,
    }
    build_entry = ServerBuild(
        bmi_env=settings.bmi_env,
        id=build_id,
        build_details=build_details,
        time=datetime.now().isoformat(),
        host=build_details["host"],
        requestor=requestor,
        build_type=build_type,
        networkdata=networkdata_resp,
        serverinfo=serverinfo_resp,
    )
    print(f"create_build: {build_entry}")
    await status_service.add_build_event(build_id, build_event)
    await kafka_service.queue_build(build_entry)
    return build_id


async def ok_to_run_build(build_details):
    builds = await kafka_service.get_host_builds(build_details["host"])
    if len(builds) != 0:
        builds.sort(key=lambda build: build["time"], reverse=True)
        latest_build_id = builds[0]["id"]
        latest_build = await status_service.get_latest_build_event(latest_build_id)
        if latest_build["status"] in RUNNING_BUILD_STATUSES:
            error_detail = {
                "message": f"build for {build_details['host']} is already in state: {latest_build['status']}",
                "existing_build_uri": f"/builds/status/{latest_build_id}",
            }
            raise HTTPException(status_code=409, detail=error_detail)


async def create_abort_build(build_id):
    status = await status_service.get_status(build_id)
    do_not_power_off_builds = [
        BuildTypes.BASELNE_HPE_ILO.value,
        BuildTypes.BASELINE_DELL_IDRAC.value,
        BuildTypes.BASELINE_HP_CHECKFIRMWARE.value,
    ]
    if status["status"] in DONT_ABORT_STATUSES:
        error_detail = {"message": f"Build {status['build_id']} already {status['status']}"}
        raise HTTPException(status_code=208, detail=error_detail)
    if status["build_type"] in do_not_power_off_builds:
        error_detail = {
            "message": f"build id {status['build_id']} is build type {status['build_type']} and can NOT be ABORTED"
        }
        raise HTTPException(status_code=208, detail=error_detail)
    resp = ""
    if status["status"] == BuildStatuses.QUEUED.value:
        build_event = {
            "status": BuildStatuses.ABORTED,
            "host": status["host"],
            "status_detail": "build was queued and aborted per request",
            "requestor": status["requestor"],
        }
        await status_service.add_build_event(build_id, build_event)
        resp = "build aborted successfully"
    if status["status"] == BuildStatuses.PROCESSING.value:
        abort_build_details = {
            "host": status["host"],
            "cpid_to_kill": status.get("metadata", {}).get("cpid", {}),
            "initial_build": status["status_detail"],
        }
        if status["metadata"].get("jenkins_job_url"):
            abort_build_details["jenkins_job_url"] = status["metadata"]["jenkins_job_url"]
        build_entry = ServerBuild(
            bmi_env=settings.bmi_env,
            id=build_id,
            build_details=abort_build_details,
            time=datetime.now().isoformat(),
            host=status["host"],
            requestor=status["requestor"],
            build_type="abort_build",
        )
        build_event = {
            "status": BuildStatuses.ABORTING,
            "host": status["host"],
            "status_detail": "build abort request initiated",
            "requestor": status["requestor"],
            "initial_build": status["status_detail"],
        }
        await status_service.add_build_event(build_id, build_event)
        await kafka_service.queue_build(build_entry)
        resp = "build ABORT process initiated"
    return StatusUriResponse(status=resp)


async def create_test_build(build_type, build_details, requestor):
    build_id = str(uuid.uuid4())
    build_event = {
        "status": BuildStatuses.QUEUED,
        "host": build_details["host"] + build_id.split("-")[-1],
        "status_detail": "build is QUEUED, api requested builder service to process build",
        "requestor": requestor,
    }
    build_entry = ServerBuild(
        bmi_env=settings.bmi_env,
        id=build_id,
        build_details=build_details,
        time=datetime.now().isoformat(),
        host=build_details["host"],
        requestor=requestor,
        build_type=build_type,
        networkdata={},
    )
    print(f"create_build: {build_entry}")
    await status_service.add_build_event(build_id, build_event)
    await kafka_service.queue_build(build_entry)
    return build_id
