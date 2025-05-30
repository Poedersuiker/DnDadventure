import unittest
from unittest.mock import patch, MagicMock
import requests
import json

# Assuming app.dnd5e_api is discoverable in PYTHONPATH
from app.dnd5e_api import get_resources, get_resource_details, _make_request, BASE_URL

class TestDnd5eApi(unittest.TestCase):

    @patch('app.dnd5e_api.requests.get')
    def test_make_request_success(self, mock_get):
        """Test _make_request successfully fetches and returns JSON data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        expected_data = {"key": "value"}
        mock_response.json.return_value = expected_data
        mock_get.return_value = mock_response

        endpoint = "/test_endpoint"
        result = _make_request(endpoint)

        mock_get.assert_called_once_with(BASE_URL + endpoint)
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(result, expected_data)

    @patch('app.dnd5e_api.requests.get')
    def test_make_request_http_error(self, mock_get):
        """Test _make_request raises HTTPError for non-200 status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_get.return_value = mock_response

        endpoint = "/test_error"
        with self.assertRaises(requests.exceptions.HTTPError):
            _make_request(endpoint)
        mock_get.assert_called_once_with(BASE_URL + endpoint)
        mock_response.raise_for_status.assert_called_once()

    @patch('app.dnd5e_api.requests.get')
    def test_make_request_request_exception(self, mock_get):
        """Test _make_request raises RequestException for network issues."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        endpoint = "/test_request_exception"
        with self.assertRaises(requests.exceptions.RequestException):
            _make_request(endpoint)
        mock_get.assert_called_once_with(BASE_URL + endpoint)

    @patch('app.dnd5e_api.requests.get')
    def test_make_request_json_decode_error(self, mock_get):
        """Test _make_request raises JSONDecodeError for invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_get.return_value = mock_response

        endpoint = "/test_json_error"
        with self.assertRaises(json.JSONDecodeError):
            _make_request(endpoint)
        mock_get.assert_called_once_with(BASE_URL + endpoint)
        mock_response.raise_for_status.assert_called_once()

    @patch('app.dnd5e_api._make_request')
    def test_get_resources(self, mock_make_request):
        """Test get_resources calls _make_request with '/' and returns its result."""
        expected_result = {"spells": "/api/spells", "monsters": "/api/monsters"}
        mock_make_request.return_value = expected_result

        result = get_resources()

        mock_make_request.assert_called_once_with("/")
        self.assertEqual(result, expected_result)

    @patch('app.dnd5e_api._make_request')
    def test_get_resource_details(self, mock_make_request):
        """Test get_resource_details calls _make_request with the correct endpoint."""
        resource_type = "spells"
        resource_index = "fireball"
        expected_endpoint = f"/{resource_type}/{resource_index}"
        expected_result = {"name": "Fireball", "desc": "A fiery explosion..."}
        mock_make_request.return_value = expected_result

        result = get_resource_details(resource_type, resource_index)

        mock_make_request.assert_called_once_with(expected_endpoint)
        self.assertEqual(result, expected_result)

if __name__ == '__main__':
    unittest.main()
