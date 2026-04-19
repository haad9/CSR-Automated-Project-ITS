"""
Lambda: Deployer
Pushes the signed certificate and private key to the Nginx server on EC2
via AWS SSM Run Command (no SSH needed).
State transition: Certificate Issued → Certificate Deployed
"""

import os
import json
import boto3
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
CERT_BUCKET = os.environ["CERT_BUCKET"]

# EC2 instance ID from SSM Parameter Store
EC2_INSTANCE_PARAM = "/csr/ec2-instance-id"


def write_audit(cert_id: str, action: str, details: dict):
    table = dynamodb.Table(AUDIT_TABLE)
    ts = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "cert_id": cert_id,
        "timestamp": ts,
        "action": action,
        "details": details,
        "actor": "deployer",
    })


def get_instance_id() -> str:
    try:
        resp = ssm_client.get_parameter(Name=EC2_INSTANCE_PARAM)
        return resp["Parameter"]["Value"]
    except Exception as e:
        raise RuntimeError(f"Could not fetch EC2 instance ID from SSM: {e}")


def get_s3_content(bucket: str, key: str) -> str:
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read().decode("utf-8")


def deploy_via_ssm(instance_id: str, cert_pem: str, key_pem: str, domain: str) -> str:
    """
    Use SSM Run Command to write cert + key to Nginx config paths and reload.
    """
    nginx_cert_path = f"/etc/nginx/certs/{domain}.crt"
    nginx_key_path = f"/etc/nginx/certs/{domain}.key"
    nginx_conf_path = f"/etc/nginx/conf.d/{domain}.conf"

    nginx_conf = f"""
server {{
    listen 443 ssl;
    server_name {domain};
    ssl_certificate {nginx_cert_path};
    ssl_certificate_key {nginx_key_path};
    ssl_protocols TLSv1.2 TLSv1.3;
    location / {{
        return 200 'CSR Demo: {domain} — Certificate Active';
        add_header Content-Type text/plain;
    }}
}}
server {{
    listen 80;
    server_name {domain};
    return 301 https://$host$request_uri;
}}
"""

    # Escape the PEM content for shell heredoc
    cert_escaped = cert_pem.replace("\\", "\\\\").replace("'", "'\\''")
    key_escaped = key_pem.replace("\\", "\\\\").replace("'", "'\\''")
    conf_escaped = nginx_conf.replace("\\", "\\\\").replace("'", "'\\''")

    commands = [
        "set -e",
        f"mkdir -p /etc/nginx/certs",
        f"cat > '{nginx_cert_path}' << 'CERT_EOF'",
        cert_pem,
        "CERT_EOF",
        f"cat > '{nginx_key_path}' << 'KEY_EOF'",
        key_pem,
        "KEY_EOF",
        f"chmod 600 '{nginx_key_path}'",
        f"cat > '{nginx_conf_path}' << 'CONF_EOF'",
        nginx_conf,
        "CONF_EOF",
        "nginx -t && systemctl reload nginx",
        "echo 'Deploy successful'",
    ]

    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
        TimeoutSeconds=60,
    )

    command_id = response["Command"]["CommandId"]

    # Wait for command completion
    for _ in range(30):
        time.sleep(2)
        inv = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        status = inv["Status"]
        if status == "Success":
            return command_id
        elif status in ("Failed", "Cancelled", "TimedOut"):
            raise RuntimeError(f"SSM command {command_id} failed: {inv.get('StandardErrorContent', '')}")

    raise TimeoutError(f"SSM command {command_id} timed out")


def handler(event, context):
    cert_id = event["cert_id"]
    domain = event.get("domain", "example.com")
    cert_s3_path = event.get("cert_s3_path")
    key_s3_path = event.get("key_s3_path")
    now = datetime.now(timezone.utc)

    logger.info(f"Deployer: deploying cert {cert_id} ({domain}) to Nginx")

    # Fetch cert and key from S3
    cert_pem = get_s3_content(CERT_BUCKET, cert_s3_path)
    key_pem = get_s3_content(CERT_BUCKET, key_s3_path)

    # Get EC2 instance
    instance_id = get_instance_id()

    # Deploy via SSM
    command_id = deploy_via_ssm(instance_id, cert_pem, key_pem, domain)

    # Update DynamoDB
    dynamodb.Table(CERT_TABLE).update_item(
        Key={"cert_id": cert_id},
        UpdateExpression="SET #s = :s, deployed_at = :ts, deploy_command_id = :cmd",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":s": "Certificate Deployed",
            ":ts": now.isoformat(),
            ":cmd": command_id,
        },
    )

    write_audit(cert_id, "CERTIFICATE_DEPLOYED", {
        "domain": domain,
        "instance_id": instance_id,
        "ssm_command_id": command_id,
        "new_state": "Certificate Deployed",
    })

    logger.info(f"Certificate deployed for {cert_id}")
    return {
        **event,
        "state": "Certificate Deployed",
        "deployed_at": now.isoformat(),
        "instance_id": instance_id,
    }
