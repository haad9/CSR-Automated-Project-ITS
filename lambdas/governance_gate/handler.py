"""
Lambda: Governance Gate
Emails the security officer for approval before deploying the new cert.
Uses Step Functions waitForTaskToken pattern — pauses workflow until officer approves.
The approval link in the email calls the API Gateway /governance/approve endpoint
which calls sfn:SendTaskSuccess to resume the workflow.
State transition: Certificate Issued → (wait) → Certificate Deployed
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sns_client = boto3.client("sns")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
GOVERNANCE_TOPIC_ARN = os.environ["GOVERNANCE_TOPIC_ARN"]

# Override in env for demo
OFFICER_EMAIL = os.environ.get("OFFICER_EMAIL", "security-officer@its.ms.gov")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod")


def write_audit(cert_id: str, action: str, details: dict):
    table = dynamodb.Table(AUDIT_TABLE)
    ts = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "cert_id": cert_id,
        "timestamp": ts,
        "action": action,
        "details": details,
        "actor": "governance-gate",
    })


def handler(event, context):
    task_token = event["task_token"]
    payload = event["input"]
    cert_id = payload["cert_id"]
    domain = payload.get("domain", "unknown")
    new_expiry = payload.get("new_expiry_date", "unknown")
    now = datetime.now(timezone.utc)

    logger.info(f"Governance gate: awaiting approval for {cert_id} ({domain})")

    # Build approval / rejection URLs
    approve_url = f"{API_BASE_URL}/governance/approve?cert_id={cert_id}&token={task_token}&action=approve"
    reject_url = f"{API_BASE_URL}/governance/approve?cert_id={cert_id}&token={task_token}&action=reject"

    # Publish to SNS (which emails the security officer)
    message = f"""
SSL Certificate Renewal Approval Required
==========================================

Certificate: {cert_id}
Domain:      {domain}
New Expiry:  {new_expiry}
Requested:   {now.strftime('%Y-%m-%d %H:%M UTC')}

Please review and take action:

✅ APPROVE deployment:
{approve_url}

❌ REJECT deployment:
{reject_url}

This request will expire in 24 hours.

— Mississippi ITS Certificate Lifecycle System
"""

    sns_client.publish(
        TopicArn=GOVERNANCE_TOPIC_ARN,
        Subject=f"[ACTION REQUIRED] SSL Cert Renewal Approval: {domain}",
        Message=message,
    )

    # Update DynamoDB to show awaiting approval
    dynamodb.Table(CERT_TABLE).update_item(
        Key={"cert_id": cert_id},
        UpdateExpression="SET governance_requested_at = :ts, governance_task_token = :tt",
        ExpressionAttributeValues={
            ":ts": now.isoformat(),
            ":tt": task_token,
        },
    )

    write_audit(cert_id, "GOVERNANCE_REQUESTED", {
        "domain": domain,
        "officer_notified_at": now.isoformat(),
        "approval_pending": True,
    })

    logger.info(f"Governance approval request sent for {cert_id}")
    # Return nothing — Step Functions waits for the task token to be sent back
    return {"status": "waiting_for_approval", "cert_id": cert_id}
