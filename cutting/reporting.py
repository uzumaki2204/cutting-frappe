"""Bounded Cutting detail/workbook reports and Desk creation summaries."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

import frappe

from cutting.access import require_viewer
from cutting.api import _data, _fail, _zone
from cutting.i18n import message


def date_range(from_date, to_date, maximum):
    if not from_date or not to_date:
        _fail("error.range_required")
    try:
        start = date.fromisoformat(str(from_date)[:10])
        end = date.fromisoformat(str(to_date)[:10])
    except ValueError:
        _fail("error.input")
    if start > end:
        start, end = end, start
    if (end - start).days + 1 > maximum:
        _fail("error.range_too_long", days=maximum)
    return start, end


def _where(filters, *, trash=0):
    if not isinstance(filters, dict):
        _fail("error.input")
    conditions = ["r.is_deleted = %(trash)s"]
    if str(trash or 0) not in ("0", "1"):
        _fail("error.input")
    params = {"trash": int(trash or 0)}
    columns = {
        "company": "r.company", "device": "r.device", "product": "r.product",
        "color": "r.color", "market": "r.market",
        "product_code_identifier": "r.product_code_identifier",
        "company_code": "c.company_code", "sample_code": "p.product_code",
        "device_name": "d.device_name", "event_no": "r.local_event_id",
    }
    for key, column in columns.items():
        if filters.get(key):
            conditions.append(f"{column} = %({key})s")
            params[key] = str(filters[key]).strip()
    return conditions, params


JOINS = """
    FROM `tabCutting Record` r
    LEFT JOIN `tabProduct` p ON p.name = r.product
    LEFT JOIN `tabColor` col ON col.name = r.color
    LEFT JOIN `tabMarket` m ON m.name = r.market
    LEFT JOIN `tabFactory Device` d ON d.name = r.device
    LEFT JOIN `tabCompany` c ON c.name = r.company
    LEFT JOIN `tabFactory` f ON f.name = d.factory
    LEFT JOIN `tabProduction Line` l ON l.name = d.line
"""


def _report_rows(from_date, to_date, maximum, filters):
    start, end = date_range(from_date, to_date, maximum)
    conditions, params = _where(filters)
    zone = _zone()
    params["start"] = datetime.combine(start, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    params["end"] = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    conditions += ["r.occurred_at >= %(start)s", "r.occurred_at < %(end)s"]
    rows = frappe.db.sql(
        """SELECT r.name, r.product, r.color, r.market, r.device, r.device_uid,
            r.product_code_identifier, r.quantity, r.occurred_at, r.creation,
            r.local_event_id, r.owner, r.source,
            COALESCE(p.product_code, '') AS product_code,
            COALESCE(p.product_name, '') AS product_name,
            COALESCE(col.color_code, '') AS color_code,
            COALESCE(col.color_name, '') AS color_name,
            COALESCE(m.code, '') AS market_code,
            COALESCE(m.name_en, '') AS market_name,
            COALESCE(d.device_name, '') AS device_name,
            COALESCE(c.company_code, '') AS company_code,
            COALESCE(c.company_name, '') AS company_name,
            COALESCE(f.factory_code, '') AS factory_code,
            COALESCE(f.factory_name, '') AS factory_name,
            COALESCE(l.line_code, '') AS line_code,
            COALESCE(l.line_name, '') AS line_name
        """ + JOINS + " WHERE " + " AND ".join(conditions) + " ORDER BY r.occurred_at, r.name",
        params, as_dict=True,
    )
    return start, end, rows


@frappe.whitelist(methods=["GET"])
def report_detail(from_date: str | None = None, to_date: str | None = None, filters: dict | str | None = None):
    require_viewer()
    _, _, rows = _report_rows(from_date, to_date, 7, _data(filters, {}))
    return rows


@frappe.whitelist(methods=["GET"])
def report_summary(from_date: str | None = None, to_date: str | None = None, filters: dict | str | None = None):
    require_viewer()
    selected = _data(filters, {})
    start, end, source = _report_rows(from_date, to_date, 31, selected)
    raw = []
    grouped = defaultdict(int)
    for row in source:
        occurred = row.occurred_at
        if isinstance(occurred, str):
            occurred = datetime.fromisoformat(occurred)
        local_day = occurred.replace(tzinfo=timezone.utc).astimezone(_zone()).date()
        monday = local_day - timedelta(days=local_day.weekday())
        key = (row.device_name, row.product_code, row.market_code, row.color_code, row.product_code_identifier, monday.isoformat())
        grouped[key] += row.quantity
        raw.append({
            "serialNo": row.device_name, "deviceName": row.device_name,
            "operatorId": row.owner, "itemId": ".".join((row.product_code, row.product_code_identifier, row.market_code, row.color_code)),
            "occurredOn": row.occurred_at, "eventNo": row.local_event_id or "",
            "companyCode": row.company_code, "companyName": row.company_name,
            "factoryCode": row.factory_code, "factoryName": row.factory_name,
            "productionLineCode": row.line_code, "productionLineName": row.line_name,
            "sampleCode": row.product_code, "planCode": row.product_code_identifier,
            "countryCode": row.market_code, "colorCode": row.color_code, "quantity": row.quantity,
        })
    rows = [{
        "serialNo": key[0], "sampleCode": key[1], "countrySampleCode": key[2] + key[1],
        "countryCode": key[2], "colorCode": key[3], "planCode": key[4],
        "startOfWeek": key[5], "quantity": quantity,
    } for key, quantity in sorted(grouped.items(), key=lambda item: item[0][1:])]
    columns = [("serialNo", "ui.device"), ("sampleCode", "ui.product"), ("countryCode", "ui.market"), ("colorCode", "ui.color"), ("planCode", "ui.plan"), ("startOfWeek", "ui.date"), ("quantity", "ui.quantity")]
    return {
        "metadata": {"occurredOnFrom": start.isoformat(), "occurredOnTo": end.isoformat(),
                     "deviceQc": "Cutting", "deviceName": selected.get("device_name"),
                     "companyCode": selected.get("company_code"),
                     "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
                     "sourceRowCount": len(raw), "groupedRowCount": len(rows)},
        "columns": [{"key": key, "label": message(label)} for key, label in columns],
        "rows": rows, "rawRows": raw,
    }


@frappe.whitelist(methods=["GET"])
def admin_summary(created_from: str | None = None, created_to: str | None = None, filters: dict | str | None = None, trash: int = 0):
    require_viewer()
    conditions, params = _where(_data(filters, {}), trash=trash)
    if created_from:
        try:
            params["created_from"] = date.fromisoformat(str(created_from)[:10])
        except ValueError:
            _fail("error.input")
        conditions.append("r.creation >= %(created_from)s")
    if created_to:
        try:
            params["created_to"] = date.fromisoformat(str(created_to)[:10]) + timedelta(days=1)
        except ValueError:
            _fail("error.input")
        conditions.append("r.creation < %(created_to)s")
    where = " WHERE " + " AND ".join(conditions)
    total = frappe.db.sql("SELECT COUNT(*) AS count, COALESCE(SUM(r.quantity),0) AS quantity " + JOINS + where, params, as_dict=True)[0]
    result = {"totalRecords": total.count, "totalQuantity": total.quantity}
    dimensions = {
        "byCreatedDate": ("DATE(r.creation)", "DATE(r.creation)"),
        "byProduct": ("r.product", "p.product_code"),
        "byColor": ("r.color", "col.color_code"),
        "byMarket": ("r.market", "m.code"),
    }
    for key, (column, label) in dimensions.items():
        result[key] = frappe.db.sql(
            f"SELECT {column} AS id, {label} AS label, COUNT(*) AS count, SUM(r.quantity) AS quantity "
            + JOINS + where + f" GROUP BY {column}, {label} ORDER BY {label}", params, as_dict=True,
        )
    return result
