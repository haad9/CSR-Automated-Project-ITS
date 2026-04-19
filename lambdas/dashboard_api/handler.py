"""
Lambda: Dashboard API
Handles all REST API requests from the React dashboard via API Gateway.
Routes: /certs, /audit, /agencies, /governance/approve, /reports, /demo/run
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
AGENCIES_TABLE = os.environ["AGENCIES_TABLE"]
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def response(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


# ── Certs ──────────────────────────────────────────────────────────────────

def get_certs(query_params: dict) -> dict:
    table = dynamodb.Table(CERT_TABLE)
    agency_id = query_params.get("agency_id")
    state_filter = query_params.get("state")

    if agency_id:
        resp = table.query(
            IndexName="agency-index",
            KeyConditionExpression=Key("agency_id").eq(agency_id),
        )
    elif state_filter:
        resp = table.query(
            IndexName="state-index",
            KeyConditionExpression=Key("state").eq(state_filter),
        )
    else:
        resp = table.scan()

    items = resp.get("Items", [])
    return response(200, {"certs": items, "count": len(items)})


def get_cert(cert_id: str) -> dict:
    table = dynamodb.Table(CERT_TABLE)
    item = table.get_item(Key={"cert_id": cert_id}).get("Item")
    if not item:
        return response(404, {"error": f"Cert {cert_id} not found"})
    return response(200, item)


def trigger_renewal(cert_id: str, body: dict) -> dict:
    table = dynamodb.Table(CERT_TABLE)
    cert = table.get_item(Key={"cert_id": cert_id}).get("Item")
    if not cert:
        return response(404, {"error": f"Cert {cert_id} not found"})

    now = datetime.now(timezone.utc)
    execution_input = {
        "cert_id": cert_id,
        "domain": cert.get("domain"),
        "agency_id": cert.get("agency_id"),
        "expiry_date": cert.get("expiry_date"),
        "triggered_at": now.isoformat(),
        "triggered_by": body.get("triggered_by", "dashboard"),
    }

    exec_resp = sfn_client.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"manual-{cert_id}-{now.strftime('%Y%m%dT%H%M%S')}",
        input=json.dumps(execution_input),
    )

    return response(200, {
        "message": "Renewal workflow started",
        "execution_arn": exec_resp["executionArn"],
        "cert_id": cert_id,
    })


# ── Audit ──────────────────────────────────────────────────────────────────

def get_audit(cert_id: str = None, query_params: dict = None) -> dict:
    table = dynamodb.Table(AUDIT_TABLE)
    if cert_id:
        resp = table.query(
            KeyConditionExpression=Key("cert_id").eq(cert_id),
            ScanIndexForward=False,
            Limit=int((query_params or {}).get("limit", 50)),
        )
    else:
        limit = int((query_params or {}).get("limit", 100))
        resp = table.scan(Limit=limit)
    items = resp.get("Items", [])
    return response(200, {"entries": items, "count": len(items)})


# ── Agencies ───────────────────────────────────────────────────────────────

def get_agencies() -> dict:
    table = dynamodb.Table(AGENCIES_TABLE)
    resp = table.scan()
    return response(200, {"agencies": resp.get("Items", [])})


# ── Governance ─────────────────────────────────────────────────────────────

def handle_governance_approval(query_params: dict, body: dict) -> dict:
    cert_id = query_params.get("cert_id") or body.get("cert_id")
    task_token = query_params.get("token") or body.get("task_token")
    action = query_params.get("action") or body.get("action", "approve")

    if not cert_id or not task_token:
        return response(400, {"error": "cert_id and token are required"})

    now = datetime.now(timezone.utc)

    # Write audit entry
    dynamodb.Table(AUDIT_TABLE).put_item(Item={
        "cert_id": cert_id,
        "timestamp": now.isoformat(),
        "action": "GOVERNANCE_DECISION",
        "details": {"decision": action, "decided_at": now.isoformat()},
        "actor": "security-officer",
    })

    if action == "approve":
        sfn_client.send_task_success(
            taskToken=task_token,
            output=json.dumps({
                "cert_id": cert_id,
                "governance_approved": True,
                "approved_at": now.isoformat(),
            }),
        )
        return response(200, {"message": "Certificate deployment approved", "cert_id": cert_id})
    else:
        sfn_client.send_task_failure(
            taskToken=task_token,
            error="GovernanceRejected",
            cause=json.dumps({"cert_id": cert_id, "rejected_at": now.isoformat()}),
        )
        return response(200, {"message": "Certificate deployment rejected", "cert_id": cert_id})


# ── Reports ────────────────────────────────────────────────────────────────

def get_reports(query_params: dict) -> dict:
    s3_client = boto3.client("s3")
    reports_bucket = os.environ.get("REPORTS_BUCKET", "")
    try:
        resp = s3_client.list_objects_v2(
            Bucket=reports_bucket,
            Prefix="reports/",
            MaxKeys=20,
        )
        reports = [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in resp.get("Contents", [])
        ]
        return response(200, {"reports": reports})
    except Exception as e:
        return response(500, {"error": str(e)})


def generate_report(body: dict) -> dict:
    """Invoke report_generator Lambda."""
    lambda_client = boto3.client("lambda")
    resp = lambda_client.invoke(
        FunctionName="csr-reportgenerator",
        InvocationType="RequestResponse",
        Payload=json.dumps({"report_type": body.get("report_type", "weekly")}),
    )
    result = json.loads(resp["Payload"].read())
    return response(200, result)


# ── Demo ───────────────────────────────────────────────────────────────────

def run_demo(body: dict) -> dict:
    """Trigger renewals for all expiring certs — demo mode."""
    table = dynamodb.Table(CERT_TABLE)
    resp = table.scan(
        FilterExpression=Attr("state").eq("Active") & Attr("demo_cert").eq(True)
    )
    certs = resp.get("Items", [])

    executions = []
    now = datetime.now(timezone.utc)

    for cert in certs[:3]:  # Demo: trigger max 3
        cert_id = cert["cert_id"]
        exec_resp = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"demo-{cert_id}-{now.strftime('%Y%m%dT%H%M%S')}",
            input=json.dumps({
                "cert_id": cert_id,
                "domain": cert.get("domain"),
                "agency_id": cert.get("agency_id"),
                "expiry_date": cert.get("expiry_date"),
                "triggered_at": now.isoformat(),
                "triggered_by": "demo",
            }),
        )
        executions.append({
            "cert_id": cert_id,
            "domain": cert.get("domain"),
            "execution_arn": exec_resp["executionArn"],
        })

    return response(200, {
        "message": f"Demo started: {len(executions)} workflows triggered",
        "executions": executions,
    })


# ── Router ─────────────────────────────────────────────────────────────────

def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}
    body = {}
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        pass

    logger.info(f"{method} {path}")

    try:
        if path == "/certs" and method == "GET":
            return get_certs(query_params)

        elif path == "/certs" and method == "POST":
            # Create cert record
            cert_id = body.get("cert_id") or f"cert-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            body["cert_id"] = cert_id
            body["state"] = body.get("state", "Active")
            body["created_at"] = datetime.now(timezone.utc).isoformat()
            dynamodb.Table(CERT_TABLE).put_item(Item=body)
            return response(201, {"cert_id": cert_id, "message": "Created"})

        elif path.startswith("/certs/") and method == "GET" and not path.endswith("/trigger"):
            cert_id = path_params.get("cert_id") or path.split("/")[2]
            return get_cert(cert_id)

        elif path.endswith("/trigger") and method == "POST":
            cert_id = path_params.get("cert_id") or path.split("/")[2]
            return trigger_renewal(cert_id, body)

        elif path == "/audit" and method == "GET":
            return get_audit(query_params=query_params)

        elif path.startswith("/audit/") and method == "GET":
            cert_id = path_params.get("cert_id") or path.split("/")[2]
            return get_audit(cert_id=cert_id, query_params=query_params)

        elif path == "/agencies" and method == "GET":
            return get_agencies()

        elif path.startswith("/governance/approve"):
            return handle_governance_approval(query_params, body)

        elif path == "/reports" and method == "GET":
            return get_reports(query_params)

        elif path == "/reports" and method == "POST":
            return generate_report(body)

        elif path == "/demo/run" and method == "POST":
            return run_demo(body)

        else:
            return response(404, {"error": f"Route not found: {method} {path}"})

    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return response(500, {"error": str(e)})
