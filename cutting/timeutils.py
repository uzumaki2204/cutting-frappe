"""Use native Frappe site time in documents and UTC at the tablet boundary."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe


def site_zone():
    name = frappe.db.get_single_value("System Settings", "time_zone") or "Asia/Ho_Chi_Minh"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Ho_Chi_Minh")


def site_now():
    return datetime.now(site_zone()).replace(tzinfo=None)


def utc_to_site(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(site_zone()).replace(tzinfo=None)


def site_to_utc(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=site_zone()).astimezone(timezone.utc).isoformat()
