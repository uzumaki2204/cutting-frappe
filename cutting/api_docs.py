"""Publish the Cutting Summary contract in Factory Management's Desk Swagger catalog."""

import json

import frappe


SERVICE_TYPE = "API Documentation Service"
ENDPOINT_TYPE = "API Documentation Endpoint"
SERVICE_KEY = "cutting"
OPERATION_ID = "cuttingSummary"
SUMMARY_PATH = "/api/method/cutting.reporting.summary"
COLUMN_KEYS = (
    "serialNo", "sampleCode", "countrySampleCode", "countryCode",
    "colorCode", "planCode", "startOfWeek", "quantity",
)


def _object(properties):
    return {"type": "object", "required": list(properties), "properties": properties}


def _summary_schema():
    text = {"type": "string"}
    date_time = {"type": "string", "format": "date-time"}
    nullable_text = {"type": ["string", "null"]}
    metadata = _object({
        "occurredOnFrom": date_time, "occurredOnTo": date_time,
        "deviceQc": text, "deviceName": nullable_text, "companyCode": nullable_text,
        "generatedAtUtc": date_time, "sourceRowCount": {"type": "integer"},
        "groupedRowCount": {"type": "integer"},
    })
    grouped = _object({
        key: ({"type": "integer"} if key == "quantity" else date_time if key == "startOfWeek" else text)
        for key in COLUMN_KEYS
    })
    raw = _object({
        key: ({"type": "integer"} if key == "quantity" else date_time if key == "occurredOn" else text)
        for key in (
            "serialNo", "deviceName", "operatorId", "itemId", "occurredOn", "eventNo",
            "companyCode", "companyName", "factoryCode", "factoryName",
            "productionLineCode", "productionLineName", "sampleCode", "planCode",
            "countryCode", "colorCode", "quantity",
        )
    })
    report = _object({
        "metadata": metadata,
        "columns": {"type": "array", "items": _object({
            "key": {"type": "string", "enum": list(COLUMN_KEYS)}, "label": text,
        })},
        "rows": {"type": "array", "items": grouped},
        "rawRows": {"type": "array", "items": raw},
    })
    return _object({
        "success": {"type": "boolean"}, "code": nullable_text,
        "message": nullable_text,
        "data": {"anyOf": [report, {"type": "null"}]},
        "errors": {"type": "array", "items": text},
    })


def _parameters():
    date_schema = {"oneOf": [
        {"type": "string", "format": "date"},
        {"type": "string", "format": "date-time"},
    ]}
    parameters = [{
        "name": name, "in": "query", "required": True,
        "schema": date_schema, "description": "CUTTING_SUMMARY_DATE_DESCRIPTION",
    } for name in ("OccurredOnFrom", "OccurredOnTo")]
    parameters.extend({
        "name": name, "in": "query", "required": False,
        "schema": {"type": "string"},
        "description": "CUTTING_SUMMARY_FILTER_" + name.upper(),
    } for name in ("CompanyCode", "SampleCode", "EventNo", "DeviceName"))
    return parameters


def _responses():
    schema = _summary_schema()
    return {
        status: {
            "description": "CUTTING_SUMMARY_RESPONSE_" + status,
            "content": {"application/json": {"schema": schema}},
        }
        for status in ("200", "400", "403", "500")
    }


def ensure_catalog():
    """Seed missing Desk records once, preserving later edits made in the UI."""
    if not all(frappe.db.exists("DocType", name) for name in (SERVICE_TYPE, ENDPOINT_TYPE)):
        return
    service = frappe.db.get_value(SERVICE_TYPE, {"service_key": SERVICE_KEY}, "name")
    if not service:
        service = frappe.get_doc({
            "doctype": SERVICE_TYPE, "service_key": SERVICE_KEY,
            "service_title": "CUTTING_API_TITLE", "version": "1.0.0",
            "description": "CUTTING_API_DESCRIPTION", "is_active": 1,
        }).insert(ignore_permissions=True).name
    if frappe.db.exists(ENDPOINT_TYPE, {"operation_id": OPERATION_ID}):
        return
    frappe.get_doc({
        "doctype": ENDPOINT_TYPE, "service": service,
        "operation_id": OPERATION_ID, "path": SUMMARY_PATH, "http_method": "GET",
        "summary": "CUTTING_SUMMARY_TITLE",
        "description": "CUTTING_SUMMARY_DESCRIPTION",
        "tags_json": json.dumps(["Cutting Reports"]),
        "parameters_json": json.dumps(_parameters()),
        "responses_json": json.dumps(_responses()),
        "security_json": json.dumps([{"FrappeSession": []}, {"ApiToken": []}]),
        "allowed_roles": [{"role": "Cutting Report Reader"}, {"role": "System Manager"}],
        "is_active": 1,
    }).insert(ignore_permissions=True)
