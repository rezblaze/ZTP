import json
import logging
import os
from typing import Dict, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    responses,
    status,
)

from app.common.domain.build_statuses import BuildStatuses
from app.common.service import sanity
from app.config import config
from app.modules._helper import set_min_networkdata
from app.modules.adminlo import AdminLOManager
from app.modules.eskm import eskm_main
from app.modules.monolith import fetch_endpoint_data
from app.modules.oneview import OneViewAPI
from app.modules.servercheck import get_oneview_server
from app.security import auth_service
from app.service.mail_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.patch(
    "/iLO/ESKM/cert/{host}",
    tags=["ESKM"],
    response_description="Patch ESKM settings",
)
async def patch_eskm_settings(
    host: str,
    response: Response,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    data = await eskm_main(host, username, password, operation="patch")
    if data.status == BuildStatuses.ERROR:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return data


@router.get(
    "/iLO/ESKM/status/{host}",
    tags=["ESKM"],
    response_description="Get ESKM settings",
)
async def get_eskm_settings(
    host: str,
    response: Response,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    data = await eskm_main(host, username, password, operation="get")
    if data.status == BuildStatuses.ERROR:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return data


@router.post("/iLO/fetch_host_data/{lom_host}", tags=["LOM other operations"])
async def fetch_endpoint_data_route(
    lom_host: str,
    endpoints: Dict[str, bool] = Body(
        {
            "AccountService": True,
            "Bios": True,
            "EthernetInterface": True,
            "HpeESKM": True,
            "HpeiLODateTime": True,
            "HpeiLOLicense": True,
            "HpeiLOSSO": True,
            "Manager": True,
            "ManagerAccount": True,
            "ManagerNetworkProtocol": True,
            "FirmwareInventory": True,
            "SoftwareInventory": True,
            "EthernetInterfaces": True,
            "Storage": True,
            "Memory": True,
            "Processors": True,
        }
    ),
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    data = await fetch_endpoint_data(lom_host, endpoints, username, password)
    return data


@router.get(
    "/lom/adminlo/credcheck/{host}",
    tags=["LOM User operations"],
    response_description="Check Adminlo account using current password",
)
async def check_adminlo_credentials(
    host: str,
    response: Response,
):
    data = await AdminLOManager().check_adminlo_creds(host)
    if data.status.value != BuildStatuses.PASS.value:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return data


@router.patch(
    "/lom/adminlo/credpatch/{host}",
    tags=["LOM User operations"],
    response_description="Adminlo account fix cred and if adminlo not exit create account, if companylo exist remove",
)
async def patch_adminlo_credentials(
    host: str,
    response: Response,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    data = await AdminLOManager().patch_creds(host, username, password)
    if data.status.value != BuildStatuses.SUCCESS.value:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return data


@router.patch(
    "/lom/adminlo/adduser/{host}",
    tags=["LOM User operations"],
    response_description="Add Adminlo account",
)
async def add_adminlo_user(
    host: str,
    response: Response,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    data = await AdminLOManager().add_adminlo_account(host, username, password)
    if data.status.value != BuildStatuses.SUCCESS.value and data.status.value != BuildStatuses.PASS.value:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return data


@router.delete(
    "/lom/companylo/removeuser/{host}",
    tags=["LOM User operations"],
    response_description="Remove companylo account",
)
async def delete_companylo_user(
    host: str,
    response: Response,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    data = await AdminLOManager().remove_companylo_account(host, username, password)
    if data.status.value != BuildStatuses.SUCCESS.value and data.status.value != BuildStatuses.PASS.value:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return data


@router.post(
    "/upload",
    tags=["File upload"],
    response_description="upload file to /pub NAS mount",
)
async def upload_file_to_pub(
    file: UploadFile = File(...), requestor: dict = Depends(auth_service.validate_and_get_username)
):
    settings = config.get_setting()
    if settings.bmi_env == "local":
        logger.warning("File upload is disabled in local environment.")
        return responses.JSONResponse(
            content={"error": "File upload is disabled in local environment."},
            status_code=status.HTTP_403_FORBIDDEN,
        )
    UPLOAD_DIR = "/pub/upload"
    try:
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        # Save the uploaded file
        with open(file_location, "wb") as f:
            f.write(await file.read())
        # Prepare email data
        data = {
            "filename": file.filename,
            "content_type": file.content_type,
            "userid": requestor["requestor_id"],
            "email": requestor["requestor_mail"],
        }
        str_data = json.dumps(data, indent=4)

        # Send emails
        recipients = [
            requestor["requestor_mail"],
            "chirag_patel@example.com",
            "david_m_blasing@example.com",
        ]
        for recipient in recipients:
            send_email(recipient, "File uploaded to /pub NAS mount", str_data)

        return responses.JSONResponse(content=data)
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return responses.JSONResponse(
            content={"error": "File upload failed", "details": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/iLO/oneview/{ilo}",
    tags=["LOM other operations"],
    response_description="Get oneview server name",
)
async def get_sso_servername(
    ilo: str,
    response: Response,
    ilo_user: Optional[str] = None,
    ilo_passwd: Optional[str] = None,
):
    return await get_oneview_server(ilo, ilo_user, ilo_passwd)


@router.post(
    "/oneview/firmware_compliance_report/{host}",
    tags=["OneView Operations"],
    response_description="Get firmware compliance report from OneView  for given server name",
)
# async def generate_oneview_report(app: str, username: str, password: str, host: str, generation: str):
async def generate_oneview_report(host: str):
    """Generate a firmware compliance report for a server managed by HPE OneView."""
    try:
        host = await sanity.sanity_check(host)
        netdata = await set_min_networkdata(host)
        ovdata = await get_oneview_server(netdata["LOMIP"])
        if ovdata["status"] == "SUCCESS":
            ovapp = ovdata["detail"]["ServerName"]
            logger.info(f"OneView Appliance: {ovapp}")
            api = OneViewAPI(ovapp)
            return await api.get_firmware_compliance_report(netdata["SHORT_NAME"])
        else:
            raise Exception("OneView appliance not found")
            # print("OneView appliance not found, adding to lab oneview")
            # result = api.add_server(netdata["LOM_FQDN"])
            # print(result)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/oneview/lab/add/{host}",
    tags=["OneView Operations"],
    response_description="Add server to OneView vmwo-l053-001.mslab.dslab.lab.example.com",
)
async def add_server_to_oneview(host: str):
    """Add a server to HPE OneView."""
    try:
        host = await sanity.sanity_check(host)
        netdata = await set_min_networkdata(host)
        ovdata = await get_oneview_server(netdata["LOMIP"])
        if ovdata["status"] == "SUCCESS":
            raise HTTPException(status_code=404, detail="OneView appliance found")
        ovapp = "vmwo-l053-001.mslab.dslab.lab.example.com"
        api = OneViewAPI(ovapp)
        result = await api.add_server(netdata["LOM_FQDN"])
        return {"status": "SUCCESS", "detail": result, "host": host, "ovapp": ovapp}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/oneview/lab/remove/{host}",
    tags=["OneView Operations"],
    response_description="Delete server from OneView vmwo-l053-001.mslab.dslab.lab.example.com",
)
async def del_server_to_oneview(host: str):
    """Delete a server to HPE OneView."""
    try:
        host = await sanity.sanity_check(host)
        netdata = await set_min_networkdata(host)
        ovdata = await get_oneview_server(netdata["LOMIP"])
        if ovdata["status"] != "SUCCESS":
            raise HTTPException(status_code=404, detail="This server is not managed by OneView appliance")
        ovapp = "vmwo-l053-001.mslab.dslab.lab.example.com"
        api = OneViewAPI(ovapp)
        result = await api.delete_server(netdata["SHORT_NAME"])
        return {"status": "SUCCESS", "detail": result, "host": host, "ovapp": ovapp}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
