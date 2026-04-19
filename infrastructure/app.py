#!/usr/bin/env python3
import aws_cdk as cdk
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from stacks.database_stack import DatabaseStack
from stacks.storage_stack import StorageStack
from stacks.iam_stack import IamStack
from stacks.workflow_stack import WorkflowStack
from stacks.compute_stack import ComputeStack
from stacks.api_stack import ApiStack

app = cdk.App()

env = cdk.Environment(
    region=app.node.try_get_context("region") or "us-east-1"
)

# --- Layer 1: stateless resources ---
db_stack = DatabaseStack(app, "CsrDatabaseStack", env=env)
storage_stack = StorageStack(app, "CsrStorageStack", env=env)

# --- Layer 2: IAM (depends on resources) ---
iam_stack = IamStack(
    app, "CsrIamStack",
    cert_table=db_stack.cert_table,
    audit_table=db_stack.audit_table,
    agencies_table=db_stack.agencies_table,
    cert_bucket=storage_stack.cert_bucket,
    reports_bucket=storage_stack.reports_bucket,
    env=env,
)

# --- Layer 3: workflow (Lambdas + Step Functions + EventBridge + SNS) ---
workflow_stack = WorkflowStack(
    app, "CsrWorkflowStack",
    cert_table=db_stack.cert_table,
    audit_table=db_stack.audit_table,
    agencies_table=db_stack.agencies_table,
    cert_bucket=storage_stack.cert_bucket,
    reports_bucket=storage_stack.reports_bucket,
    lambda_role=iam_stack.lambda_role,
    env=env,
)

# --- Layer 4: EC2 for Pebble CA + Nginx ---
compute_stack = ComputeStack(app, "CsrComputeStack", env=env)

# --- Layer 5: API Gateway + dashboard Lambda ---
api_stack = ApiStack(
    app, "CsrApiStack",
    cert_table=db_stack.cert_table,
    audit_table=db_stack.audit_table,
    agencies_table=db_stack.agencies_table,
    lambda_role=iam_stack.lambda_role,
    state_machine=workflow_stack.state_machine,
    env=env,
)

cdk.Tags.of(app).add("Project", "CSR-Automated-ITS")
cdk.Tags.of(app).add("Environment", "demo")

app.synth()
