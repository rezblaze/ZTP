import logging
from typing import Optional

import faust

from app.common.domain.build_event import BuildEvent
from app.common.domain.server_build import ServerBuild
from app.config import config

settings = config.get_setting()

logger = logging.getLogger(__name__)

faust_app: Optional[faust.App] = None

build_events_topic = None
build_events = None
server_builds_topic = None
server_builds = None


def setup_faust_app(loop):
    global faust_app, build_events_topic, build_events, server_builds_topic, server_builds

    faust_app = faust.App(
        "bmi_api", broker=settings.kafka_broker, debug=True, loop=loop, producer_max_request_size=11534336
    )

    build_events_topic = faust_app.topic("build_events", key_type=str, value_type=BuildEvent)
    build_events = faust_app.Table("events_for_builds", default=list)

    server_builds_topic = faust_app.topic("server_builds", key_type=str, value_type=ServerBuild)
    server_builds = faust_app.Table("builds_by_host", default=list)

    @faust_app.agent(build_events_topic)
    async def group_build_events(stream):
        try:
            async for event in stream.group_by(BuildEvent.build_id):
                events = build_events[event.build_id]
                events.append(event.as_dict())
                build_events[event.build_id] = events
                print("fn:group_build_events: processing event")
        except Exception as exception:
            logger.error(f"error in group_build_events: {str(exception)}")

    @faust_app.agent(server_builds_topic)
    async def group_server_builds(stream):
        try:
            async for build in stream.group_by(ServerBuild.host):
                host_builds = server_builds[build.host]
                host_builds.append(build.as_dict())
                server_builds[build.host] = host_builds
                logger.info(str(host_builds))
        except Exception as exception:
            logger.error(f"Error in group_server_builds: {str(exception)}")

    return faust_app


async def queue_build(server_build):
    logger.info(f"Sending event to server_builds topic for host {server_build.host}")
    await server_builds_topic.send(key=server_build.host, value=server_build)


async def add_status_event(build_id, event):
    await build_events_topic.send(key=build_id, value=event)


async def get_build_events(build_id):
    return build_events[build_id]


async def get_host_builds(host):
    return server_builds[host]


async def get_all_builds():
    return server_builds


async def get_all_build_events():
    return build_events
