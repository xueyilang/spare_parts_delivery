import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest

from feishu_client import get_tenant_access_token, search_record_by_cas

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("trengo_feishu_service")

FIELD_MAPPING = {
    "ticket_number": "客诉号 Ticket Number",
    "work_order": "工单号 Work Order",
    "sn_for_system_of_ticket": "客诉系统序列号 SN for System of Ticket",
    "item_name": "发货备件信息 Item Name",
    "quantity": "发货数量 Quantity",
    "sn_for_shipment": "实际拣货SN (SN for Shipment)",
    "tracking_number": "物流单号(发货) Tracking Number",
    "logistics_status": "物流状态 Logistics Status",
    "freight_forwarder": "货代（售后物流发货）Freight Forwarder",
}

app = Flask(__name__)


def get_env_variable(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def make_json_error(message: str, status_code: int):
    response = jsonify({"error": message})
    response.status_code = status_code
    return response


def authorize_request():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return make_json_error("Missing Authorization header", 401)

    if not auth_header.startswith("Bearer "):
        return make_json_error("Authorization header must be Bearer token", 401)

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return make_json_error("Authorization token is empty", 401)

    try:
        expected_secret = get_env_variable("TRANGO_SHARED_SECRET")
    except ValueError:
        logger.error("Missing TRANGO_SHARED_SECRET environment variable")
        return make_json_error("Server configuration error", 500)

    if token != expected_secret:
        return make_json_error("Invalid bearer token", 401)

    return None


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


@app.route("/lookup-cas", methods=["POST"])
def lookup_cas():
    logger.info("Received /lookup-cas request from %s", request.remote_addr)
    auth_error = authorize_request()
    if auth_error:
        return auth_error

    try:
        payload = request.get_json(force=True)
    except BadRequest:
        logger.error("Invalid JSON body for /lookup-cas request")
        return make_json_error("Invalid JSON body", 400)

    if not isinstance(payload, dict):
        logger.error("JSON body is not an object: %s", type(payload).__name__)
        return make_json_error("JSON body must be an object", 400)

    cas_value = payload.get("cas")
    if cas_value is None:
        return make_json_error("Missing required field: cas", 400)

    cas = str(cas_value).strip()
    if not cas:
        return make_json_error("Field cas must not be empty", 400)

    logger.info("Looking up CAS value: %s", cas)

    try:
        feishu_app_id = get_env_variable("FEISHU_APP_ID")
        feishu_app_secret = get_env_variable("FEISHU_APP_SECRET")
        feishu_app_token = get_env_variable("FEISHU_APP_TOKEN")
        feishu_table_id = get_env_variable("FEISHU_TABLE_ID")
        feishu_search_field_name = os.getenv(
            "FEISHU_SEARCH_FIELD_NAME",
            "客诉号 Ticket Number",
        )

        tenant_access_token = get_tenant_access_token(feishu_app_id, feishu_app_secret)
        record_fields = search_record_by_cas(
            tenant_access_token,
            feishu_app_token,
            feishu_table_id,
            feishu_search_field_name,
            cas,
        )
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return make_json_error("Server configuration error", 500)
    except RuntimeError as exc:
        logger.error("External service error: %s", exc)
        return make_json_error("External service unavailable", 500)
    except Exception:
        logger.exception("Unexpected error while processing CAS lookup")
        return make_json_error("Internal server error", 500)

    if not record_fields:
        logger.info("No matching record found for CAS: %s", cas)
        return jsonify(
            [
                {"key": "cas_found", "value": "no"},
                {"key": "cas", "value": cas},
            ]
        ), 200

    logger.info("Matched %d record(s) for CAS: %s", len(record_fields), cas)
    response_items = [
        {"key": "cas_found", "value": "yes"},
        {"key": "cas", "value": cas},
        {"key": "record_count", "value": str(len(record_fields))},
    ]

    records_data = []
    for record_fields_dict in record_fields:
        record_obj = {}
        for trengo_key, feishu_field_name in FIELD_MAPPING.items():
            raw_value = record_fields_dict.get(feishu_field_name, "")
            if raw_value is None:
                raw_value = ""
            elif isinstance(raw_value, bool):
                raw_value = "true" if raw_value else "false"
            elif not isinstance(raw_value, str):
                raw_value = str(raw_value)
            record_obj[trengo_key] = raw_value
        records_data.append(record_obj)

    response_items.append({"key": "records", "value": records_data})

    return jsonify(response_items), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
