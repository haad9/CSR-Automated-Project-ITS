"""
Lambda: CSR Generator
Generates a 2048-bit RSA private key and a Certificate Signing Request (CSR).
Stores both in S3. Updates cert state to CSR Generated.
State transition: Renewal Initiated → CSR Generated
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509 import (
    CertificateSigningRequestBuilder,
    NameAttribute,
)
from cryptography.x509.oid import NameOID

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
CERT_BUCKET = os.environ["CERT_BUCKET"]


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
    domain = event.get("domain", "example.com")
    now = datetime.now(timezone.utc)

    logger.info(f"Generating CSR for cert {cert_id} domain {domain}")

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Serialize private key (PEM, unencrypted for demo)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Build CSR
    csr = (
        CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            NameAttribute(NameOID.COMMON_NAME, domain),
            NameAttribute(NameOID.ORGANIZATION_NAME, "Mississippi ITS"),
            NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Mississippi"),
            NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ]))
        .sign(private_key, hashes.SHA256())
    )

    csr_pem = csr.public_bytes(serialization.Encoding.PEM)

    # Store key + CSR in S3
    key_s3_path = f"certs/{cert_id}/private.key"
    csr_s3_path = f"certs/{cert_id}/request.csr"

    s3_client.put_object(
        Bucket=CERT_BUCKET,
        Key=key_s3_path,
        Body=private_key_pem,
        ServerSideEncryption="AES256",
    )
    s3_client.put_object(
        Bucket=CERT_BUCKET,
        Key=csr_s3_path,
        Body=csr_pem,
        ServerSideEncryption="AES256",
    )

    # Update DynamoDB
    dynamodb.Table(CERT_TABLE).update_item(
        Key={"cert_id": cert_id},
        UpdateExpression="SET #s = :s, csr_generated_at = :ts, key_s3_path = :kp, csr_s3_path = :cp",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":s": "CSR Generated",
            ":ts": now.isoformat(),
            ":kp": key_s3_path,
            ":cp": csr_s3_path,
        },
    )

    write_audit(cert_id, "CSR_GENERATED", {
        "domain": domain,
        "key_s3_path": key_s3_path,
        "csr_s3_path": csr_s3_path,
        "new_state": "CSR Generated",
    })

    logger.info(f"CSR generated and stored for {cert_id}")
    return {
        **event,
        "state": "CSR Generated",
        "key_s3_path": key_s3_path,
        "csr_s3_path": csr_s3_path,
        "csr_generated_at": now.isoformat(),
    }
