from datetime import datetime


def get_time_diff_minutes(start: datetime, end: datetime):
    diff = end - start
    return divmod(diff.total_seconds(), 60)[0]
