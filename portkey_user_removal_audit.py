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

ORG_ID = os.environ.get("PORTKEY_ORG_ID")
if not ORG_ID:
    print("ERROR: PORTKEY_ORG_ID environment variable not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.portkey.ai/v1"
HEADERS = {"x-portkey-api-key": API_KEY}
ISO8601_FMT = "%Y-%m-%dT%H:%M:%SZ"
SCIM_PATH = "/scim/"
USERS_PATH = "/users/"
REQUEST_BODY_KEY = "request_body"
UNKNOWN_USER = "Unknown"
METHOD_DELETE = "DELETE"

now = datetime.now(timezone.utc)
start_time = (now - timedelta(hours=24)).strftime(ISO8601_FMT)
end_time = now.strftime(ISO8601_FMT)


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
    return None


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
    name = body.get("displayName", UNKNOWN_USER)
    emails = body.get("emails", [])
    email = next((e["value"] for e in emails if e.get("primary")), "")
    if not email and emails:
        email = emails[0].get("value", "")
    username = body.get("userName", email)
    return name, email, username


def make_removal(rtype, record, name=UNKNOWN_USER, email="", username=""):
    """Build a removal event dict from an audit log record."""
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


def _check_scim_put(record, lu):
    """Check for SCIM PUT deactivation (active=false)."""
    if SCIM_PATH not in lu or USERS_PATH not in lu:
        return None
    body = parse_body(record.get(REQUEST_BODY_KEY))
    if body.get("active") is not False:
        return None
    name, email, uname = scim_user_info(body)
    return make_removal("SCIM Deactivation (active=false)", record, name, email, uname)


def _check_scim_delete(record, lu):
    """Check for SCIM DELETE on a user endpoint."""
    if SCIM_PATH not in lu or USERS_PATH not in lu:
        return None
    return make_removal("SCIM User Deletion (DELETE)", record)


def _check_direct_delete(record, lu):
    """Check for direct (non-SCIM) user deletion."""
    if USERS_PATH not in lu or SCIM_PATH in lu:
        return None
    body = parse_body(record.get(REQUEST_BODY_KEY))
    return make_removal(
        "Direct User Deletion", record,
        body.get("displayName", body.get("name", UNKNOWN_USER)),
        body.get("email", ""),
        body.get("userName", ""),
    )


def _check_member_removal(record, lu):
    """Check for workspace member removal."""
    if "/member" not in lu:
        return None
    body = parse_body(record.get(REQUEST_BODY_KEY))
    return make_removal(
        "Workspace Member Removal", record,
        body.get("name", UNKNOWN_USER),
        body.get("email", ""),
    )


def _check_scim_patch(record, lu):
    """Check for SCIM PATCH deactivation."""
    if SCIM_PATH not in lu or USERS_PATH not in lu:
        return None
    body = parse_body(record.get(REQUEST_BODY_KEY))
    ops = body.get("Operations", body.get("operations", []))
    if not isinstance(ops, list):
        return None
    for op in ops:
        path = str(op.get("path", ""))
        value = op.get("value", "")
        vs = json.dumps(value).lower() if not isinstance(value, str) else value.lower()
        if "active" in path.lower() and "false" in vs:
            name, email, uname = scim_user_info(body)
            return make_removal("SCIM PATCH Deactivation", record, name, email, uname)
    return None


def classify_record(record):
    """Classify an audit log record, returning a removal dict or None."""
    method = record.get("method", "")
    lu = record.get("uri", "").lower()

    handlers = {
        "PUT": _check_scim_put,
        METHOD_DELETE: lambda r, u: (
            _check_scim_delete(r, u)
            or _check_direct_delete(r, u)
            or _check_member_removal(r, u)
        ),
        "PATCH": _check_scim_patch,
    }
    handler = handlers.get(method)
    if handler:
        return handler(record, lu)
    return None


def deduplicate(removals):
    """Deduplicate removals by request_id."""
    seen = set()
    unique = []
    for r in removals:
        rid = r["request_id"]
        if rid in seen:
            continue
        seen.add(rid)
        unique.append(r)
    return unique


def print_results(ok, fail):
    """Print the human-readable results."""
    print("\n" + "=" * 80)
    print("RESULTS: USER REMOVALS IN THE LAST 24 HOURS")
    print("=" * 80)

    if not ok:
        print("\n  No successful user removals detected in the last 24 hours.")
        return

    print(f"\n  TOTAL SUCCESSFUL USER REMOVALS: {len(ok)}\n")
    for i, r in enumerate(ok, 1):
        _print_removal(i, r)

    if fail:
        print(f"\n  FAILED REMOVAL ATTEMPTS: {len(fail)}")
        for i, r in enumerate(fail, 1):
            print(f"    #{i} [{r['timestamp']}] {r['type']}: {r['user_name']} -> HTTP {r['status_code']}")


def _print_removal(index, r):
    """Print a single removal entry."""
    print(f"  --- Removal #{index} ---")
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


def write_report(ok, fail, total_scanned):
    """Write the JSON report file and return the path."""
    by_type = {}
    for r in ok:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    report = {
        "audit_window": {"start": start_time, "end": end_time},
        "organisation_id": ORG_ID,
        "generated_at": now.strftime(ISO8601_FMT),
        "total_records_scanned": total_scanned,
        "summary": {
            "total_successful_removals": len(ok),
            "total_failed_attempts": len(fail),
            "by_type": by_type,
        },
        "successful_removals": ok,
        "failed_removals": fail,
    }
    report_dir = os.environ.get("REPORT_DIR", "/tmp")
    path = os.path.join(report_dir, "portkey_user_removal_report.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path, by_type


def main():
    """Run the audit."""
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
        methods[record.get("method", "")] = methods.get(record.get("method", ""), 0) + 1
        removal = classify_record(record)
        if removal:
            removals.append(removal)

    print(f"  Methods breakdown: {json.dumps(methods, indent=2)}")

    unique = deduplicate(removals)
    ok = sorted([r for r in unique if 200 <= r["status_code"] < 300], key=lambda x: x["timestamp"], reverse=True)
    fail = sorted([r for r in unique if r["status_code"] >= 300], key=lambda x: x["timestamp"], reverse=True)

    print_results(ok, fail)
    path, by_type = write_report(ok, fail, len(all_records))

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
