# CSR Automated Certificate Lifecycle — Mississippi ITS/MDA

Automated, AI-powered SSL certificate lifecycle management system for Mississippi state agencies.

## Team
- **Haad Imran** — Backend & automation lead
- **Riad Benyamna** — Solutions architect & AI lead
- **Abdelrahman Teima** — Cryptography & systems lead

## What It Does
Automatically renews SSL certificates through all 8 ITS-defined lifecycle states with zero manual intervention, AI-powered exception analysis, and an immutable audit trail.

## Certificate Lifecycle States
```
Active → Expiration Detected → Renewal Initiated → CSR Generated
→ Certificate Issued → Certificate Deployed → Certificate Validated → Renewal Closed
```

## Stack
- **AWS Lambda** — serverless automation per lifecycle state
- **AWS Step Functions** — 8-state workflow orchestration
- **AWS DynamoDB** — certificate inventory + append-only audit log
- **AWS EventBridge** — daily expiration monitoring
- **AWS Bedrock (Claude)** — AI exception analysis + report generation
- **AWS EC2** — Pebble test CA + Nginx deployment target
- **React + API Gateway** — real-time dashboard

## Project Structure
```
infrastructure/   — AWS CDK stacks
lambdas/          — one Lambda per lifecycle state
dashboard/        — React frontend + API
pebble/           — Test CA setup
policies/         — YAML security policies
seed/             — Synthetic test data
tests/            — End-to-end tests
```
