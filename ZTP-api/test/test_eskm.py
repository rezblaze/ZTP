import asyncio
import validators
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.eskm import eskm_main


class TestESKMMain(unittest.TestCase):
    @patch("app.modules.eskm.is_valid_hostname_or_ip")
    @patch("app.modules.eskm.create_requests_retry_session")
    @patch("app.modules.eskm.get_gen")
    @patch("app.modules.eskm.get_infra_data")
    @patch("app.modules.eskm.create_payload")
    @patch("app.modules.eskm.get_eskm_config")
    async def test_eskm_main_success(
        self,
        mock_get_eskm_config,
        mock_create_payload,
        mock_get_infra_data,
        mock_get_gen,
        mock_create_requests_retry_session,
        mock_is_valid_hostname_or_ip,
    ):
        mock_is_valid_hostname_or_ip.return_value = "lab-dc1-r1-s17-lom.example.com"
        mock_create_requests_retry_session.return_value = MagicMock()
        mock_get_gen.return_value = "Gen10"
        mock_get_infra_data.return_value = {"DC": "SITE_B"}
        mock_create_payload.return_value = {"PrimaryKeyServerAddress": "10.0.0.1", "PrimaryKeyServerPort": 9000}
        mock_get_eskm_config.return_value = {"PrimaryKeyServerAddress": "10.0.0.1", "PrimaryKeyServerPort": 9000}

        result = await eskm_main("lab-dc1-r1-s17-lom.example.com", "admin", "password")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.status_detail, "No differences found, configuration is up to date.")
        self.assertEqual(result.host, "lab-dc1-r1-s17-lom.example.com")
        self.assertEqual(result.requestor, "admin")

    @patch("app.modules.eskm.is_valid_hostname_or_ip")
    @patch("app.modules.eskm.create_requests_retry_session")
    @patch("app.modules.eskm.get_gen")
    @patch("app.modules.eskm.get_infra_data")
    @patch("app.modules.eskm.create_payload")
    @patch("app.modules.eskm.get_eskm_config")
    async def test_eskm_main_error(
        self,
        mock_get_eskm_config,
        mock_create_payload,
        mock_get_infra_data,
        mock_get_gen,
        mock_create_requests_retry_session,
        mock_is_valid_hostname_or_ip,
    ):
        mock_is_valid_hostname_or_ip.return_value = "lab-dc1-r1-s17-lom.example.com"
        mock_create_requests_retry_session.return_value = MagicMock()
        mock_get_gen.return_value = "Gen10"
        mock_get_infra_data.return_value = {"DC": "SITE_B"}
        mock_create_payload.return_value = {"PrimaryKeyServerAddress": "10.0.0.1", "PrimaryKeyServerPort": 9000}
        mock_get_eskm_config.return_value = {"PrimaryKeyServerAddress": "10.0.0.2", "PrimaryKeyServerPort": 9000}

        result = await eskm_main("lab-dc1-r1-s17-lom.example.com", "admin", "password")

        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.status_detail, "Differences found, configuration is not up to date.")
        self.assertEqual(result.host, "lab-dc1-r1-s17-lom.example.com")
        self.assertEqual(result.requestor, "admin")


if __name__ == "__main__":
    unittest.main()