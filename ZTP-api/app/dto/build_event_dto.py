from pydantic import BaseModel

from app.common.domain.build_statuses import BuildStatuses


class BuildEventDto(BaseModel):
    status: BuildStatuses = BuildStatuses.ERROR.value
    build_id: str
    host: str
    status_detail: str
    time: str
    requestor: dict
    metadata: dict
