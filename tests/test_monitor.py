#!/usr/bin/env python3
"""
Unit test: Monitor Lambda
Tests that the monitor correctly identifies expiring certs and starts workflows.
"""
import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

# Make lambdas importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "monitor"))

os.environ["CERT_TABLE"] = "csr-cert-inventory"
os.environ["AUDIT_TABLE"] = "csr-audit-log"
os.environ["AGENCIES_TABLE"] = "csr-agencies"
os.environ["CERT_BUCKET"] = "csr-cert-store-test"
os.environ["REPORTS_BUCKET"] = "csr-reports-test"
os.environ["ALERT_TOPIC_ARN"] = "arn:aws:sns:us-east-1:000000000000:csr-alerts"
os.environ["GOVERNANCE_TOPIC_ARN"] = "arn:aws:sns:us-east-1:000000000000:csr-governance"
os.environ["STATE_MACHINE_ARN"] = "arn:aws:states:us-east-1:000000000000:stateMachine:csr-cert-lifecycle"


class TestMonitor(unittest.TestCase):

    @patch("handler.sfn_client")
    @patch("handler.dynamodb")
    def test_finds_expiring_certs_and_starts_workflows(self, mock_dynamo, mock_sfn):
        from handler import handler

        now = datetime.now(timezone.utc)
        expiring_cert = {
            "cert_id": "cert-test-001",
            "domain": "test.ms.gov",
            "agency_id": "agency-its",
            "state": "Active",
            "expiry_date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
        }

        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": [expiring_cert]}
        mock_table.update_item.return_value = {}
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:::execution/test"
        }

        result = handler({}, None)

        self.assertEqual(result["triggered"], 1)
        self.assertIn("cert-test-001", result["cert_ids"])
        mock_sfn.start_execution.assert_called_once()

        call_kwargs = mock_sfn.start_execution.call_args[1]
        input_data = json.loads(call_kwargs["input"])
        self.assertEqual(input_data["cert_id"], "cert-test-001")
        self.assertEqual(input_data["domain"], "test.ms.gov")

    @patch("handler.sfn_client")
    @patch("handler.dynamodb")
    def test_skips_non_active_certs(self, mock_dynamo, mock_sfn):
        from handler import handler

        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": []}

        result = handler({}, None)

        self.assertEqual(result["triggered"], 0)
        mock_sfn.start_execution.assert_not_called()

    @patch("handler.sfn_client")
    @patch("handler.dynamodb")
    def test_handles_concurrent_modification(self, mock_dynamo, mock_sfn):
        """If a cert was already processed (ConditionalCheckFailedException), skip it."""
        from handler import handler
        from botocore.exceptions import ClientError

        now = datetime.now(timezone.utc)
        cert = {
            "cert_id": "cert-test-002",
            "domain": "portal.ms.gov",
            "agency_id": "agency-its",
            "state": "Active",
            "expiry_date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
        }

        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": [cert]}

        error_response = {"Error": {"Code": "ConditionalCheckFailedException"}}
        mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

        # Wire the meta client exception
        mock_dynamo.meta = MagicMock()
        mock_dynamo.meta.client.exceptions.ConditionalCheckFailedException = ClientError

        result = handler({}, None)
        self.assertEqual(result["triggered"], 0)


class TestCSRGenerator(unittest.TestCase):

    @patch("handler.s3_client")
    @patch("handler.dynamodb")
    def test_generates_valid_csr(self, mock_dynamo, mock_s3):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "csr_generator"))
        import handler as csr_handler

        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table
        mock_s3.put_object.return_value = {}

        event = {
            "cert_id": "cert-test-001",
            "domain": "test.ms.gov",
            "agency_id": "agency-its",
        }

        result = csr_handler.handler(event, None)

        self.assertEqual(result["state"], "CSR Generated")
        self.assertIn("key_s3_path", result)
        self.assertIn("csr_s3_path", result)
        self.assertTrue(result["key_s3_path"].startswith("certs/cert-test-001/"))

        # Verify S3 was called with private key
        calls = mock_s3.put_object.call_args_list
        self.assertEqual(len(calls), 2)  # key + CSR


if __name__ == "__main__":
    unittest.main(verbosity=2)
