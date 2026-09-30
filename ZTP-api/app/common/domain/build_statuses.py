from enum import Enum


class BuildStatuses(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"
    SUCCESS = "SUCCESS"
    UNCHANGED = "UNCHANGED"
    WARNING = "WARNING"
    PASS = "PASS"
