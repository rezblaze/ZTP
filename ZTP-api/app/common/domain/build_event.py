from faust import Record

from app.common.domain.build_statuses import BuildStatuses


class BuildEvent(Record, serializer="json"):
    status: BuildStatuses
    status_detail: str
    build_id: str
    build_type: str
    host: str
    time: str
    requestor: dict
    metadata: dict

    def as_dict(self):
        return {
            "status": self.status,
            "status_detail": self.status_detail,
            "build_id": self.build_id,
            "build_type": self.build_type,
            "host": self.host,
            "time": self.time,
            "requestor": self.requestor,
            "metadata": self.metadata,
        }
