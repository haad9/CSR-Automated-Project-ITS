import json
import os
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_events as events,
    aws_events_targets as targets,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct

LAMBDAS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "lambdas")


def make_lambda(scope, name: str, handler_module: str, role: iam.Role, env_vars: dict) -> _lambda.Function:
    return _lambda.Function(
        scope, name,
        function_name=f"csr-{name.lower().replace('_', '-')}",
        runtime=_lambda.Runtime.PYTHON_3_12,
        handler=f"{handler_module}.handler",
        code=_lambda.Code.from_asset(os.path.join(LAMBDAS_DIR, handler_module)),
        role=role,
        timeout=Duration.seconds(300),
        memory_size=256,
        environment=env_vars,
    )


class WorkflowStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cert_table: dynamodb.Table,
        audit_table: dynamodb.Table,
        agencies_table: dynamodb.Table,
        cert_bucket: s3.Bucket,
        reports_bucket: s3.Bucket,
        lambda_role: iam.Role,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # --- SNS Topics ---
        self.alert_topic = sns.Topic(self, "AlertTopic", topic_name="csr-alerts")
        self.governance_topic = sns.Topic(self, "GovernanceTopic", topic_name="csr-governance")

        base_env = {
            "CERT_TABLE": cert_table.table_name,
            "AUDIT_TABLE": audit_table.table_name,
            "AGENCIES_TABLE": agencies_table.table_name,
            "CERT_BUCKET": cert_bucket.bucket_name,
            "REPORTS_BUCKET": reports_bucket.bucket_name,
            "ALERT_TOPIC_ARN": self.alert_topic.topic_arn,
            "GOVERNANCE_TOPIC_ARN": self.governance_topic.topic_arn,
        }

        # --- Lambda Functions ---
        self.renewal_initiator_fn = make_lambda(self, "RenewalInitiator", "renewal_initiator", lambda_role, base_env)
        self.csr_generator_fn = make_lambda(self, "CsrGenerator", "csr_generator", lambda_role, base_env)
        self.acme_client_fn = make_lambda(self, "AcmeClient", "acme_client", lambda_role, base_env)
        self.governance_gate_fn = make_lambda(self, "GovernanceGate", "governance_gate", lambda_role, base_env)
        self.deployer_fn = make_lambda(self, "Deployer", "deployer", lambda_role, base_env)
        self.validator_fn = make_lambda(self, "Validator", "validator", lambda_role, base_env)
        self.renewal_closer_fn = make_lambda(self, "RenewalCloser", "renewal_closer", lambda_role, base_env)
        self.exception_handler_fn = make_lambda(self, "ExceptionHandler", "exception_handler", lambda_role, base_env)
        self.report_generator_fn = make_lambda(self, "ReportGenerator", "report_generator", lambda_role, base_env)
        self.audit_writer_fn = make_lambda(self, "AuditWriter", "audit_writer", lambda_role, base_env)
        self.monitor_fn = make_lambda(self, "Monitor", "monitor", lambda_role, {
            **base_env,
            "STATE_MACHINE_ARN": "",  # injected after state machine is created via env update
        })

        # --- Step Functions States ---
        # Single exception handler state (shared catch target)
        exception_task = sfn_tasks.LambdaInvoke(
            self, "HandleException",
            lambda_function=self.exception_handler_fn,
            output_path="$.Payload",
        )

        def with_catch(state):
            state.add_catch(exception_task, errors=["States.ALL"], result_path="$.error_info")
            return state

        step_renewal_initiated = with_catch(sfn_tasks.LambdaInvoke(
            self, "StateRenewalInitiated",
            lambda_function=self.renewal_initiator_fn,
            output_path="$.Payload",
        ))

        step_csr_generated = with_catch(sfn_tasks.LambdaInvoke(
            self, "StateCSRGenerated",
            lambda_function=self.csr_generator_fn,
            output_path="$.Payload",
        ))

        step_cert_issued = with_catch(sfn_tasks.LambdaInvoke(
            self, "StateCertificateIssued",
            lambda_function=self.acme_client_fn,
            output_path="$.Payload",
        ))

        # Governance gate uses waitForTaskToken pattern
        step_governance = with_catch(sfn_tasks.LambdaInvoke(
            self, "StateGovernanceGate",
            lambda_function=self.governance_gate_fn,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object({
                "task_token": sfn.JsonPath.task_token,
                "input": sfn.JsonPath.entire_payload,
            }),
            timeout=Duration.hours(24),
        ))

        step_cert_deployed = with_catch(sfn_tasks.LambdaInvoke(
            self, "StateCertificateDeployed",
            lambda_function=self.deployer_fn,
            output_path="$.Payload",
        ))

        step_cert_validated = with_catch(sfn_tasks.LambdaInvoke(
            self, "StateCertificateValidated",
            lambda_function=self.validator_fn,
            output_path="$.Payload",
        ))

        step_renewal_closed = sfn_tasks.LambdaInvoke(
            self, "StateRenewalClosed",
            lambda_function=self.renewal_closer_fn,
            output_path="$.Payload",
        )

        # --- Chain ---
        definition = (
            step_renewal_initiated
            .next(step_csr_generated)
            .next(step_cert_issued)
            .next(step_governance)
            .next(step_cert_deployed)
            .next(step_cert_validated)
            .next(step_renewal_closed)
        )

        self.state_machine = sfn.StateMachine(
            self, "CertLifecycleMachine",
            state_machine_name="csr-cert-lifecycle",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.hours(26),
        )

        # Update monitor env with real state machine ARN
        self.monitor_fn.add_environment("STATE_MACHINE_ARN", self.state_machine.state_machine_arn)

        # --- EventBridge: daily expiry scan at 6 AM UTC ---
        events.Rule(
            self, "DailyMonitorRule",
            rule_name="csr-daily-monitor",
            schedule=events.Schedule.cron(minute="0", hour="6"),
            targets=[targets.LambdaFunction(self.monitor_fn)],
        )

        # Outputs
        CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)
        CfnOutput(self, "AlertTopicArn", value=self.alert_topic.topic_arn)
        CfnOutput(self, "GovernanceTopicArn", value=self.governance_topic.topic_arn)
