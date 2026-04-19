#!/usr/bin/env python3
"""
Seed script: populates DynamoDB with 10 fake certificates across 3 agencies.
Run: python3 seed/seed_data.py [--region us-east-1] [--reset]
"""

import argparse
import json
import os
import sys
import boto3
from datetime import datetime, timezone, timedelta
import random

CERT_TABLE = "csr-cert-inventory"
AUDIT_TABLE = "csr-audit-log"
AGENCIES_TABLE = "csr-agencies"

AGENCIES = [
    {
        "agency_id": "agency-mdot",
        "name": "Mississippi Department of Transportation",
        "short_name": "MDOT",
        "contact_email": "webmaster@mdot.ms.gov",
        "officer_email": "security@mdot.ms.gov",
    },
    {
        "agency_id": "agency-mda",
        "name": "Mississippi Development Authority",
        "short_name": "MDA",
        "contact_email": "webmaster@mda.ms.gov",
        "officer_email": "security@mda.ms.gov",
    },
    {
        "agency_id": "agency-its",
        "name": "Mississippi ITS",
        "short_name": "ITS",
        "contact_email": "webmaster@its.ms.gov",
        "officer_email": "security@its.ms.gov",
    },
]

CERTS = [
    # MDOT — 4 certs
    {"cert_id": "cert-mdot-001", "domain": "www.mdot.ms.gov",          "agency_id": "agency-mdot", "expiry_days": 5},
    {"cert_id": "cert-mdot-002", "domain": "permits.mdot.ms.gov",      "agency_id": "agency-mdot", "expiry_days": 12},
    {"cert_id": "cert-mdot-003", "domain": "maps.mdot.ms.gov",         "agency_id": "agency-mdot", "expiry_days": 38},
    {"cert_id": "cert-mdot-004", "domain": "construction.mdot.ms.gov", "agency_id": "agency-mdot", "expiry_days": 90},
    # MDA — 3 certs
    {"cert_id": "cert-mda-001", "domain": "www.mda.ms.gov",            "agency_id": "agency-mda",  "expiry_days": 8},
    {"cert_id": "cert-mda-002", "domain": "invest.mda.ms.gov",         "agency_id": "agency-mda",  "expiry_days": 45},
    {"cert_id": "cert-mda-003", "domain": "grants.mda.ms.gov",         "agency_id": "agency-mda",  "expiry_days": 120},
    # ITS — 3 certs
    {"cert_id": "cert-its-001", "domain": "portal.its.ms.gov",         "agency_id": "agency-its",  "expiry_days": 3},
    {"cert_id": "cert-its-002", "domain": "helpdesk.its.ms.gov",       "agency_id": "agency-its",  "expiry_days": 25},
    {"cert_id": "cert-its-003", "domain": "api.its.ms.gov",            "agency_id": "agency-its",  "expiry_days": 200},
]


def seed(region: str, reset: bool = False):
    dynamodb = boto3.resource("dynamodb", region_name=region)
    now = datetime.now(timezone.utc)

    print(f"Seeding DynamoDB in region {region}...")

    # ── Agencies ──────────────────────────────────────────────────────────
    agencies_table = dynamodb.Table(AGENCIES_TABLE)
    for agency in AGENCIES:
        agencies_table.put_item(Item=agency)
        print(f"  ✓ Agency: {agency['name']}")

    # ── Certificates ──────────────────────────────────────────────────────
    cert_table = dynamodb.Table(CERT_TABLE)
    audit_table = dynamodb.Table(AUDIT_TABLE)

    for cert in CERTS:
        expiry = (now + timedelta(days=cert["expiry_days"])).strftime("%Y-%m-%d")
        issued = (now - timedelta(days=47 - cert["expiry_days"])).strftime("%Y-%m-%d")

        item = {
            "cert_id": cert["cert_id"],
            "domain": cert["domain"],
            "agency_id": cert["agency_id"],
            "state": "Active",
            "expiry_date": expiry,
            "issued_date": issued,
            "renewals_count": random.randint(0, 5),
            "last_renewed_at": (now - timedelta(days=47)).isoformat(),
            "created_at": (now - timedelta(days=180)).isoformat(),
            "demo_cert": True,
        }

        cert_table.put_item(Item=item)

        # Seed an initial audit entry
        audit_table.put_item(Item={
            "cert_id": cert["cert_id"],
            "timestamp": (now - timedelta(days=180)).isoformat(),
            "action": "CERT_CREATED",
            "details": {
                "domain": cert["domain"],
                "expiry_date": expiry,
                "source": "seed_script",
            },
            "actor": "seed-script",
        })

        days_left = cert["expiry_days"]
        status = "🔴" if days_left <= 7 else "🟡" if days_left <= 30 else "🟢"
        print(f"  {status} {cert['domain']:<40} expires in {days_left:>3}d  ({expiry})")

    print(f"\n✅ Seeded {len(AGENCIES)} agencies and {len(CERTS)} certificates")
    print(f"   Certs expiring within 47 days: {sum(1 for c in CERTS if c['expiry_days'] <= 47)}")
    print(f"   These will be picked up by the monitor on next run.\n")


def main():
    parser = argparse.ArgumentParser(description="Seed CSR demo data")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--reset", action="store_true", help="Delete all existing items first")
    args = parser.parse_args()
    seed(args.region, args.reset)


if __name__ == "__main__":
    main()
