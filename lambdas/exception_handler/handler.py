"""
Lambda: Exception Handler — Phase 5 AI Layer
Called by Step Functions when any state throws an error.
Uses AWS Bedrock (Claude Haiku) to analyze the failure and produce
a human-readable explanation + recommended remediation steps.
Writes the AI analysis to DynamoDB audit log and notifies via SNS.
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
sns_client = boto3.client("sns")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
ALERT_TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]

CLAUDE_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


def write_audit(cert_id: str, action: str, details: dict):
    table = dynamodb.Table(AUDIT_TABLE)
    ts = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "cert_id": cert_id,
        "timestamp": ts,
        "action": action,
        "details": details,
        "actor": "exception-handler",
    })


def analyze_with_claude(error_info: dict, cert_context: dict) -> dict:
    """
    Send the error details to Claude Haiku for intelligent analysis.
    Returns structured analysis with root cause and remediation steps.
    """
    prompt = f"""You are an expert SSL certificate lifecycle engineer analyzing a failure in an automated certificate renewal system for Mississippi state agencies.

FAILURE DETAILS:
- Certificate ID: {cert_context.get('cert_id', 'unknown')}
- Domain: {cert_context.get('domain', 'unknown')}
- Failed State: {error_info.get('failed_state', 'unknown')}
- Error Type: {error_info.get('error_type', 'unknown')}
- Error Message: {error_info.get('error_message', 'unknown')}
- Timestamp: {datetime.now(timezone.utc).isoformat()}

Provide a structured analysis in JSON format with these exact fields:
{{
  "root_cause": "one sentence explaining why this failed",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "impact": "what is affected if not resolved",
  "remediation_steps": ["step 1", "step 2", "step 3"],
  "can_auto_retry": true/false,
  "estimated_resolution_time": "e.g. 5 minutes",
  "notify_human": true/false
}}

Respond ONLY with the JSON object, no other text."""

    try:
        response = bedrock_client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        analysis_text = body["content"][0]["text"].strip()

        # Parse JSON from Claude's response
        if analysis_text.startswith("{"):
            analysis = json.loads(analysis_text)
        else:
            # Extract JSON if wrapped in text
            start = analysis_text.find("{")
            end = analysis_text.rfind("}") + 1
            analysis = json.loads(analysis_text[start:end])

        return {**analysis, "ai_model": CLAUDE_MODEL_ID, "ai_analyzed": True}

    except Exception as e:
        logger.warning(f"Bedrock analysis failed (using fallback): {e}")
        return {
            "root_cause": f"Automated analysis unavailable. Raw error: {error_info.get('error_message', 'unknown')}",
            "severity": "HIGH",
            "impact": "Certificate renewal blocked — manual intervention required",
            "remediation_steps": [
                "Check CloudWatch logs for the failed Lambda",
                "Verify AWS service connectivity",
                "Retry the renewal workflow manually",
            ],
            "can_auto_retry": False,
            "notify_human": True,
            "ai_analyzed": False,
            "fallback_reason": str(e),
        }


def handler(event, context):
    # Extract error info from Step Functions Catch block
    error_info = event.get("error_info", {})
    cert_id = event.get("cert_id", "unknown")
    domain = event.get("domain", "unknown")
    now = datetime.now(timezone.utc)

    # Determine which state failed
    error_cause = error_info.get("Cause", "{}")
    error_type = error_info.get("Error", "UnknownError")

    try:
        cause_parsed = json.loads(error_cause) if isinstance(error_cause, str) else error_cause
        error_message = cause_parsed.get("errorMessage", str(error_cause))
    except Exception:
        error_message = str(error_cause)

    structured_error = {
        "error_type": error_type,
        "error_message": error_message,
        "failed_state": event.get("state", "unknown"),
        "raw_cause": error_cause,
    }

    logger.info(f"Analyzing exception for cert {cert_id}: {error_type}")

    # AI Analysis via Bedrock
    analysis = analyze_with_claude(structured_error, {
        "cert_id": cert_id,
        "domain": domain,
    })

    # Update cert state to show failure
    try:
        dynamodb.Table(CERT_TABLE).update_item(
            Key={"cert_id": cert_id},
            UpdateExpression="SET #s = :s, exception_at = :ts, exception_analysis = :ea",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={
                ":s": "Exception",
                ":ts": now.isoformat(),
                ":ea": analysis,
            },
        )
    except Exception as e:
        logger.warning(f"Could not update cert state: {e}")

    write_audit(cert_id, "EXCEPTION_ANALYZED", {
        "domain": domain,
        "error_type": error_type,
        "error_message": error_message,
        "ai_analysis": analysis,
    })

    # Alert if human intervention needed
    if analysis.get("notify_human", True):
        try:
            severity = analysis.get("severity", "HIGH")
            sns_client.publish(
                TopicArn=ALERT_TOPIC_ARN,
                Subject=f"[{severity}] Certificate Renewal Failed: {domain}",
                Message=(
                    f"Certificate renewal failed and requires attention.\n\n"
                    f"Domain: {domain}\nCert ID: {cert_id}\n"
                    f"Error: {error_message}\n\n"
                    f"AI Analysis:\n{json.dumps(analysis, indent=2)}"
                ),
            )
        except Exception as e:
            logger.warning(f"SNS alert failed: {e}")

    logger.info(f"Exception handled for {cert_id}: severity={analysis.get('severity')}")
    return {
        "cert_id": cert_id,
        "domain": domain,
        "state": "Exception",
        "analysis": analysis,
        "handled_at": now.isoformat(),
    }
