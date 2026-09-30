import logging
from json import dumps

from kafka import KafkaProducer

import app.build_service.loran_service as loran_service
import app.build_service.mail_service as mail_service
import app.build_service.splunk_service as splunk_service
import app.build_service.status_service as status_service
import app.config.config as config
from app.common.domain.build_statuses import BuildStatuses

logger = logging.getLogger(__name__)


def add_status_event(build_id, event):
    settings = config.get_setting()
    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda x: x.dumps(),
        batch_size=settings.kafka_producer_batch_size,
        key_serializer=lambda x: dumps(x).encode("utf-8"),
    )
    logger.info(f"sending event to build_events topic for {build_id} with status {event.status}")
    producer.send("build_events", key=build_id, value=event)


def append_build_event(build, status, status_detail):
    host = build["build_details"]["host"]
    build_id = build["id"]
    build_event = {
        "status": status,
        "status_detail": status_detail,
        "build_type": build["build_type"],
        "host": host,
        "requestor": build["requestor"],
        "metadata": build.get("metadata", {}),
    }
    splunk_service.send_to_splunk(build, status, status_detail)
    status_service.add_build_event(build_id=build_id, event=build_event)
    loran_service.update_loran_hostdata(host, {"build_status": status})
    no_email_env = ["local"]
    if (
        status in (BuildStatuses.ABORTED.value, BuildStatuses.COMPLETE.value, BuildStatuses.ERROR.value)
        and build["bmi_env"] not in no_email_env
    ):
        build_event["build_id"] = build_id
        try:
            mail_service.sendMail(build_event)
        except Exception:
            logger.info("problem with mail service...continuing")
