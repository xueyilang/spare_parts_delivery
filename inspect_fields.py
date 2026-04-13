#!/usr/bin/env python3
"""
Temporary script to fetch Feishu Bitable fields from the provided URL.
This script will:
1. Read FEISHU_APP_ID and FEISHU_APP_SECRET from .env
2. Get tenant_access_token
3. Fetch fields from the target bitable table
4. Print field names and their types
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Feishu API endpoints
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
FIELDS_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

# Target Bitable info from the URL
TARGET_APP_TOKEN = "DNn4b8zIlaHdI4sG8FVjlmAVpNb"
TARGET_TABLE_ID = "tblNRrqN3Btj6L93"
TARGET_VIEW_ID = "vewnaltTqS"

def get_tenant_access_token():
    """Get tenant_access_token from Feishu."""
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        raise ValueError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET in .env")
    
    payload = {
        "app_id": app_id,
        "app_secret": app_secret,
    }
    
    print(f"[*] Requesting token from {TOKEN_URL}...")
    response = requests.post(TOKEN_URL, json=payload, timeout=10)
    response.raise_for_status()
    
    body = response.json()
    if body.get("code") != 0 or not body.get("tenant_access_token"):
        raise RuntimeError(f"Token request failed: {body.get('msg', 'Unknown error')}")
    
    token = body["tenant_access_token"]
    print(f"[+] Token obtained successfully")
    return token

def get_table_fields(tenant_access_token):
    """Fetch table fields from Feishu Bitable."""
    url = FIELDS_URL.format(app_token=TARGET_APP_TOKEN, table_id=TARGET_TABLE_ID)
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json",
    }
    
    print(f"[*] Fetching fields from {url}...")
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(f"Field request failed: {body.get('msg', 'Unknown error')}")
    
    data = body.get("data") or {}
    items = data.get("items") or []
    
    return items

def main():
    try:
        print("=" * 80)
        print("Feishu Bitable Field Inspector")
        print("=" * 80)
        print(f"\nTarget: app_token={TARGET_APP_TOKEN}")
        print(f"        table_id={TARGET_TABLE_ID}")
        print(f"        view_id={TARGET_VIEW_ID}\n")
        
        token = get_tenant_access_token()
        fields = get_table_fields(token)
        
        if not fields:
            print("[-] No fields found in the table")
            return
        
        print(f"\n[+] Found {len(fields)} fields:\n")
        print("-" * 100)
        print(f"{'Field Name (field_name)':<50} | {'Type':<10} | {'UI Type':<15}")
        print("-" * 100)
        
        for field in fields:
            field_name = field.get("field_name", "N/A")
            field_type = field.get("type", "N/A")
            ui_type = field.get("ui_type", "N/A")
            field_id = field.get("field_id", "N/A")
            
            print(f"{field_name:<50} | {str(field_type):<10} | {ui_type:<15}")
            print(f"  └─ field_id: {field_id}")
        
        print("-" * 80)
        print(f"\n[+] Total fields: {len(fields)}")
        
        # Also dump as JSON for reference
        print("\n\nFull JSON response:")
        print(json.dumps(fields, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"[-] Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
