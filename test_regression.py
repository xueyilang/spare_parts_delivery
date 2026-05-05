"""Final comprehensive regression + edge case test suite."""
import os, json, sys
from collections import defaultdict, Counter
import requests
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FLASK_RUN_HOST", "127.0.0.1")

from app import (
    app, clean_tracking, clean_status, clean_forwarder,
    build_logistics_message,
    FIELD_MAPPING, STATUS_MAP, FORWARDER_MAP,
)
from feishu_client import normalize_field_value, get_tenant_access_token, search_record_by_cas

PASS = 0
FAIL = 0

def t(name, result, detail=""):
    global PASS, FAIL
    if result:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")

def has_cn(s):
    return any("一" <= c <= "鿿" for c in s)


# ═══════════════════════════════════════════════
# SECTION 1: clean_tracking
# ═══════════════════════════════════════════════
print("=" * 60)
print("1. clean_tracking")
print("=" * 60)

# Normal cases
t("normal GLS number", clean_tracking("60104324929") == "60104324929")
t("normal Cargoboard number", clean_tracking("11665490") == "11665490")
t("LHZ-DPD identifier", clean_tracking("LHZ-DPD") == "")
t("Selbstabholung", clean_tracking("Selbstabholung") == "")

# NTS placeholders (Regression: Bug fix - startswith NTS物流)
t("NTS物流 → empty", clean_tracking("NTS物流") == "")
t("NTS物流-DHL → empty", clean_tracking("NTS物流-DHL") == "")
t("NTS物流 statt11677714 → empty", clean_tracking("NTS物流 statt11677714") == "")

# Chinese-annotated tracking (Regression: extract before CN)
t("601043494079快递改为邮政... → 601043494079, 601051439079",
  clean_tracking("601043494079快递改为邮政601051439079") == "601043494079, 601051439079")
t("60104695999(偏远地址)... → 60104695999, 60853113806",
  clean_tracking("60104695999(偏远地址),60853113806(express)") == "60104695999, 60853113806")
t("60853113898,带电池发海运 → 60853113898",
  clean_tracking("60853113898,带电池发海运") == "60853113898")

# Whitespace handling (Regression: Bug fix - strip)
t("leading space stripped", clean_tracking(" 60104349372") == "60104349372")
t("trailing space stripped", clean_tracking("60104349372 ") == "60104349372")
t("whitespace-only → empty", clean_tracking("   ") == "")
t("empty string → empty", clean_tracking("") == "")
t("tab+newline → empty", clean_tracking("\t\n") == "")
t("NTS物流 with trailing space → empty", clean_tracking("NTS物流 ") == "")
t("leading space NTS物流 → empty", clean_tracking(" NTS物流") == "")

# No-CN tracking with special chars
t("slash in tracking", clean_tracking("60853062530/60853062600") == "60853062530, 60853062600")
t("alpha+digits mixed → keep only digits", clean_tracking("ZHO7CPGE,60104674014") == "60104674014")
t("Selbstabholung → empty", clean_tracking("Selbstabholung") == "")
t("Selbstabholung variant → empty", clean_tracking("Selbstabholung - UK,40257145950397840382") == "")
t("LHZ-DPD → empty", clean_tracking("LHZ-DPD") == "")
t("LHZ-DPD-Other → empty", clean_tracking("LHZ-DPD-Other") == "")
t("LHZ-DPD-Other(Hofheim) → empty", clean_tracking("LHZ-DPD-Other(LHZ-Hofheim)") == "")
t("multi-tracking CAS-152629", clean_tracking("60105718349,改单60105859391") == "60105718349, 60105859391")
t("DPD format preserved", clean_tracking("01606817 0146 66") == "01606817 0146 66")

# ═══════════════════════════════════════════════
# SECTION 2: clean_status
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. clean_status")
print("=" * 60)

# Normal bilingual format
t("已发货 Shipped → Shipped", clean_status("已发货 Shipped") == "Shipped")
t("已取消 Shipment cancelled → Shipment cancelled",
  clean_status("已取消 Shipment cancelled") == "Shipment cancelled")
t("未处理 Not processed → Not processed",
  clean_status("未处理 Not processed") == "Not processed")

# English-only
t("Shipped → Shipped", clean_status("Shipped") == "Shipped")
t("In Transit → In Transit", clean_status("In Transit") == "In Transit")

# Chinese-only (defense in depth: mapped in STATUS_MAP)
t("已发货 only → Shipped", clean_status("已发货") == "Shipped")
t("已取消 only → Shipment cancelled", clean_status("已取消") == "Shipment cancelled")
t("未处理 only → Not processed", clean_status("未处理") == "Not processed")

# Whitespace (Regression: Bug fix - strip before processing)
t("whitespace-only → Unknown", clean_status("   ") == "Unknown")
t("empty string → Unknown", clean_status("") == "Unknown")
t("trailing space → Shipped", clean_status("Shipped ") == "Shipped")
t("leading space bilingual → Shipped", clean_status(" 已发货 Shipped") == "Shipped")

# Unexpected statuses
t("unknown status passed through", clean_status("Delivered") == "Delivered")
t("multi-word unknown", clean_status("Partially Shipped") == "Partially Shipped")

# ═══════════════════════════════════════════════
# SECTION 3: clean_forwarder
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. clean_forwarder")
print("=" * 60)

# Known forwarders
t("GLS → GLS", clean_forwarder("GLS") == "GLS")
t("Cargoboard → Cargoboard", clean_forwarder("Cargoboard") == "Cargoboard")
t("NTS-Logistik Partner → NTS-Logistik Partner",
  clean_forwarder("NTS-Logistik Partner") == "NTS-Logistik Partner")
t("LHZ-DPD → LHZ-DPD", clean_forwarder("LHZ-DPD") == "LHZ-DPD")
t("DPD → DPD", clean_forwarder("DPD") == "DPD")

# Chinese forwarder (Regression: 安装商或客户自提 key fix)
t("安装商或客户自提 → Self pick-up",
  clean_forwarder("安装商或客户自提") == "Self pick-up")

# Whitespace (Regression: strip fix)
t("leading space → GLS", clean_forwarder(" GLS") == "GLS")
t("trailing space → GLS", clean_forwarder("GLS ") == "GLS")
t("both spaces → GLS", clean_forwarder(" GLS ") == "GLS")
t("empty → Unknown", clean_forwarder("") == "Unknown")
t("whitespace-only → Unknown", clean_forwarder("   ") == "Unknown")

# Unknown forwarder
t("unknown passed through", clean_forwarder("FedEx") == "FedEx")

# ═══════════════════════════════════════════════
# SECTION 4: build_logistics_message
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. build_logistics_message")
print("=" * 60)

def check_msg(name, cas, record, expects, not_expects=None):
    msg = build_logistics_message(cas, record)
    ok = True
    errors = []
    if has_cn(msg):
        ok = False
        errors.append("HAS_CHINESE")
    for e in expects:
        if e not in msg:
            ok = False
            errors.append(f"missing '{e}'")
    if not_expects:
        for ne in not_expects:
            if ne in msg:
                ok = False
                errors.append(f"has '{ne}'")
    t(name, ok, f"→ {msg}" if not ok else "")
    if ok:
        print(f"       {msg}")

# Not found
check_msg("not found", "CAS-999", None, ["No logistics record found", "CAS-999"], ["Tracking", "Status", "Forwarder"])

# Non-shipped: only status
check_msg("cancelled", "CAS-1", {"tracking_number": "", "logistics_status": "Shipment cancelled", "freight_forwarder": ""},
          ["Status: Shipment cancelled"], ["Tracking number", "Forwarder"])
check_msg("not processed", "CAS-2", {"tracking_number": "", "logistics_status": "Not processed", "freight_forwarder": ""},
          ["Status: Not processed"], ["Tracking number", "Forwarder"])

# Shipped + valid tracking
check_msg("shipped+GLS", "CAS-3", {"tracking_number": "60104324929", "logistics_status": "Shipped", "freight_forwarder": "GLS"},
          ["Tracking number: 60104324929", "Status: Shipped", "Forwarder: GLS"])
check_msg("shipped+Cargoboard", "CAS-4", {"tracking_number": "11665490", "logistics_status": "Shipped", "freight_forwarder": "Cargoboard"},
          ["Tracking number: 11665490", "Status: Shipped", "Forwarder: Cargoboard"])

# Shipped + no tracking (NTS case)
check_msg("shipped+NTS", "CAS-5", {"tracking_number": "", "logistics_status": "Shipped", "freight_forwarder": "NTS-Logistik Partner"},
          ["Tracking number: not available", "Status: Shipped", "Forwarder: NTS-Logistik Partner"])

# Shipped + self pick-up (tracking = Selbstabholung → cleaned to empty)
check_msg("shipped+selfpickup", "CAS-6", {"tracking_number": "", "logistics_status": "Shipped", "freight_forwarder": "Self pick-up"},
          ["Tracking number: not available", "Status: Shipped", "Forwarder: Self pick-up"])

# Edge: unknown status (not in STATUS_MAP)
check_msg("unknown status", "CAS-7", {"tracking_number": "12345", "logistics_status": "Delivered", "freight_forwarder": "FedEx"},
          ["Status: Delivered"], ["Tracking number", "Forwarder"])

# ═══════════════════════════════════════════════
# SECTION 5: Flask endpoint integration
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. Flask endpoint integration")
print("=" * 60)

secret = os.getenv("TRANGO_SHARED_SECRET")

with app.test_client() as client:
    # Health check
    r = client.get("/")
    t("GET / → 200", r.status_code == 200 and r.json["status"] == "ok")

    # Auth failures
    r = client.post("/lookup-cas", json={"cas": "CAS-123"})
    t("missing auth → 401", r.status_code == 401)

    r = client.post("/lookup-cas", json={"cas": "CAS-123"},
                    headers={"Authorization": "Bearer wrong"})
    t("wrong auth → 401", r.status_code == 401)

    # Input validation
    r = client.post("/lookup-cas", json={},
                    headers={"Authorization": f"Bearer {secret}"})
    t("missing cas field → 400", r.status_code == 400)

    r = client.post("/lookup-cas", json={"cas": "  "},
                    headers={"Authorization": f"Bearer {secret}"})
    t("empty cas → 400", r.status_code == 400)

    r = client.post("/lookup-cas", data="not json",
                    headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"})
    t("invalid JSON → 400", r.status_code == 400)

    # Real CAS lookups
    # Normal Shipped + GLS
    r = client.post("/lookup-cas", json={"cas": "CAS-145296"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("CAS-145296 (Shipped+GLS): no CN", not has_cn(msg), f"msg={msg}")
    t("CAS-145296 (Shipped+GLS): has tracking", "Tracking number:" in msg, f"msg={msg}")

    # Not found
    r = client.post("/lookup-cas", json={"cas": "CAS-00000000"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("non-existent CAS: not found message", "No logistics record found" in msg)

    # Cancelled (Regression: should NOT show tracking/forwarder)
    r = client.post("/lookup-cas", json={"cas": "CAS-144236"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("cancelled CAS: no CN", not has_cn(msg), f"msg={msg}")
    t("cancelled CAS: status only", "Status:" in msg and "Tracking number:" not in msg and "Forwarder:" not in msg, f"msg={msg}")

    # Not processed
    r = client.post("/lookup-cas", json={"cas": "CAS-147094"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("not processed CAS: no CN", not has_cn(msg), f"msg={msg}")
    t("not processed CAS: status only", "Status:" in msg and "Tracking number:" not in msg, f"msg={msg}")

    # Bug regression: CAS-136194 (mixed NTS + Cargoboard) → should pick Cargoboard
    r = client.post("/lookup-cas", json={"cas": "CAS-136194"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("CAS-136194 regression: not 'not available'", "not available" not in msg, f"msg={msg}")
    t("CAS-136194 regression: has Cargoboard tracking", "Tracking number: 11677043" in msg, f"msg={msg}")

    # Bug regression: NTS CAS → should still work (no valid alternative, just placeholder)
    r = client.post("/lookup-cas", json={"cas": "CAS-145263"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("CAS-145263 (NTS only): not available", "not available" in msg, f"msg={msg}")
    t("CAS-145263 (NTS only): has NTS forwarder", "NTS-Logistik Partner" in msg, f"msg={msg}")

    # Self pick-up regression (Selbstabholung → not available)
    r = client.post("/lookup-cas", json={"cas": "CAS-147422"},
                    headers={"Authorization": f"Bearer {secret}"})
    msg = r.json.get("ai_message", "")
    t("CAS-147422 (self pick-up): no CN", not has_cn(msg), f"msg={msg}")
    t("CAS-147422 (self pick-up): Self pick-up", "Self pick-up" in msg, f"msg={msg}")
    t("CAS-147422 (self pick-up): not available", "not available" in msg, f"msg={msg}")

# ═══════════════════════════════════════════════
# SECTION 6: All 500 records pipeline test
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("6. Full pipeline on 500 records")
print("=" * 60)

r = requests.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
    json={"app_id": os.getenv("FEISHU_APP_ID"), "app_secret": os.getenv("FEISHU_APP_SECRET")},
    timeout=10,
)
token = r.json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
APP_TOKEN = os.getenv("FEISHU_APP_TOKEN")
TABLE_ID = os.getenv("FEISHU_TABLE_ID")
search_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/search"

r = requests.post(search_url, json={"page_size": 500}, headers=h, timeout=30)
items = r.json()["data"]["items"]

cn_msgs = 0
cn_tracking = 0
cn_status = 0
cn_forwarder = 0
unexpected_statuses = Counter()
unexpected_forwarders = Counter()
invalid_trackings = []

for item in items:
    f = item["fields"]
    raw_trk = normalize_field_value(f.get("物流单号(发货) Tracking Number"))
    raw_sts = normalize_field_value(f.get("物流状态 Logistics Status"))
    raw_fwd = normalize_field_value(f.get("货代（售后物流发货）Freight Forwarder"))
    cas = normalize_field_value(f.get("客诉号 Ticket Number"))

    trk = clean_tracking(raw_trk)
    sts = clean_status(raw_sts)
    fwd = clean_forwarder(raw_fwd)

    if has_cn(trk): cn_tracking += 1
    if has_cn(sts): cn_status += 1
    if has_cn(fwd): cn_forwarder += 1

    if sts not in STATUS_MAP and sts not in ("Unknown",):
        unexpected_statuses[sts] += 1
    if fwd not in ("GLS", "Cargoboard", "NTS-Logistik Partner", "LHZ-DPD", "DPD", "Self pick-up", "Unknown"):
        unexpected_forwarders[fwd] += 1

    # Check for obviously invalid cleaned tracking
    if trk and not any(c.isdigit() for c in trk):
        invalid_trackings.append((cas, trk[:60]))

    msg = build_logistics_message(cas, {"tracking_number": trk, "logistics_status": sts, "freight_forwarder": fwd})
    if has_cn(msg):
        cn_msgs += 1
        if cn_msgs <= 3:
            print(f"  CN in msg: {msg}")

t("0 messages with Chinese", cn_msgs == 0, f"{cn_msgs} failed")
t("0 cleaned tracking with Chinese", cn_tracking == 0, f"{cn_tracking} failed")
t("0 cleaned status with Chinese", cn_status == 0, f"{cn_status} failed")
t("0 cleaned forwarder with Chinese", cn_forwarder == 0, f"{cn_forwarder} failed")

if unexpected_statuses:
    print(f"  INFO: unexpected status values: {dict(unexpected_statuses)}")
else:
    t("all statuses known", True)

if unexpected_forwarders:
    print(f"  INFO: unexpected forwarder values: {dict(unexpected_forwarders)}")
else:
    t("all forwarders known", True)

if invalid_trackings:
    print(f"  WARN: {len(invalid_trackings)} tracking numbers without digits:")
    for cas, trk in invalid_trackings[:5]:
        print(f"    {cas}: {trk}")
else:
    t("all tracking numbers seem valid", True)

# ═══════════════════════════════════════════════
# SECTION 7: Field mapping integrity
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("7. FIELD_MAPPING integrity")
print("=" * 60)

expected_keys = ["tracking_number", "logistics_status", "freight_forwarder"]
t("FIELD_MAPPING has 3 keys", len(FIELD_MAPPING) == 3)
t("FIELD_MAPPING keys correct", list(FIELD_MAPPING.keys()) == expected_keys)

t("STATUS_MAP has 6 entries", len(STATUS_MAP) == 6)
t("FORWARDER_MAP has 1 entry", len(FORWARDER_MAP) == 1)
t("FORWARDER_MAP key = 安装商或客户自提", list(FORWARDER_MAP.keys())[0] == "安装商或客户自提")

# ═══════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed  ({(PASS*100)//(PASS+FAIL)}%)")
print(f"{'='*60}")
