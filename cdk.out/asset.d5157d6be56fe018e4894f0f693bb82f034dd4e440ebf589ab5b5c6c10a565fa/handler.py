"""
Lambda: Report Generator — Phase 5 AI Layer
Generates weekly SSL certificate status reports using AWS Bedrock Claude Sonnet.
Queries DynamoDB for all cert data, audit logs, and exception history.
Produces a formatted report and stores it in S3. Returns a signed download URL.
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
s3_client = boto3.client("s3")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
AGENCIES_TABLE = os.environ["AGENCIES_TABLE"]
REPORTS_BUCKET = os.environ["REPORTS_BUCKET"]

CLAUDE_MODEL_ID = "anthropic.claude-sonnet-4-5"


def get_all_certs() -> list:
    table = dynamodb.Table(CERT_TABLE)
    resp = table.scan()
    return resp.get("Items", [])


def get_recent_audit_entries(days: int = 7) -> list:
    table = dynamodb.Table(AUDIT_TABLE)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    resp = table.scan(
        FilterExpression=Attr("timestamp").gte(since)
    )
    return resp.get("Items", [])


def get_agencies() -> list:
    table = dynamodb.Table(AGENCIES_TABLE)
    resp = table.scan()
    return resp.get("Items", [])


def generate_report_with_claude(certs: list, audit_entries: list, agencies: list, report_type: str) -> str:
    """
    Use Claude Sonnet to write a professional weekly report.
    """
    # Build statistics
    state_counts = {}
    for cert in certs:
        state = cert.get("state", "Unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

    exceptions = [e for e in audit_entries if e.get("action") == "EXCEPTION_ANALYZED"]
    renewals_completed = [e for e in audit_entries if e.get("action") == "RENEWAL_CLOSED"]
    renewals_initiated = [e for e in audit_entries if e.get("action") == "RENEWAL_INITIATED"]

    # Certs expiring in next 14 days
    now = datetime.now(timezone.utc)
    expiring_soon = []
    for cert in certs:
        try:
            expiry = datetime.strptime(cert["expiry_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_left = (expiry - now).days
            if days_left <= 14:
                expiring_soon.append({
                    "domain": cert.get("domain"),
                    "days_left": days_left,
                    "agency": cert.get("agency_id"),
                })
        except Exception:
            pass

    data_summary = {
        "report_period": f"Week ending {now.strftime('%Y-%m-%d')}",
        "total_certificates": len(certs),
        "state_breakdown": state_counts,
        "agencies": len(agencies),
        "renewals_completed_this_week": len(renewals_completed),
        "renewals_initiated_this_week": len(renewals_initiated),
        "exceptions_this_week": len(exceptions),
        "expiring_within_14_days": expiring_soon,
        "exception_details": [
            {
                "cert_id": e.get("cert_id"),
                "domain": e.get("details", {}).get("domain"),
                "error": e.get("details", {}).get("error_type"),
                "ai_analysis": e.get("details", {}).get("ai_analysis", {}).get("root_cause"),
            }
            for e in exceptions[:5]
        ],
    }

    prompt = f"""You are a senior IT systems engineer writing a weekly SSL certificate management report for Mississippi ITS (Information Technology Services) leadership.

Write a professional, executive-level report based on this data:

{json.dumps(data_summary, indent=2, default=str)}

The report should include:
1. **Executive Summary** (2-3 sentences, highlight key metrics)
2. **Certificate Status Overview** (current state breakdown)
3. **Renewal Activity This Week** (what happened)
4. **Exceptions & Incidents** (any failures, with root causes)
5. **Expiring Soon** (certs requiring attention in next 14 days)
6. **System Health Assessment** (overall automation performance)
7. **Recommendations** (1-3 actionable items)

Format: Use markdown headings and bullet points. Be concise and professional.
Tone: Government IT report — factual, clear, no marketing language."""

    try:
        response = bedrock_client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        return body["content"][0]["text"]

    except Exception as e:
        logger.warning(f"Bedrock report generation failed: {e}")
        # Fallback report
        return f"""# Mississippi ITS — SSL Certificate Weekly Report
**Period**: {data_summary['report_period']}

## Executive Summary
The automated certificate lifecycle system managed {data_summary['total_certificates']} certificates across {data_summary['agencies']} agencies this week.

## Certificate Status
{json.dumps(state_counts, indent=2)}

## Renewal Activity
- Completed: {len(renewals_completed)}
- Initiated: {len(renewals_initiated)}
- Exceptions: {len(exceptions)}

*AI report generation unavailable — see raw data above.*
"""


def handler(event, context):
    report_type = event.get("report_type", "weekly")
    now = datetime.now(timezone.utc)

    logger.info(f"Generating {report_type} report")

    certs = get_all_certs()
    audit_entries = get_recent_audit_entries(days=7 if report_type == "weekly" else 30)
    agencies = get_agencies()

    report_content = generate_report_with_claude(certs, audit_entries, agencies, report_type)

    # Store in S3
    report_key = f"reports/{report_type}/{now.strftime('%Y/%m/%d')}/report-{now.strftime('%H%M%S')}.md"
    s3_client.put_object(
        Bucket=REPORTS_BUCKET,
        Key=report_key,
        Body=report_content.encode("utf-8"),
        ContentType="text/markdown",
    )

    # Generate pre-signed download URL (valid 24h)
    download_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": REPORTS_BUCKET, "Key": report_key},
        ExpiresIn=86400,
    )

    logger.info(f"Report generated: {report_key}")
    return {
        "report_key": report_key,
        "download_url": download_url,
        "generated_at": now.isoformat(),
        "cert_count": len(certs),
        "report_preview": report_content[:500],
        "full_report": report_content,
    }
