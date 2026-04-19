"""
Lambda: Renewal Initiator
First step in the Step Functions workflow.
State transition: Expiration Detected → Renewal Initiated
Writes the first audit entry for this renewal cycle.
"""

import os
import boto3
import logging
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]


def write_audit(cert_id: str, action: str, details: dict):
    table = dynamodb.Table(AUDIT_TABLE)
    ts = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "cert_id": cert_id,
        "timestamp": ts,
        "action": action,
        "details": details,
        "actor": "system",
    })


def handler(event, context):
    cert_id = event["cert_id"]
    domain = event.get("domain", "unknown")
    now = datetime.now(timezone.utc)

    logger.info(f"Initiating renewal for cert {cert_id} ({domain})")

    cert_table = dynamodb.Table(CERT_TABLE)

    # Transition: Expiration Detected → Renewal Initiated
    cert_table.update_item(
        Key={"cert_id": cert_id},
        UpdateExpression="SET #s = :s, renewal_started_at = :ts",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":s": "Renewal Initiated",
            ":ts": now.isoformat(),
        },
    )

    write_audit(cert_id, "RENEWAL_INITIATED", {
        "domain": domain,
        "previous_state": "Expiration Detected",
        "new_state": "Renewal Initiated",
    })

    logger.info(f"Renewal initiated for {cert_id}")
    return {**event, "state": "Renewal Initiated", "renewal_started_at": now.isoformat()}
