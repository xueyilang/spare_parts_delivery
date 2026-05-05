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
    "tracking_number": "物流单号(发货) Tracking Number",
    "logistics_status": "物流状态 Logistics Status",
    "freight_forwarder": "货代（售后物流发货）Freight Forwarder",
}

STATUS_MAP = {
    "Shipped": "Shipped",
    "已发货": "Shipped",
    "Shipment cancelled": "Shipment cancelled",
    "已取消": "Shipment cancelled",
    "Not processed": "Not processed",
    "未处理": "Not processed",
}

FORWARDER_MAP = {
    "安装商或客户自提": "Self pick-up",
}


def _extract_before_chinese(text: str) -> str:
    for i, ch in enumerate(text):
        if '一' <= ch <= '鿿':
            result = text[:i]
            while result and not (result[-1].isalnum() or result[-1].isspace()):
                result = result[:-1]
            return result.strip()
    return text


def _looks_like_tracking(value: str) -> bool:
    return bool(value) and any(ch.isdigit() for ch in value)


def clean_tracking(value: str) -> str:
    if not value or not value.strip():
        return ""
    if value.startswith("NTS物流"):
        return ""
    if "selbstabholung" in value.lower():
        return ""
    if value.startswith("LHZ-DPD"):
        return ""
    if any("一" <= ch <= "鿿" for ch in value):
        extracted = _extract_before_chinese(value)
        if _looks_like_tracking(extracted):
            return extracted.strip()
        return ""
    return value.strip()


def clean_status(value: str) -> str:
    if not value or not value.strip():
        return "Unknown"
    value = value.strip()
    parts = value.split(" ", 1)
    if len(parts) > 1 and any("一" <= c <= "鿿" for c in parts[0]):
        english_part = parts[1].strip()
    else:
        english_part = value
    return STATUS_MAP.get(english_part, english_part)


def clean_forwarder(value: str) -> str:
    if not value or not value.strip():
        return "Unknown"
    return FORWARDER_MAP.get(value.strip(), value.strip())

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


def map_record_fields(record_fields: dict) -> dict:
    mapped = {}
    for output_key, feishu_field_name in FIELD_MAPPING.items():
        mapped[output_key] = record_fields.get(feishu_field_name, "")
    return mapped


def build_logistics_message(cas: str, record: dict | None) -> str:
    if record is None:
        return f"No logistics record found for CAS {cas}."

    status = record.get("logistics_status", "")
    tracking = record.get("tracking_number", "")
    forwarder = record.get("freight_forwarder", "")

    if status != "Shipped":
        return f"Status: {status}."

    if tracking:
        return f"Tracking number: {tracking}, Status: {status}, Forwarder: {forwarder}."

    return f"Tracking number: not available, Status: {status}, Forwarder: {forwarder}."


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

    if record_fields:
        best = record_fields[0]
        for rec in record_fields:
            raw_trk = rec.get("物流单号(发货) Tracking Number", "")
            if raw_trk and not raw_trk.startswith("NTS物流"):
                best = rec
                break
        raw = map_record_fields(best)
        record = {
            "tracking_number": clean_tracking(raw.get("tracking_number", "")),
            "logistics_status": clean_status(raw.get("logistics_status", "")),
            "freight_forwarder": clean_forwarder(raw.get("freight_forwarder", "")),
        }
    else:
        record = None

    ai_message = build_logistics_message(cas, record)

    logger.info("Returning ai_message for CAS %s", cas)
    return jsonify({"ai_message": ai_message}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
