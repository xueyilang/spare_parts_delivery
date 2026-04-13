import logging
import requests

logger = logging.getLogger("trengo_feishu_service.feishu_client")

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
BITABLE_QUERY_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/query"


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    payload = {
        "app_id": app_id,
        "app_secret": app_secret,
    }

    try:
        response = requests.post(TOKEN_URL, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Feishu token request failed: %s", exc)
        raise RuntimeError("Unable to fetch Feishu tenant_access_token") from exc

    try:
        body = response.json()
    except ValueError as exc:
        logger.error("Invalid JSON in Feishu token response: %s", exc)
        raise RuntimeError("Invalid response from Feishu token endpoint") from exc

    if body.get("code") != 0 or not body.get("tenant_access_token"):
        message = body.get("msg") or "Unknown Feishu token error"
        logger.error("Feishu token response error: %s", message)
        raise RuntimeError("Feishu tenant_access_token request returned an error")

    return body["tenant_access_token"]


def search_record_by_cas(
    tenant_access_token: str,
    app_token: str,
    table_id: str,
    cas: str,
) -> dict | None:
    url = BITABLE_QUERY_URL.format(app_token=app_token, table_id=table_id)
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "filter": f'CAS = "{cas}"',
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Feishu record query failed: %s", exc)
        raise RuntimeError("Unable to query Feishu record") from exc

    try:
        body = response.json()
    except ValueError as exc:
        logger.error("Invalid JSON in Feishu query response: %s", exc)
        raise RuntimeError("Invalid response from Feishu record query") from exc

    if body.get("code") != 0:
        message = body.get("msg") or "Unknown Feishu query error"
        logger.error("Feishu query returned code %s: %s", body.get("code"), message)
        raise RuntimeError("Feishu record query returned an error")

    data = body.get("data") or {}
    items = data.get("items")
    if not items or not isinstance(items, list):
        return []

    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields")
        if isinstance(fields, dict):
            records.append(fields)

    return records
