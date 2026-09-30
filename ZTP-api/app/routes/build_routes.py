import logging

from fastapi import APIRouter, Depends

from app.common.domain.build_types import BuildTypes
from app.dto.server_build_dto import EsxiBuildDto, LinuxBuildDto, WindowsBuildDto
from app.dto.status_response import StatusUriResponse
from app.security import auth_service
from app.service import build_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/builds/linux",
    tags=["Server Builds"],
)
async def create_linux_provisioning(
    build: LinuxBuildDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2><b>Linux image on baremetal server with some role option</b></h2>
    - *payload*
        - **host**: fully qualified domain name of server/host
        - **os**: rhel-9.6, rocky-9.6, rhel-8.10, rocky-8.10
        - **attributes**:
            - **role**: anthos, hcc, splunk, bdpaas, emb, pep-ece, shop_admin, base
            - **dataraid**: "",0, 1, 5, 6, 10

    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BUILDS_LINUX.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.post("/builds/windows", tags=["Server Builds"])
async def create_windows_provisioning(
    build: WindowsBuildDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2><b>Windows image on baremetal server</b></h2>
    - *payload*
        - **host**: fully qualified domain name of server/host
        - **os**: win2019, win2022, win2022core
        - **attributes**:
            - **env**: prod, stage, test, dev
            - **computerdomain**: computer domain to join
            - *additional parameter can be added if necessary*
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BUILDS_WINDOWS.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.post("/builds/esxi", tags=["Server Builds"])
async def create_esxi_provisioning(
    build: EsxiBuildDto, requestor: dict = Depends(auth_service.validate_and_get_username)
):
    """
    <h2><b>ESXi image on baremetal server</b></h2>
    - *attributes*
        - **host**: fully qualified domain name of server/host
        - **os**: Check  [SupportedEsxiOs] section below
        - **vlan**: optional, default value is "3020" for ODI
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BUILDS_ESXI.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")
