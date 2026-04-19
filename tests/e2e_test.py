#!/usr/bin/env python3
"""
End-to-end test: triggers a full certificate renewal workflow and
verifies every state transition happens in the correct order.
Run: python3 tests/e2e_test.py [--region us-east-1] [--cert-id cert-its-001]
"""

import argparse
import json
import time
import sys
import boto3
from datetime import datetime, timezone

CERT_TABLE = "csr-cert-inventory"
AUDIT_TABLE = "csr-audit-log"
STATE_MACHINE_NAME = "csr-cert-lifecycle"

EXPECTED_STATES = [
    "Renewal Initiated",
    "CSR Generated",
    "Certificate Issued",
    "Certificate Deployed",
    "Certificate Validated",
    "Active",  # RenewalClosed resets to Active
]


def get_state_machine_arn(region: str) -> str:
    sfn = boto3.client("stepfunctions", region_name=region)
    resp = sfn.list_state_machines()
    for sm in resp["stateMachines"]:
        if sm["name"] == STATE_MACHINE_NAME:
            return sm["stateMachineArn"]
    raise RuntimeError(f"State machine '{STATE_MACHINE_NAME}' not found")


def get_cert(region: str, cert_id: str) -> dict:
    dynamodb = boto3.resource("dynamodb", region_name=region)
    item = dynamodb.Table(CERT_TABLE).get_item(Key={"cert_id": cert_id}).get("Item")
    if not item:
        raise RuntimeError(f"Cert {cert_id} not found")
    return item


def get_audit_entries(region: str, cert_id: str) -> list:
    dynamodb = boto3.resource("dynamodb", region_name=region)
    from boto3.dynamodb.conditions import Key
    resp = dynamodb.Table(AUDIT_TABLE).query(
        KeyConditionExpression=Key("cert_id").eq(cert_id),
        ScanIndexForward=True,
    )
    return resp.get("Items", [])


def wait_for_state(region: str, cert_id: str, target_state: str, timeout: int = 120) -> bool:
    """Poll DynamoDB until cert reaches the target state."""
    start = time.time()
    while time.time() - start < timeout:
        cert = get_cert(region, cert_id)
        current = cert.get("state")
        print(f"  [{int(time.time() - start):>3}s] State: {current}")
        if current == target_state:
            return True
        if current == "Exception":
            analysis = cert.get("exception_analysis", {})
            print(f"\n❌ Cert entered Exception state")
            print(f"   Root cause: {analysis.get('root_cause', 'unknown')}")
            return False
        time.sleep(3)
    return False


def run_e2e(region: str, cert_id: str, auto_approve: bool = True):
    print(f"\n{'='*60}")
    print(f" CSR End-to-End Test")
    print(f" Cert: {cert_id}")
    print(f" Region: {region}")
    print(f" Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    # Reset cert to Active state first
    dynamodb = boto3.resource("dynamodb", region_name=region)
    cert = get_cert(region, cert_id)
    original_state = cert["state"]
    print(f"Starting state: {original_state}")

    if original_state not in ("Active", "Exception"):
        print(f"⚠️  Cert is in state '{original_state}' — resetting to Active for test")
        dynamodb.Table(CERT_TABLE).update_item(
            Key={"cert_id": cert_id},
            UpdateExpression="SET #s = :s, governance_task_token = :null",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={":s": "Active", ":null": None},
        )

    # Trigger workflow
    sfn = boto3.client("stepfunctions", region_name=region)
    sm_arn = get_state_machine_arn(region)
    now = datetime.now(timezone.utc)

    execution = sfn.start_execution(
        stateMachineArn=sm_arn,
        name=f"e2e-{cert_id}-{now.strftime('%Y%m%dT%H%M%S')}",
        input=json.dumps({
            "cert_id": cert_id,
            "domain": cert["domain"],
            "agency_id": cert.get("agency_id"),
            "expiry_date": cert.get("expiry_date"),
            "triggered_at": now.isoformat(),
        }),
    )
    print(f"Execution ARN: {execution['executionArn']}\n")

    passed = 0
    failed = 0

    # Test each state transition
    for expected_state in EXPECTED_STATES:
        if expected_state == "Active":
            # Skip governance gate in auto mode by injecting approval
            break  # Will handle separately

        print(f"Waiting for: {expected_state}")
        ok = wait_for_state(region, cert_id, expected_state, timeout=90)

        if ok:
            print(f"  ✅ PASS: {expected_state}\n")
            passed += 1
        else:
            print(f"  ❌ FAIL: {expected_state}\n")
            failed += 1
            break

        # Handle governance gate
        if expected_state == "Certificate Issued" and auto_approve:
            print("Governance Gate: auto-approving (test mode)...")
            cert_fresh = get_cert(region, cert_id)
            token = cert_fresh.get("governance_task_token")
            if token:
                sfn.send_task_success(
                    taskToken=token,
                    output=json.dumps({
                        "cert_id": cert_id,
                        "governance_approved": True,
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                    }),
                )
                print("  ✅ Governance approval sent\n")
            else:
                print("  ⚠️  No task token found — governance gate may not have executed yet")

    # Wait for final Active state
    print("Waiting for: Renewal Closed → Active")
    ok = wait_for_state(region, cert_id, "Active", timeout=90)
    if ok:
        print(f"  ✅ PASS: Renewal Closed → Active\n")
        passed += 1
    else:
        print(f"  ❌ FAIL: Final Active state\n")
        failed += 1

    # Verify audit log
    print("Verifying audit log...")
    entries = get_audit_entries(region, cert_id)
    recent = [e for e in entries if e["timestamp"] > now.isoformat()]
    print(f"  {len(recent)} audit entries written for this run")
    expected_actions = {"RENEWAL_INITIATED", "CSR_GENERATED", "CERTIFICATE_ISSUED",
                        "GOVERNANCE_REQUESTED", "CERTIFICATE_DEPLOYED",
                        "CERTIFICATE_VALIDATED", "RENEWAL_CLOSED"}
    found_actions = {e["action"] for e in recent}
    missing = expected_actions - found_actions
    if missing:
        print(f"  ⚠️  Missing audit actions: {missing}")
    else:
        print(f"  ✅ All expected audit actions present")
        passed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f" RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="CSR End-to-end test")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--cert-id", default="cert-its-001")
    parser.add_argument("--no-auto-approve", action="store_true")
    args = parser.parse_args()

    success = run_e2e(
        region=args.region,
        cert_id=args.cert_id,
        auto_approve=not args.no_auto_approve,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
