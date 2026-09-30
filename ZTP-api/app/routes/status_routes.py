import logging

from fastapi import APIRouter

from app.service import status_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/builds/status/{build_id}",
    tags=["Build Status"],
    response_description="Current status of build",
)
async def get_build_status(build_id: str):
    """
    <h3><b>Latest build status for build_id</b></h3>
        **QUEUED** => build is queued in and waitting for builder to process
        **PROCESSING** => build is processing
        **COMPLETE** => build is completed successfully
        **ERROR** => build failed
        **ABORTING** => aborting build on user request
        **ABORTED** =>  build aborted on user request
    """
    return await status_service.get_status(build_id)


@router.get(
    "/builds/events/{build_id}",
    tags=["Build Status"],
    response_description="Current status of build",
)
async def get_all_build_id_events(build_id: str):
    """
    <h3>All events for build_id</h3>
        **QUEUED** => build is queued in and waitting for builder to process
        **PROCESSING** => build is processing
        **COMPLETE** => build is completed successfully
        **ERROR** => build failed
        **ABORTING** => aborting build on user request
        **ABORTED** =>  build aborted on user request
    """
    return await status_service.get_build_events(build_id)
