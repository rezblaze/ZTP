import logging

from fastapi import APIRouter, Depends, Response, status

from app.common.domain.build_statuses import BuildStatuses
from app.common.service import sanity
from app.modules.networkdata import networkdata
from app.modules.serverinfo import serverinfo
from app.security import auth_service
from app.service import status_service
from app.service.loran_service import get_loran_hostdata

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/networkdata/{host}",
    tags=["Useful"],
    response_description="Host network related data",
)
async def get_networkdata(host: str, response: Response):
    host = await sanity.sanity_check(host)
    data = await networkdata(host)
    if data["STATUS"] == BuildStatuses.ERROR.value:
        response.status_code = status.HTTP_424_FAILED_DEPENDENCY
    return data


@router.get(
    "/serverinfo/{host}",
    tags=["Useful"],
    response_description="Host network related data",
)
async def get_serverinfo(host: str, response: Response):
    host = await sanity.sanity_check(host)
    data = await serverinfo(host)
    if data["STATUS"] == BuildStatuses.ERROR.value:
        response.status_code = status.HTTP_424_FAILED_DEPENDENCY
    return data


@router.get(
    "/loran/{host}",
    tags=["Useful"],
    response_description="Host loran data",
)
async def get_lorandata(host: str, response: Response):
    # host = await sanity.sanity_check(host)
    data = get_loran_hostdata(host)
    return data


@router.get(
    "/myrequeststoday",
    tags=["Useful"],
    response_description="my requests for today",
)
async def get_my_requests_for_today(
    username: str = Depends(auth_service.validate_and_get_username),
):
    return await status_service.get_my_current_build_events(username)


@router.get(
    "/builds/by/{username}/today",
    tags=["Useful"],
    response_description="builds today",
)
async def get_my_requests_today(username: str):
    return await status_service.get_my_build_events(username, 0)


@router.get(
    "/builds/by/{username}/lastweek",
    tags=["Useful"],
    response_description="builds last week",
)
async def get_my_7days_build_events(username: str):
    return await status_service.get_my_build_events(username, 7)
