"""Datetime helper utilities."""
from datetime import datetime, timezone


def format_datetime_iso(dt: datetime) -> str:
    if dt is None:
        return None
    
    if dt.tzinfo is not None:
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
    else:
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'


def format_datetime_iso_optional(dt: datetime) -> str | None:
    if dt is None:
        return None
    return format_datetime_iso(dt)
