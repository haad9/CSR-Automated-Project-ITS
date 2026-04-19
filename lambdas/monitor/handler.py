"""
Lambda: Monitor
Runs daily via EventBridge. Scans DynamoDB cert-inventory for certs
expiring within 47 days and starts a Step Functions workflow for each.
State transition: Active → Expiration Detected
"""

import json
import os
import boto3
import logging
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")

CERT_TABLE = os.environ["CERT_TABLE"]
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
EXPIRY_THRESHOLD_DAYS = int(os.environ.get("EXPIRY_THRESHOLD_DAYS", "47"))


def handler(event, context):
    table = dynamodb.Table(CERT_TABLE)
    now = datetime.now(timezone.utc)
    threshold = now + timedelta(days=EXPIRY_THRESHOLD_DAYS)

    logger.info(f"Monitor running. Threshold: {threshold.isoformat()}")

    # Scan for Active certs expiring within threshold
    response = table.scan(
        FilterExpression=(
            Attr("state").eq("Active") &
            Attr("expiry_date").lte(threshold.strftime("%Y-%m-%d"))
        )
    )

    certs = response.get("Items", [])
    logger.info(f"Found {len(certs)} certs nearing expiry")

    triggered = []
    skipped = []

    for cert in certs:
        cert_id = cert["cert_id"]
        domain = cert.get("domain", "unknown")

        # Update state to Expiration Detected
        try:
            table.update_item(
                Key={"cert_id": cert_id},
                UpdateExpression="SET #s = :s, detected_at = :ts",
                ConditionExpression=Attr("state").eq("Active"),
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={
                    ":s": "Expiration Detected",
                    ":ts": now.isoformat(),
                },
            )
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            logger.warning(f"Cert {cert_id} state already changed, skipping")
            skipped.append(cert_id)
            continue

        # Start Step Functions workflow
        execution_input = {
            "cert_id": cert_id,
            "domain": domain,
            "agency_id": cert.get("agency_id"),
            "expiry_date": cert.get("expiry_date"),
            "triggered_at": now.isoformat(),
        }

        sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"renewal-{cert_id}-{now.strftime('%Y%m%dT%H%M%S')}",
            input=json.dumps(execution_input),
        )

        logger.info(f"Started workflow for cert {cert_id} ({domain})")
        triggered.append(cert_id)

    result = {
        "triggered": len(triggered),
        "skipped": len(skipped),
        "cert_ids": triggered,
        "timestamp": now.isoformat(),
    }
    logger.info(f"Monitor complete: {result}")
    return result
