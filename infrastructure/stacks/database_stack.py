from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct


class DatabaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Certificate inventory table
        self.cert_table = dynamodb.Table(
            self, "CertInventory",
            table_name="csr-cert-inventory",
            partition_key=dynamodb.Attribute(
                name="cert_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )
        # GSI: query by agency
        self.cert_table.add_global_secondary_index(
            index_name="agency-index",
            partition_key=dynamodb.Attribute(
                name="agency_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="expiry_date",
                type=dynamodb.AttributeType.STRING,
            ),
        )
        # GSI: query by state
        self.cert_table.add_global_secondary_index(
            index_name="state-index",
            partition_key=dynamodb.Attribute(
                name="state",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="expiry_date",
                type=dynamodb.AttributeType.STRING,
            ),
        )

        # Append-only audit log table
        self.audit_table = dynamodb.Table(
            self, "AuditLog",
            table_name="csr-audit-log",
            partition_key=dynamodb.Attribute(
                name="cert_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Agencies table
        self.agencies_table = dynamodb.Table(
            self, "Agencies",
            table_name="csr-agencies",
            partition_key=dynamodb.Attribute(
                name="agency_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
