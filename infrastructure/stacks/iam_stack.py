from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from constructs import Construct


class IamStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cert_table: dynamodb.Table,
        audit_table: dynamodb.Table,
        agencies_table: dynamodb.Table,
        cert_bucket: s3.Bucket,
        reports_bucket: s3.Bucket,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            role_name="csr-lambda-execution-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # DynamoDB permissions
        cert_table.grant_read_write_data(self.lambda_role)
        audit_table.grant_read_write_data(self.lambda_role)
        agencies_table.grant_read_write_data(self.lambda_role)

        # S3 permissions
        cert_bucket.grant_read_write(self.lambda_role)
        reports_bucket.grant_read_write(self.lambda_role)

        # Step Functions — start executions + send task success/failure
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "states:StartExecution",
                    "states:SendTaskSuccess",
                    "states:SendTaskFailure",
                    "states:DescribeExecution",
                    "states:ListExecutions",
                ],
                resources=["*"],
            )
        )

        # SNS — publish alerts
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sns:Publish"],
                resources=["*"],
            )
        )

        # SES — send governance approval emails
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # SSM — run commands on EC2 (deploy cert to Nginx)
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ssm:SendCommand",
                    "ssm:GetCommandInvocation",
                    "ssm:DescribeInstanceInformation",
                ],
                resources=["*"],
            )
        )

        # Bedrock — Claude AI for exception analysis + reports
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["*"],
            )
        )

        # EventBridge — for governance callback URL
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["events:PutEvents"],
                resources=["*"],
            )
        )

        # API Gateway management (for WebSocket push — optional)
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=["*"],
            )
        )
