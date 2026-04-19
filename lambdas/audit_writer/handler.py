"""
Lambda: Audit Writer
Utility Lambda — can be called directly to write an audit entry.
Also used by DynamoDB Streams to capture all cert state changes
and write immutable audit records.
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

AUDIT_TABLE = os.environ["AUDIT_TABLE"]
CERT_TABLE = os.environ["CERT_TABLE"]


def write_entry(cert_id: str, action: str, details: dict, actor: str = "system"):
    table = dynamodb.Table(AUDIT_TABLE)
    ts = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "cert_id": cert_id,
        "timestamp": ts,
        "action": action,
        "details": details,
        "actor": actor,
    })
    return ts


def process_dynamodb_stream(record: dict):
    """Process a DynamoDB Streams record — capture state changes."""
    if record.get("eventName") not in ("MODIFY", "INSERT"):
        return

    new_image = record.get("dynamodb", {}).get("NewImage", {})
    old_image = record.get("dynamodb", {}).get("OldImage", {})

    cert_id = new_image.get("cert_id", {}).get("S")
    if not cert_id:
        return

    new_state = new_image.get("state", {}).get("S")
    old_state = old_image.get("state", {}).get("S") if old_image else None

    if new_state and new_state != old_state:
        write_entry(
            cert_id=cert_id,
            action="STATE_CHANGE",
            details={
                "old_state": old_state,
                "new_state": new_state,
                "source": "dynamodb-stream",
            },
            actor="stream-processor",
        )


def handler(event, context):
    # Direct invocation mode
    if "cert_id" in event and "action" in event:
        cert_id = event["cert_id"]
        action = event["action"]
        details = event.get("details", {})
        actor = event.get("actor", "system")
        ts = write_entry(cert_id, action, details, actor)
        return {"written": True, "timestamp": ts}

    # DynamoDB Streams trigger mode
    if "Records" in event:
        for record in event["Records"]:
            if record.get("eventSource") == "aws:dynamodb":
                process_dynamodb_stream(record)
        return {"processed": len(event["Records"])}

    return {"error": "Unknown invocation mode"}
