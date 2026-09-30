import logging

from fastapi import APIRouter, Depends

from app.security import auth_service
from app.service import build_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/builds/abort/{build_id}", tags=["Abort"])
async def abort_running_build(build_id: str, requestor: str = Depends(auth_service.validate_and_get_username)):
    """
    <h3>Abort build for build_id</h3>
    Stop build and poweroff server
    """
    return await build_service.create_abort_build(build_id)
