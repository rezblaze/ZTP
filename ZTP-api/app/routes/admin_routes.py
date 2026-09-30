import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.common.domain.build_statuses import BuildStatuses
from app.common.domain.build_types import BuildTypes
from app.dto.build_event_dto import BuildEventDto
from app.dto.status_response import StatusUriResponse
from app.modules.sync_mod import sync_postbuild, sync_standards
from app.security import auth_service
from app.service import build_service, status_service

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginDto(BaseModel):
    username: str
    password: str


@router.post("/builds/test", tags=["Test"])
async def create_e2e_test(requestor: dict = Depends(auth_service.validate_and_get_username)):
    """
    only for developers to use
    """
    build_details_dict = {"host": "fake_hostname", "sleep": 15, "cycle": 4}
    build_id = await build_service.create_test_build(BuildTypes.BUILDS_TEST.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.put(
    "/builds/events/{build_id}",
    tags=["Events"],
    include_in_schema=True,
)
async def add_build_event(
    build_id: str,
    event: BuildEventDto,
    requestor: str = Depends(auth_service.validate_and_get_username),
):
    """
    <h3>Add specific status event for build_id</h3>
        **QUEUED** => build is queued in and waitting for builder to process
        **PROCESSING** => build is processing
        **COMPLETE** => build is completed successfully
        **ERROR** => build failed
        **ABORTING** => aborting build on user request
        **ABORTED** =>  build aborted on user request
    """
    await status_service.add_build_event(build_id, event.dict())
    return StatusUriResponse(status=f"event added for {build_id} by {requestor}")


@router.get("/builds/allbuilds", tags=["Metrics"], response_description="All current builds", include_in_schema=True)
async def get_all_builds():
    return await status_service.get_all_builds()


@router.get("/builds/allevents", tags=["Metrics"], response_description="All build events", include_in_schema=True)
async def get_all_build_events():
    return await status_service.get_all_build_events()


@router.get(
    "/builds/allqueued",
    tags=["Metrics"],
    response_description="All currently queued builds",
    include_in_schema=True,
)
async def get_all_queued_builds():
    return await status_service.get_all_status_build_events(BuildStatuses.QUEUED.value)


@router.get(
    "/builds/allprocessing",
    tags=["Metrics"],
    response_description="All currently processing builds",
    include_in_schema=True,
)
async def get_all_processing_builds():
    return await status_service.get_all_status_build_events(BuildStatuses.PROCESSING.value)


@router.get(
    "/builds/allcompleted",
    tags=["Metrics"],
    response_description="All currently completed builds",
    include_in_schema=True,
)
async def get_all_complete_builds():
    return await status_service.get_all_status_build_events(BuildStatuses.COMPLETE.value)


@router.get(
    "/builds/allerror",
    tags=["Metrics"],
    response_description="All error builds",
    include_in_schema=True,
)
async def get_all_complete_builds():
    return await status_service.get_all_status_build_events(BuildStatuses.ERROR.value)


@router.get(
    "/builds/allaborted",
    tags=["Metrics"],
    response_description="All aborted builds",
    include_in_schema=True,
)
async def get_all_complete_builds():
    return await status_service.get_all_status_build_events(BuildStatuses.ABORTED.value)


@router.post(
    "/sync/standards",
    tags=["Sync"],
    response_description="sync stanadards repository",
    include_in_schema=True,
)
async def sync_standard_github_repository():
    """
    <h2><b>sync standard repository below</b></h2>
    - https://github.com/company-org/HPE-Standard.git
    - https://github.com/company-org/Dell_Standards.git
    - https://github.example.com/example-org/ztp-infra.git

    <b>sync location</b>: /pub/tools/github/standards
    """
    return await sync_standards()


@router.post(
    "/sync/postbuild",
    tags=["Sync"],
    response_description="sync postbuild config repository",
    include_in_schema=True,
)
async def sync_postbuild_github_repository():
    """
    <h2><b>sync postbuild repository below</b></h2>
    - https://github.com/company-org/company-ansible.git
    - https://github.com/company-org/compliance_make_backup.git
    - https://github.com/company-org/doesapi_client_handler.git
    - https://github.com/company-org/company_compliance_standard_baseline.git
    - https://github.com/company-org/company_patch_utils.git
    - https://github.com/company-org/company_rhel_qas.git
    - https://github.com/company-org/company_rhel_standard.git
    - https://github.com/company-org/company_rsyslog_config.git
    - https://github.com/company-org/line.git
    - https://github.com/company-org/company_satellite_reg.git

    <b>sync location</b>: /pub/tools/github/postbuild

    <b>compressed tar ball</b>: /pub/tools/github/postbuild/postbuild.tar
    """
    return await sync_postbuild()


@router.post("/auth/login_for_ui", tags=["Authentication"])
async def login(login: LoginDto):
    """
    <h2><b>User login</b></h2>
    - *payload*
        - **username**: user's username
        - **password**: user's password
    """
    try:
        username = base64.b64decode(login.username).decode("utf-8")
        password = base64.b64decode(login.password).decode("utf-8")
    except:
        username = login.username
        password = login.password
    sanitized_username = username.replace("\n", "").replace("\r", "")
    logger.info(f"username: {sanitized_username} attempting to login")
    authenticated_user = await auth_service.authenticate_and_get_connection(username, password)
    if not authenticated_user:
        logger.info(f"username: {sanitized_username} authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(f"username: {sanitized_username} authentication successful")
    return {"user": sanitized_username, "status": "authentication successful"}
