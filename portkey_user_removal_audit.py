#!/usr/bin/env python3
"""
Portkey User Removal Audit Script

Queries the Portkey Audit Logs API to identify users removed in the last 24 hours.
User removals can happen via:
  1. SCIM PUT with active=false (IdP-driven deprovisioning)
  2. SCIM DELETE on a user endpoint
  3. SCIM PATCH to deactivate
  4. Direct user deletion via the Users API
  5. Workspace member removal
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API_KEY = os.environ.get("PORTKEY_ADMIN_API_KEY")
if not API_KEY:
    print("ERROR: PORTKEY_ADMIN_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.portkey.ai/v1"
ORG_ID = "d1243619-42c1-49ed-98d8-3acb99d8c21b"
HEADERS = {"x-portkey-api-key": API_KEY}

now = datetime.now(timezone.utc)
start_time = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_page(page=0, page_size=100):
    """Fetch a single page of audit logs."""
    params = {
        "start_time": start_time,
        "end_time": end_time,
        "organisation_id": ORG_ID,
        "page_size": page_size,
        "current_page": page,
    }
    for attempt in range(4):
        resp = requests.get(f"{BASE_URL}/audit-logs", params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if attempt < 3:
            wait = 2 ** (attempt + 1)
            print(f"      Retry {attempt+1}/3 after HTTP {resp.status_code} (waiting {wait}s)...")
            time.sleep(wait)
        else:
            print(f"ERROR: HTTP {resp.status_code} after 4 attempts: {resp.text}", file=sys.stderr)
            sys.exit(1)


def fetch_all_logs():
    """Paginate through all audit log pages."""
    all_records = []
    page = 0
    page_size = 100
    first = fetch_page(page, page_size)
    total = first.get("total", 0)
    all_records.extend(first.get("records", []))
    print(f"      Total records in time window: {total}")

    while len(all_records) < total:
        page += 1
        time.sleep(0.2)
        data = fetch_page(page, page_size)
        records = data.get("records", [])
        if not records:
            break
        all_records.extend(records)
        if page % 3 == 0:
            print(f"      Fetched {len(all_records)} / {total}...")

    return all_records


def parse_body(raw):
    """Safely parse the request_body JSON string."""
    if not raw or raw == "{}":
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def scim_user_info(body):
    """Extract user display name and email from a SCIM request body."""
    name = body.get("displayName", "Unknown")
    emails = body.get("emails", [])
    email = next((e["value"] for e in emails if e.get("primary")), "")
    if not email and emails:
        email = emails[0].get("value", "")
    username = body.get("userName", email)
    return name, email, username


def make_removal(rtype, record, name="Unknown", email="", username=""):
    return {
        "type": rtype,
        "timestamp": record["timestamp"],
        "user_name": name,
        "user_email": email,
        "username": username,
        "uri": record.get("uri", ""),
        "status_code": record.get("response_status_code", 0),
        "client_ip": record.get("client_ip", ""),
        "country": record.get("country", ""),
        "request_id": record.get("request_id", ""),
        "actor_user_id": record.get("user_id", ""),
        "actor_type": record.get("user_type", ""),
    }


def main():
    print("=" * 80)
    print("PORTKEY USER REMOVAL AUDIT - Last 24 Hours")
    print(f"Time window : {start_time}  to  {end_time}")
    print(f"Organisation: {ORG_ID}")
    print("=" * 80)

    print("\nFetching all audit logs...")
    all_records = fetch_all_logs()
    print(f"      Retrieved {len(all_records)} records\n")

    removals = []
    methods = {}

    for record in all_records:
        method = record.get("method", "")
        uri = record.get("uri", "")
        lu = uri.lower()
        methods[method] = methods.get(method, 0) + 1

        # 1) SCIM PUT with active=false
        if method == "PUT" and "/scim/" in lu and "/users/" in lu:
            body = parse_body(record.get("request_body"))
            if body.get("active") is False:
                name, email, uname = scim_user_info(body)
                removals.append(make_removal("SCIM Deactivation (active=false)", record, name, email, uname))

        # 2) SCIM DELETE /Users/
        elif method == "DELETE" and "/scim/" in lu and "/users/" in lu:
            removals.append(make_removal("SCIM User Deletion (DELETE)", record))

        # 3) Direct user deletion (non-SCIM)
        elif method == "DELETE" and "/users" in lu and "scim" not in lu:
            body = parse_body(record.get("request_body"))
            removals.append(make_removal(
                "Direct User Deletion", record,
                body.get("displayName", body.get("name", "Unknown")),
                body.get("email", ""),
                body.get("userName", ""),
            ))

        # 4) Workspace member removal
        elif method == "DELETE" and "/member" in lu:
            body = parse_body(record.get("request_body"))
            removals.append(make_removal(
                "Workspace Member Removal", record,
                body.get("name", "Unknown"),
                body.get("email", ""),
            ))

        # 5) SCIM PATCH to deactivate
        elif method == "PATCH" and "/scim/" in lu and "/users/" in lu:
            body = parse_body(record.get("request_body"))
            ops = body.get("Operations", body.get("operations", []))
            if isinstance(ops, list):
                for op in ops:
                    path = str(op.get("path", ""))
                    value = op.get("value", "")
                    vs = json.dumps(value).lower() if not isinstance(value, str) else value.lower()
                    if "active" in path.lower() and "false" in vs:
                        name, email, uname = scim_user_info(body)
                        removals.append(make_removal("SCIM PATCH Deactivation", record, name, email, uname))
                        break

    print(f"  Methods breakdown: {json.dumps(methods, indent=2)}")

    # Deduplicate
    seen = set()
    unique = []
    for r in removals:
        rid = r["request_id"]
        if rid in seen:
            continue
        seen.add(rid)
        unique.append(r)

    ok = sorted([r for r in unique if 200 <= r["status_code"] < 300], key=lambda x: x["timestamp"], reverse=True)
    fail = sorted([r for r in unique if r["status_code"] >= 300], key=lambda x: x["timestamp"], reverse=True)

    # --- Print results ---
    print("\n" + "=" * 80)
    print("RESULTS: USER REMOVALS IN THE LAST 24 HOURS")
    print("=" * 80)

    if not ok:
        print("\n  No successful user removals detected in the last 24 hours.")
    else:
        print(f"\n  TOTAL SUCCESSFUL USER REMOVALS: {len(ok)}\n")
        for i, r in enumerate(ok, 1):
            print(f"  --- Removal #{i} ---")
            print(f"    Type       : {r['type']}")
            print(f"    Timestamp  : {r['timestamp']}")
            print(f"    User Name  : {r['user_name']}")
            if r["user_email"]:
                print(f"    User Email : {r['user_email']}")
            if r.get("username") and r["username"] != r.get("user_email"):
                print(f"    Username   : {r['username']}")
            print(f"    URI        : {r['uri']}")
            print(f"    HTTP Status: {r['status_code']}")
            print(f"    Actor      : {r['actor_type']} ({r['actor_user_id']})")
            print(f"    Client IP  : {r['client_ip']}  ({r['country']})")
            print(f"    Request ID : {r['request_id']}")
            print()

    if fail:
        print(f"\n  FAILED REMOVAL ATTEMPTS: {len(fail)}")
        for i, r in enumerate(fail, 1):
            print(f"    #{i} [{r['timestamp']}] {r['type']}: {r['user_name']} -> HTTP {r['status_code']}")

    # JSON report
    by_type = {}
    for r in ok:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    report = {
        "audit_window": {"start": start_time, "end": end_time},
        "organisation_id": ORG_ID,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_records_scanned": len(all_records),
        "summary": {
            "total_successful_removals": len(ok),
            "total_failed_attempts": len(fail),
            "by_type": by_type,
        },
        "successful_removals": ok,
        "failed_removals": fail,
    }
    path = "/workspace/portkey_user_removal_report.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Audit log records scanned : {len(all_records)}")
    print(f"  Successful user removals  : {len(ok)}")
    print(f"  Failed removal attempts   : {len(fail)}")
    if by_type:
        print("  Breakdown by type:")
        for t, c in by_type.items():
            print(f"    - {t}: {c}")
    print(f"\n  JSON report: {path}")


if __name__ == "__main__":
    main()
