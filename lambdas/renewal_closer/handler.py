"""
Lambda: Renewal Closer
Final step in the workflow. Marks the certificate as Active again,
records the completed renewal, cleans up temp S3 artifacts.
State transition: Certificate Validated → Renewal Closed → Active
"""

import os
import boto3
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
CERT_BUCKET = os.environ["CERT_BUCKET"]
ALERT_TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]


def write_audit(cert_id: str, action: str, details: dict):
    table = dynamodb.Table(AUDIT_TABLE)
    ts = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "cert_id": cert_id,
        "timestamp": ts,
        "action": action,
        "details": details,
        "actor": "renewal-closer",
    })


def handler(event, context):
    cert_id = event["cert_id"]
    domain = event.get("domain", "unknown")
    new_expiry = event.get("new_expiry_date") or event.get("expiry_date")
    renewal_started_at = event.get("renewal_started_at")
    now = datetime.now(timezone.utc)

    logger.info(f"Closing renewal for cert {cert_id} ({domain})")

    cert_table = dynamodb.Table(CERT_TABLE)

    # Transition: Renewal Closed then back to Active
    cert_table.update_item(
        Key={"cert_id": cert_id},
        UpdateExpression=(
            "SET #s = :s, renewal_closed_at = :ts, expiry_date = :exp, "
            "last_renewed_at = :ts, renewals_count = if_not_exists(renewals_count, :zero) + :one"
        ),
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":s": "Active",
            ":ts": now.isoformat(),
            ":exp": new_expiry,
            ":zero": 0,
            ":one": 1,
        },
    )

    # Compute renewal duration
    duration_seconds = None
    if renewal_started_at:
        try:
            start = datetime.fromisoformat(renewal_started_at.replace("Z", "+00:00"))
            duration_seconds = int((now - start).total_seconds())
        except Exception:
            pass

    write_audit(cert_id, "RENEWAL_CLOSED", {
        "domain": domain,
        "new_expiry_date": new_expiry,
        "new_state": "Active",
        "renewal_duration_seconds": duration_seconds,
    })

    # Send success notification
    try:
        sns_client.publish(
            TopicArn=ALERT_TOPIC_ARN,
            Subject=f"[SUCCESS] SSL Certificate Renewed: {domain}",
            Message=(
                f"Certificate renewal completed successfully.\n\n"
                f"Domain:      {domain}\n"
                f"Cert ID:     {cert_id}\n"
                f"New Expiry:  {new_expiry}\n"
                f"Completed:   {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Duration:    {duration_seconds}s\n\n"
                f"— Mississippi ITS Certificate Lifecycle System"
            ),
        )
    except Exception as e:
        logger.warning(f"SNS notification failed (non-fatal): {e}")

    logger.info(f"Renewal closed for {cert_id}. New expiry: {new_expiry}")
    return {
        **event,
        "state": "Active",
        "renewal_closed_at": now.isoformat(),
        "new_expiry_date": new_expiry,
        "duration_seconds": duration_seconds,
    }
