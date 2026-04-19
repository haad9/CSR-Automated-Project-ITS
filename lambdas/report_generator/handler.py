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

CLAUDE_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


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
        # Rich fallback report using raw data
        active = state_counts.get("Active", 0)
        total = data_summary["total_certificates"]
        health_pct = round((active / total * 100) if total else 0)
        expiring_list = data_summary["expiring_within_14_days"]
        exc_count = data_summary["exceptions_this_week"]

        expiring_section = ""
        if expiring_list:
            expiring_section = "\n### Certificates Requiring Immediate Attention\n"
            for e in expiring_list:
                urgency = "🔴 CRITICAL" if e["days_left"] <= 7 else "🟡 WARNING"
                expiring_section += f"- {urgency} — **{e['domain']}** ({e['days_left']} days remaining, agency: {e['agency']})\n"
        else:
            expiring_section = "\n✅ No certificates expiring within 14 days.\n"

        exc_section = ""
        if exc_count > 0:
            exc_section = f"\n### Exceptions This Week: {exc_count}\n"
            for ex in data_summary.get("exception_details", [])[:5]:
                exc_section += f"- **{ex.get('domain', ex.get('cert_id', 'Unknown'))}** — {ex.get('ai_analysis') or ex.get('error', 'See audit log')}\n"
        else:
            exc_section = "\n✅ Zero exceptions — all renewals completed without incident.\n"

        return f"""# Mississippi ITS — SSL Certificate Weekly Report
**Report Period:** {data_summary["report_period"]}
**Generated:** {now.strftime("%B %d, %Y at %H:%M UTC")}
**Classification:** Internal — IT Operations

---

## Executive Summary

The Mississippi ITS Automated Certificate Lifecycle System is managing **{total} SSL certificates** across **{data_summary["agencies"]} state agencies**. This week, **{data_summary["renewals_completed_this_week"]} renewals were completed automatically** with **{data_summary["renewals_initiated_this_week"]} initiated**, saving an estimated **{data_summary["renewals_completed_this_week"] * 2} staff-hours** compared to manual processing.

Overall system health: **{health_pct}% of certificates are currently active and valid**.

---

## Certificate Status Overview

| State | Count |
|-------|-------|
{"".join(f"| {k} | {v} |\n" for k, v in state_counts.items())}

- **Active (Secure):** {active} of {total} certificates ({health_pct}%)
- **Exceptions:** {state_counts.get("Exception", 0)} certificate(s) require manual review

---

## Renewal Activity This Week

- **Renewals Completed:** {data_summary["renewals_completed_this_week"]}
- **Renewals Initiated:** {data_summary["renewals_initiated_this_week"]}
- **Exceptions / Failures:** {exc_count}
- **Estimated Staff Hours Saved:** {data_summary["renewals_completed_this_week"] * 2} hours

{exc_section}

---

## Expiring Certificates (Next 14 Days)
{expiring_section}

---

## System Health Assessment

{"🟢 **HEALTHY** — All automated processes running normally." if exc_count == 0 else f"🟡 **ATTENTION REQUIRED** — {exc_count} exception(s) need review. All other processes running normally."}

The EventBridge scheduler triggers the monitor Lambda daily at 06:00 UTC. Step Functions orchestrates the 8-stage renewal pipeline automatically. Human approval is required only at the certificate deployment stage.

---

## Recommendations

1. {"Review and resolve the " + str(exc_count) + " open exception(s) in the Incidents tab." if exc_count > 0 else "Continue current automation — no corrective action needed."}
2. {"Address " + str(len(expiring_list)) + " certificate(s) expiring within 14 days — auto-renewal should trigger within the next monitoring cycle." if expiring_list else "No expiry concerns in the next 14-day window."}
3. Enable AWS Bedrock (Claude AI) to receive AI-authored narrative reports with pattern detection and recommendations.

---
*Report generated by Mississippi ITS Automated Certificate Lifecycle System v1.0*
*To enable AI-authored reports: AWS Console → Bedrock → Model Access → Enable Anthropic Claude*
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
