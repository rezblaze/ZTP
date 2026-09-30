from enum import Enum


class BuildStatuses(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"
