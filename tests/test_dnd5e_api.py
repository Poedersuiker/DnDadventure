import unittest
from unittest.mock import patch, MagicMock
import requests
import json

# Assuming app.dnd5e_api is discoverable in PYTHONPATH
from app.dnd5e_api import (
    get_resources, get_resource_details, _make_request, BASE_URL,
    get_all_classes, get_class_details, get_class_level_details # Added new functions
)

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

    # --- Tests for get_all_classes ---
    @patch('app.dnd5e_api._make_request')
    def test_get_all_classes_success(self, mock_make_request):
        """Test get_all_classes successfully fetches and extracts class list."""
        expected_classes = [{'index': 'bard', 'name': 'Bard', 'url': '/api/classes/bard'}]
        mock_make_request.return_value = {'count': 1, 'results': expected_classes}

        result = get_all_classes()

        mock_make_request.assert_called_once_with("/classes")
        self.assertEqual(result, expected_classes)

    @patch('app.dnd5e_api._make_request')
    def test_get_all_classes_missing_results(self, mock_make_request):
        """Test get_all_classes returns empty list if 'results' key is missing."""
        mock_make_request.return_value = {'count': 0} # No 'results' key

        result = get_all_classes()

        mock_make_request.assert_called_once_with("/classes")
        self.assertEqual(result, [])

    @patch('app.dnd5e_api._make_request')
    def test_get_all_classes_api_error(self, mock_make_request):
        """Test get_all_classes re-raises RequestException from _make_request."""
        mock_make_request.side_effect = requests.exceptions.RequestException("API down")

        with self.assertRaises(requests.exceptions.RequestException):
            get_all_classes()
        mock_make_request.assert_called_once_with("/classes")

    @patch('app.dnd5e_api._make_request')
    def test_get_all_classes_json_error(self, mock_make_request):
        """Test get_all_classes re-raises JSONDecodeError from _make_request."""
        mock_make_request.side_effect = json.JSONDecodeError("Bad JSON", "doc", 0)

        with self.assertRaises(json.JSONDecodeError):
            get_all_classes()
        mock_make_request.assert_called_once_with("/classes")

    # --- Tests for get_class_details ---
    @patch('app.dnd5e_api._make_request')
    def test_get_class_details_success(self, mock_make_request):
        """Test get_class_details calls _make_request with correct endpoint and returns data."""
        class_index = "wizard"
        expected_details = {"index": "wizard", "name": "Wizard", "hit_die": 6}
        mock_make_request.return_value = expected_details

        result = get_class_details(class_index)

        mock_make_request.assert_called_once_with(f"/classes/{class_index}")
        self.assertEqual(result, expected_details)

    @patch('app.dnd5e_api._make_request')
    def test_get_class_details_api_error(self, mock_make_request):
        """Test get_class_details re-raises RequestException."""
        class_index = "wizard"
        mock_make_request.side_effect = requests.exceptions.RequestException("API error")

        with self.assertRaises(requests.exceptions.RequestException):
            get_class_details(class_index)
        mock_make_request.assert_called_once_with(f"/classes/{class_index}")

    @patch('app.dnd5e_api._make_request')
    def test_get_class_details_json_error(self, mock_make_request):
        """Test get_class_details re-raises JSONDecodeError."""
        class_index = "wizard"
        mock_make_request.side_effect = json.JSONDecodeError("Bad JSON", "doc", 0)

        with self.assertRaises(json.JSONDecodeError):
            get_class_details(class_index)
        mock_make_request.assert_called_once_with(f"/classes/{class_index}")

    # --- Tests for get_class_level_details ---
    @patch('app.dnd5e_api._make_request')
    def test_get_class_level_details_success(self, mock_make_request):
        """Test get_class_level_details calls _make_request with correct endpoint."""
        class_index = "bard"
        level = 1
        expected_level_details = {"level": 1, "prof_bonus": 2, "features": [{"name": "Spellcasting"}, {"name": "Bardic Inspiration (d6)"}]}
        mock_make_request.return_value = expected_level_details

        result = get_class_level_details(class_index, level)

        mock_make_request.assert_called_once_with(f"/classes/{class_index}/levels/{level}")
        self.assertEqual(result, expected_level_details)

    @patch('app.dnd5e_api._make_request')
    def test_get_class_level_details_api_error(self, mock_make_request):
        """Test get_class_level_details re-raises RequestException."""
        class_index = "bard"
        level = 1
        mock_make_request.side_effect = requests.exceptions.RequestException("API error")

        with self.assertRaises(requests.exceptions.RequestException):
            get_class_level_details(class_index, level)
        mock_make_request.assert_called_once_with(f"/classes/{class_index}/levels/{level}")

    @patch('app.dnd5e_api._make_request')
    def test_get_class_level_details_json_error(self, mock_make_request):
        """Test get_class_level_details re-raises JSONDecodeError."""
        class_index = "bard"
        level = 1
        mock_make_request.side_effect = json.JSONDecodeError("Bad JSON", "doc", 0)

        with self.assertRaises(json.JSONDecodeError):
            get_class_level_details(class_index, level)
        mock_make_request.assert_called_once_with(f"/classes/{class_index}/levels/{level}")

if __name__ == '__main__':
    unittest.main()
