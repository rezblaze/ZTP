from datetime import datetime

import app.build_service.kafka_service as kafka_service
from app.common.domain.build_event import BuildEvent


def add_build_event(build_id, event):
    build_time = datetime.now().isoformat()
    status_detail = event["status_detail"] if "status_detail" in event else ""
    host = event["host"] if "host" in event else ""
    requestor = event["requestor"] if "requestor" in event else ""
    metadata = event["metadata"] if "metadata" in event else {}
    build_type = event["build_type"] if "build_type" in event else ""
    event = BuildEvent(
        status=event["status"],
        status_detail=status_detail,
        build_id=build_id,
        build_type=build_type,
        host=host,
        time=build_time,
        requestor=requestor,
        metadata=metadata,
    )
    kafka_service.add_status_event(build_id, event)
