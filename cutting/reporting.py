"""Bounded Cutting detail/workbook reports and Desk creation summaries."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import frappe

from cutting.access import has_role, require_viewer
from cutting.api import _data, _fail
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
    LEFT JOIN `tabProduct Color` col ON col.name = r.color
    LEFT JOIN `tabMarket` m ON m.name = r.market
    LEFT JOIN `tabFactory Device` d ON d.name = r.device
    LEFT JOIN `tabCompany` c ON c.name = r.company
    LEFT JOIN `tabFactory` f ON f.name = d.factory
    LEFT JOIN `tabProduction Line` l ON l.name = d.line
"""


def _dotnet_where(filters):
    conditions, params = _where({})
    columns = {
        "company_code": "c.company_code",
        "sample_code": "p.product_code",
        "event_no": "r.local_event_id",
    }
    for key, column in columns.items():
        if filters.get(key):
            conditions.append(f"LOWER({column}) = %({key})s")
            params[key] = filters[key].strip().lower()
    if filters.get("device_name"):
        conditions.append("LOCATE(%(device_name)s, LOWER(d.device_name)) > 0")
        params["device_name"] = filters["device_name"].strip().lower()
    return conditions, params


def _report_rows(from_date, to_date, maximum, filters, *, dotnet=False):
    start, end = date_range(from_date, to_date, maximum)
    conditions, params = _dotnet_where(filters) if dotnet else _where(filters)
    params["start"] = datetime.combine(start, time.min)
    conditions.append("r.occurred_at >= %(start)s")
    if end == date.max:
        params["end"] = datetime.max
        conditions.append("r.occurred_at <= %(end)s")
    else:
        params["end"] = datetime.combine(end + timedelta(days=1), time.min)
        conditions.append("r.occurred_at < %(end)s")
    rows = frappe.db.sql(
        f"""SELECT r.name, r.product, r.color, r.market, r.device, r.device_uid,
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


def _trim_key(plan, sample, color):
    return tuple(str(value or "").strip().casefold() for value in (plan, sample, color))


def _trim_order_quantities(keys):
    if not frappe.db.table_exists("Trim", cached=False) or not frappe.db.table_exists("Trim Item", cached=False):
        return None
    unique = {}
    for key in keys:
        values = tuple(str(value or "").strip() for value in key)
        if all(values):
            unique.setdefault(_trim_key(*values), values)
    keys = list(unique.values())
    totals = {}
    for offset in range(0, len(keys), 200):
        batch = keys[offset:offset + 200]
        placeholders = ", ".join(["(%s, %s, %s)"] * len(batch))
        values = [value for key in batch for value in key]
        rows = frappe.db.sql(
            """SELECT i.order_plan_number, i.sample_code, i.color_code,
                      SUM(i.order_qty) AS total
                 FROM `tabTrim Item` i
                 INNER JOIN `tabTrim` t ON t.name = i.parent
                 WHERE i.parenttype = 'Trim'
                   AND COALESCE(t.document_status, '') != %s
                   AND (i.order_plan_number, i.sample_code, i.color_code) IN ("""
            + placeholders + ") GROUP BY i.order_plan_number, i.sample_code, i.color_code",
            ["Cancel", *values], as_dict=True,
        )
        for row in rows:
            key = _trim_key(row.order_plan_number, row.sample_code, row.color_code)
            totals[key] = int(row.total or 0)
    return totals


def _cutting_rates(products):
    products = sorted(set(products))
    rates = {}
    for offset in range(0, len(products), 200):
        batch = products[offset:offset + 200]
        for row in frappe.get_all(
            "Cutting Standard", filters={"product": ["in", batch]},
            fields=["product", "rate_m_per_piece"], limit=len(batch),
        ):
            rates[row.product] = Decimal(str(row.rate_m_per_piece))
    return rates


@frappe.whitelist(methods=["GET"])
def report_detail(from_date: str | None = None, to_date: str | None = None, filters: dict | str | None = None):
    require_viewer()
    _, _, rows = _report_rows(from_date, to_date, 7, _data(filters, {}))
    totals = _trim_order_quantities((row.product_code_identifier, row.market_code + row.product_code,
                                    row.color_code) for row in rows)
    for row in rows:
        key = _trim_key(row.product_code_identifier, row.market_code + row.product_code, row.color_code)
        row["sum_order_qty"] = totals.get(key, 0) if totals is not None else None
    return rows


@frappe.whitelist(methods=["GET"])
def report_summary(from_date: str | None = None, to_date: str | None = None, filters: dict | str | None = None):
    require_viewer()
    selected = _data(filters, {})
    start, end, source = _report_rows(from_date, to_date, 31, selected)
    report = _summary_payload(start, end, source, selected, group_by_product=True)
    totals = _trim_order_quantities((row["planCode"], row["countrySampleCode"], row["colorCode"])
                                    for row in report["rows"])
    rates = _cutting_rates(row["_product"] for row in report["rows"])
    for row in report["rows"]:
        key = _trim_key(row["planCode"], row["countrySampleCode"], row["colorCode"])
        row["sumOrderQty"] = totals.get(key, 0) if totals is not None else None
        rate = rates.get(row.pop("_product"))
        row["cuttingQtyM"] = (float(Decimal(row["quantity"]) * rate)
                              if rate is not None else None)
    report["columns"].append({"key": "sumOrderQty", "label": message("ui.sum_order_qty")})
    report["columns"].append({"key": "cuttingQtyM", "label": message("ui.cutting_qty_m")})
    return report


def _summary_payload(start, end, source, selected, *, group_by_product=False):
    raw = []
    grouped = defaultdict(int)
    for row in source:
        occurred = row.occurred_at
        if isinstance(occurred, str):
            occurred = datetime.fromisoformat(occurred)
        local_day = occurred.date()
        monday = local_day - timedelta(days=local_day.weekday())
        key = (row.device_name, row.product_code, row.market_code, row.color_code,
               row.product_code_identifier, monday.isoformat(),
               row.product if group_by_product else "")
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
        **({"_product": key[6]} if group_by_product else {}),
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


def _summary_response(data=None, error_key=None, status=200, **values):
    description = message(error_key, **values) if error_key else None
    frappe.local.response["http_status_code"] = status
    return {
        "success": error_key is None,
        "code": None,
        "message": description,
        "data": data,
        "errors": [description] if description else [],
    }


def _summary_date(value):
    return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()


def _display_filter(value):
    if value is None:
        return None
    return str(value).strip() or None


@frappe.whitelist(allow_guest=True, methods=["GET"])
def summary(OccurredOnFrom=None, OccurredOnTo=None, CompanyCode=None, SampleCode=None,
            EventNo=None, DeviceName=None):
    """Expose the .NET Cutting Summary contract from Frappe Cutting records."""
    if not has_role("Cutting Report Reader"):
        return _summary_response(error_key="error.permission", status=403)
    if not OccurredOnFrom or not OccurredOnTo:
        return _summary_response(error_key="report.summary_range_required", status=400)
    try:
        start = _summary_date(OccurredOnFrom)
        end = _summary_date(OccurredOnTo)
    except (TypeError, ValueError):
        return _summary_response(error_key="error.input", status=400)
    if start > end:
        start, end = end, start
    if (end - start).days >= 31:
        return _summary_response(error_key="report.summary_range_too_long", status=400, days=31)

    selected = {
        "company_code": _display_filter(CompanyCode),
        "sample_code": _display_filter(SampleCode),
        "event_no": _display_filter(EventNo),
        "device_name": _display_filter(DeviceName),
    }
    try:
        _, _, source = _report_rows(start.isoformat(), end.isoformat(), 31, selected, dotnet=True)
        report = _summary_payload(start, end, source, selected)
    except Exception:
        try:
            frappe.log_error(frappe.get_traceback(), title=message("error.report_unavailable"))
        except Exception:
            pass
        return _summary_response(error_key="error.report_unavailable", status=500)

    report["metadata"].update({
        "occurredOnFrom": start.isoformat() + "T00:00:00",
        "occurredOnTo": end.isoformat() + "T00:00:00",
        "deviceQc": "CUTTING",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    report["columns"] = [
        {"key": key, "label": message("report.summary_column_" + key)}
        for key in ("serialNo", "sampleCode", "countrySampleCode", "countryCode",
                    "colorCode", "planCode", "startOfWeek", "quantity")
    ]
    report["rows"].sort(key=lambda row: (
        row["sampleCode"], row["countryCode"], row["colorCode"], row["planCode"],
        row["serialNo"], row["startOfWeek"],
    ))
    for row in report["rows"]:
        row["startOfWeek"] += "T00:00:00"
    for row in report["rawRows"]:
        occurred = row["occurredOn"]
        row["occurredOn"] = (occurred if isinstance(occurred, datetime)
                             else datetime.fromisoformat(str(occurred))).isoformat()
    return _summary_response(data=report)


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
