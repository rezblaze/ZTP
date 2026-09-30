from pydantic import BaseModel

from app.common.domain.build_statuses import BuildStatuses


class StatusResponse(BaseModel):
    status: BuildStatuses
    host: str = ""
    status_detail: str = ""
    requestor: str = ""
    time: str = ""
    metadata: dict = {}


class StatusUriResponse(BaseModel):
    status: str
