"""
Lambda: ACME Client
Submits the CSR to Pebble CA (ACME protocol) and retrieves the signed certificate.
Stores the signed cert in S3. Updates cert state to Certificate Issued.
State transition: CSR Generated → Certificate Issued
"""

import os
import json
import boto3
import logging
import requests
import time
import base64
import hashlib
import hmac
from datetime import datetime, timezone
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")

CERT_TABLE = os.environ["CERT_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
CERT_BUCKET = os.environ["CERT_BUCKET"]

# Pebble CA URL — retrieved from SSM Parameter Store at runtime
PEBBLE_URL = os.environ.get("PEBBLE_URL", "https://localhost:14000")


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


def get_pebble_url() -> str:
    """Fetch Pebble CA URL from SSM Parameter Store."""
    try:
        resp = ssm_client.get_parameter(Name="/csr/pebble-url")
        return resp["Parameter"]["Value"]
    except Exception:
        return PEBBLE_URL


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def acme_new_nonce(directory_url: str) -> str:
    resp = requests.head(f"{directory_url}/nonce-plz", verify=False, timeout=10)
    return resp.headers["Replay-Nonce"]


def acme_request_cert(pebble_url: str, csr_pem: bytes, domain: str) -> bytes:
    """
    Simplified ACME flow against Pebble (which auto-validates).
    Returns the signed certificate PEM.
    """
    # Pebble has PEBBLE_VA_ALWAYS_VALID=1 so we skip challenge proof
    dir_url = f"{pebble_url}/dir"
    directory = requests.get(dir_url, verify=False, timeout=10).json()

    # Generate ACME account key
    account_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Build JWK
    pub = account_key.public_key()
    pub_numbers = pub.public_numbers()
    jwk = {
        "kty": "RSA",
        "n": b64url(pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, "big")),
        "e": b64url(pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, "big")),
    }

    def sign_request(url, payload, nonce, kid=None):
        if payload is None:
            payload_b64 = ""
        else:
            payload_b64 = b64url(json.dumps(payload).encode())

        protected = {"alg": "RS256", "nonce": nonce, "url": url}
        if kid:
            protected["kid"] = kid
        else:
            protected["jwk"] = jwk

        protected_b64 = b64url(json.dumps(protected).encode())
        signing_input = f"{protected_b64}.{payload_b64}".encode()

        sig = account_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        return {
            "protected": protected_b64,
            "payload": payload_b64,
            "signature": b64url(sig),
        }

    # 1. New account
    nonce = acme_new_nonce(pebble_url)
    acct_resp = requests.post(
        directory["newAccount"],
        json=sign_request(directory["newAccount"], {"termsOfServiceAgreed": True}, nonce),
        headers={"Content-Type": "application/jose+json"},
        verify=False, timeout=10,
    )
    kid = acct_resp.headers.get("Location")

    # 2. New order
    nonce = acct_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))
    order_resp = requests.post(
        directory["newOrder"],
        json=sign_request(directory["newOrder"], {"identifiers": [{"type": "dns", "value": domain}]}, nonce, kid=kid),
        headers={"Content-Type": "application/jose+json"},
        verify=False, timeout=10,
    )
    order = order_resp.json()
    order_url = order_resp.headers.get("Location")

    # 3. Get authorization (Pebble auto-validates with PEBBLE_VA_ALWAYS_VALID)
    nonce = order_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))
    auth_url = order["authorizations"][0]
    auth_resp = requests.post(
        auth_url,
        json=sign_request(auth_url, None, nonce, kid=kid),
        headers={"Content-Type": "application/jose+json"},
        verify=False, timeout=10,
    )
    auth = auth_resp.json()

    # 4. Respond to HTTP-01 challenge (auto-validated by Pebble)
    nonce = auth_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))
    challenge = next(c for c in auth["challenges"] if c["type"] == "http-01")
    chall_resp = requests.post(
        challenge["url"],
        json=sign_request(challenge["url"], {}, nonce, kid=kid),
        headers={"Content-Type": "application/jose+json"},
        verify=False, timeout=10,
    )
    nonce = chall_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))

    # 5. Poll until order is ready
    for _ in range(10):
        time.sleep(1)
        poll_resp = requests.post(
            order_url,
            json=sign_request(order_url, None, nonce, kid=kid),
            headers={"Content-Type": "application/jose+json"},
            verify=False, timeout=10,
        )
        nonce = poll_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))
        order = poll_resp.json()
        if order["status"] in ("ready", "valid"):
            break

    # 6. Finalize — submit CSR
    csr_der = x509.load_pem_x509_csr(csr_pem).public_bytes(serialization.Encoding.DER)
    finalize_resp = requests.post(
        order["finalize"],
        json=sign_request(order["finalize"], {"csr": b64url(csr_der)}, nonce, kid=kid),
        headers={"Content-Type": "application/jose+json"},
        verify=False, timeout=10,
    )
    nonce = finalize_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))

    # 7. Poll until valid
    for _ in range(10):
        time.sleep(1)
        poll_resp = requests.post(
            order_url,
            json=sign_request(order_url, None, nonce, kid=kid),
            headers={"Content-Type": "application/jose+json"},
            verify=False, timeout=10,
        )
        nonce = poll_resp.headers.get("Replay-Nonce", acme_new_nonce(pebble_url))
        order = poll_resp.json()
        if order["status"] == "valid":
            break

    # 8. Download certificate
    cert_resp = requests.post(
        order["certificate"],
        json=sign_request(order["certificate"], None, nonce, kid=kid),
        headers={"Content-Type": "application/jose+json"},
        verify=False, timeout=10,
    )
    return cert_resp.content  # PEM chain


def handler(event, context):
    cert_id = event["cert_id"]
    domain = event.get("domain", "example.com")
    csr_s3_path = event.get("csr_s3_path")
    now = datetime.now(timezone.utc)

    logger.info(f"ACME client: requesting cert for {cert_id} ({domain})")

    # Load CSR from S3
    obj = s3_client.get_object(Bucket=CERT_BUCKET, Key=csr_s3_path)
    csr_pem = obj["Body"].read()

    pebble_url = get_pebble_url()
    cert_pem = acme_request_cert(pebble_url, csr_pem, domain)

    # Store signed cert in S3
    cert_s3_path = f"certs/{cert_id}/certificate.pem"
    s3_client.put_object(
        Bucket=CERT_BUCKET,
        Key=cert_s3_path,
        Body=cert_pem,
        ServerSideEncryption="AES256",
    )

    # Parse expiry from cert
    cert_obj = x509.load_pem_x509_certificate(cert_pem.split(b"-----END CERTIFICATE-----")[0] + b"-----END CERTIFICATE-----\n")
    new_expiry = cert_obj.not_valid_after_utc.strftime("%Y-%m-%d")

    # Update DynamoDB
    dynamodb.Table(CERT_TABLE).update_item(
        Key={"cert_id": cert_id},
        UpdateExpression="SET #s = :s, cert_issued_at = :ts, cert_s3_path = :cp, new_expiry_date = :exp",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":s": "Certificate Issued",
            ":ts": now.isoformat(),
            ":cp": cert_s3_path,
            ":exp": new_expiry,
        },
    )

    write_audit(cert_id, "CERTIFICATE_ISSUED", {
        "domain": domain,
        "cert_s3_path": cert_s3_path,
        "new_expiry_date": new_expiry,
        "new_state": "Certificate Issued",
        "ca": "Pebble (test CA)",
    })

    logger.info(f"Certificate issued for {cert_id}, expires {new_expiry}")
    return {
        **event,
        "state": "Certificate Issued",
        "cert_s3_path": cert_s3_path,
        "new_expiry_date": new_expiry,
        "cert_issued_at": now.isoformat(),
    }
