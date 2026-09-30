from datetime import date, datetime

from dateutil.parser import parse
from fastapi import HTTPException

from app.common.domain.build_event import BuildEvent
from app.common.domain.build_statuses import BuildStatuses
from app.common.service import date_util
from app.service import kafka_service

BUILD_TIMEOUT_IN_MINUTES = 60


async def get_status(build_id: str):
    latest_event = await get_latest_build_event(build_id)
    if latest_event["status"] == BuildStatuses.QUEUED.value:
        last_update_time = parse(latest_event["time"])
        time_diff = date_util.get_time_diff_minutes(last_update_time, datetime.now())
        if time_diff > BUILD_TIMEOUT_IN_MINUTES:
            error_event = {
                "status": BuildStatuses.ERROR.value,
                "host": latest_event["host"],
                "status_detail": "build timed out in BMI API",
            }
            await add_build_event(build_id, error_event)
            latest_event = error_event
    return latest_event


async def add_build_event(build_id, event):
    build_time = datetime.now().isoformat()
    status_detail = event.get("status_detail", "null")
    host = event.get("host", "null")
    requestor = event.get("requestor", {})
    metadata = event.get("metadata", {})
    build_type = event.get("build_type", "null")
    event = BuildEvent(
        status=event.get("status", "null"),
        status_detail=status_detail,
        build_id=build_id,
        build_type=build_type,
        host=host,
        time=build_time,
        requestor=requestor,
        metadata=metadata,
    )
    await kafka_service.add_status_event(build_id, event)


async def get_latest_build_event(build_id: str):
    events = await kafka_service.get_build_events(build_id)
    if len(events) == 0:
        raise HTTPException(
            status_code=404, detail="Sorry, build_id not found in bmi api, please retry in few seconds!"
        )
    sorted_events = sorted(events, key=lambda event: event["time"], reverse=True)
    return sorted_events[0]


async def get_latest_build_event_host(host: str):
    events = await kafka_service.get_host_builds(host)
    if len(events) == 0:
        raise HTTPException(
            status_code=404, detail="Sorry, build_id not found in  bmi api, please retry in few seconds!"
        )
    sorted_events = sorted(events, key=lambda event: event["time"], reverse=True)
    return sorted_events[0]


async def get_build_events(build_id: str):
    return await kafka_service.get_build_events(build_id)


async def get_host_build_events(host: str):
    return await kafka_service.get_host_builds(host)


async def get_all_builds():
    return await kafka_service.get_all_builds()


### EVENTS


async def get_all_build_events():
    return await kafka_service.get_all_build_events()


async def get_my_build_events(username, day=0):
    events = await kafka_service.get_all_build_events()
    if len(events) == 0:
        raise HTTPException(status_code=404, detail="Sorry, No build found in bmi-service for today!")
    build_event = []
    for key, val in events.items():
        build_day = str(val[0]["time"])
        requestor = val[0].get("requestor", {})
        if bool(requestor) and len(requestor) != 0:
            requestor = requestor.get("requestor_id", "")
        if day == 0:
            today = date.today()
            if today.isoformat() in build_day and requestor == username:
                build_event.append(val)
        else:
            if requestor == username:
                build_event.append(val)
    today_list = []
    for builds in build_event:
        newlist = sorted(builds, key=lambda d: d["time"], reverse=True)
        today_list.append(newlist[0])
    if len(today_list) == 0:
        raise HTTPException(status_code=404, detail=f"No current builds found for user {username}!")
    sorted_events = sorted(today_list, key=lambda today_list: today_list["time"], reverse=True)
    return sorted_events


async def get_all_status_build_events(status):
    events = await kafka_service.get_all_build_events()
    processing_build = []
    for build_id in events.keys():
        latest_build = await get_latest_build_event(build_id)
        if latest_build["status"] == status:
            processing_build.append(latest_build)
    if not processing_build:
        raise HTTPException(status_code=404, detail=f"There is no build in status {status} at the moment")
    return sorted(processing_build, key=lambda d: d["time"], reverse=True)
