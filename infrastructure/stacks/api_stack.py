import os
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    CfnOutput,
)
from constructs import Construct

LAMBDAS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "lambdas")


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cert_table: dynamodb.Table,
        audit_table: dynamodb.Table,
        agencies_table: dynamodb.Table,
        lambda_role: iam.Role,
        state_machine: sfn.StateMachine,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Dashboard API Lambda
        self.dashboard_api_fn = _lambda.Function(
            self, "DashboardApi",
            function_name="csr-dashboard-api",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(os.path.join(LAMBDAS_DIR, "dashboard_api")),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "CERT_TABLE": cert_table.table_name,
                "AUDIT_TABLE": audit_table.table_name,
                "AGENCIES_TABLE": agencies_table.table_name,
                "STATE_MACHINE_ARN": state_machine.state_machine_arn,
            },
        )

        # API Gateway REST API
        self.api = apigw.RestApi(
            self, "CsrApi",
            rest_api_name="csr-api",
            description="CSR Certificate Lifecycle API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        integration = apigw.LambdaIntegration(self.dashboard_api_fn)

        # /certs
        certs = self.api.root.add_resource("certs")
        certs.add_method("GET", integration)
        certs.add_method("POST", integration)

        cert_item = certs.add_resource("{cert_id}")
        cert_item.add_method("GET", integration)
        cert_item.add_method("PUT", integration)

        # /certs/{cert_id}/trigger
        trigger = cert_item.add_resource("trigger")
        trigger.add_method("POST", integration)

        # /audit
        audit = self.api.root.add_resource("audit")
        audit.add_method("GET", integration)

        audit_cert = audit.add_resource("{cert_id}")
        audit_cert.add_method("GET", integration)

        # /agencies
        agencies = self.api.root.add_resource("agencies")
        agencies.add_method("GET", integration)

        # /governance/approve
        governance = self.api.root.add_resource("governance")
        approve = governance.add_resource("approve")
        approve.add_method("POST", integration)

        # /reports
        reports = self.api.root.add_resource("reports")
        reports.add_method("GET", integration)
        reports.add_method("POST", integration)

        # /demo/run
        demo = self.api.root.add_resource("demo")
        demo_run = demo.add_resource("run")
        demo_run.add_method("POST", integration)

        CfnOutput(self, "ApiUrl", value=self.api.url)
