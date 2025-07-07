import os
import unittest
from unittest.mock import patch, MagicMock

import sys
import os

# Ensure the project root is in PYTHONPATH for `from app import ...`
# When running `python -m unittest tests.test_app` from the project root,
# the project root is usually automatically part of sys.path.
# Explicitly adding it can help in some environments or if run differently.
# os.path.dirname(__file__) is /path/to/project/tests
# os.path.join(os.path.dirname(__file__), '..') is /path/to/project
# This adds the project root directory to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import requests for mocking exceptions
import requests

# It's important to configure the app for testing BEFORE importing it if it initializes extensions at import time.
# However, our app.py initializes extensions (like LoginManager) at the module level.
# This makes it tricky. A better approach is an app factory pattern.
# For now, we will try to work with the existing structure.

# Apply test configurations globally before app import for some settings if possible,
# or ensure they are applied before the first request.
# This is a common challenge with Flask app testing without a factory.

from app import app, User # login_manager is already configured in app.py
from flask import current_app # For new tests

# Apply test configurations. This should ideally be done before the app is fully "used".
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing forms if any
app.config['SECRET_KEY'] = 'test_secret_key_for_unittest' # Ensure a consistent secret key for session for tests
app.config['SERVER_NAME'] = 'localhost.test' # Required for url_for outside of request context in some cases
app.config['LOGIN_DISABLED'] = False # Explicitly enable login for tests

# Override sensitive or environment-specific configs for tests
# Ensure these are applied before any test client makes requests.
app.config['GOOGLE_CLIENT_ID'] = 'TEST_CLIENT_ID_FOR_UNITTEST'
app.config['GOOGLE_CLIENT_SECRET'] = 'TEST_CLIENT_SECRET_FOR_UNITTEST'
app.config['ADMIN_EMAIL'] = 'test_admin_for_unittest@example.com'
app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost.test/auth/google/authorized' # Test specific redirect URI with new path
# The dummy config.py created by app.py might overwrite these if not careful.
# It's better if tests manage their config explicitly.

class FeatureTestCase(unittest.TestCase): # Renamed class

    def setUp(self):
        # The app is already configured with TESTING = True etc. from above.
        # Create a new test client for each test.
        self.client = app.test_client()
        self.app_context = app.app_context() # Create an app context
        self.app_context.push() # Push it to make it active

        # Create a dummy user for login simulation
        self.test_user_id = '12345'
        self.test_user_name = 'Test User'
        self.test_user_email = 'test@example.com'
        self.user_data = {'id': self.test_user_id, 'name': self.test_user_name, 'email': self.test_user_email}

    def tearDown(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        self.app_context.pop() # Pop the app context

    # Helper to simulate login
    def _simulate_login(self):
        with self.client.session_transaction() as sess:
            sess['user_data'] = self.user_data
            sess['_user_id'] = self.test_user_id
            sess['_fresh'] = True
            # No need for a special login route if User.get loads from session correctly

    def test_01_index_redirects_to_login_page_when_not_logged_in(self):
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login_page' in response.location)

    def test_02_login_page_loads(self):
        response = self.client.get('/login_page')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login with Google', response.data)

    @patch('app.OAuth2Session')
    def test_03_google_login_redirects_to_google(self, mock_oauth_session):
        mock_session_instance = MagicMock()
        mock_session_instance.authorization_url.return_value = ('https://google.com/auth', 'test_state')
        mock_oauth_session.return_value = mock_session_instance

        response = self.client.get('/login/google', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, 'https://google.com/auth')
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['oauth_state'], 'test_state')

    @patch('app.OAuth2Session')
    def test_04_google_callback_success(self, mock_oauth_session):
        mock_session_instance = MagicMock()
        # Simulate token fetching
        mock_session_instance.fetch_token.return_value = {'access_token': 'fake_token'}
        # Simulate user info fetching
        mock_user_info = {'id': self.test_user_id, 'name': self.test_user_name, 'email': self.test_user_email}
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = mock_user_info
        mock_get_response.raise_for_status.return_value = None # Simulate successful HTTP request
        mock_session_instance.get.return_value = mock_get_response

        mock_oauth_session.return_value = mock_session_instance

        with self.client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state_callback'

        response = self.client.get('/auth/google/authorized?state=test_state_callback&code=auth_code', follow_redirects=False) # Updated path

        self.assertEqual(response.status_code, 302) # Should redirect to home
        self.assertTrue('/home' in response.location)

        with self.client.session_transaction() as sess:
            self.assertTrue('_user_id' in sess) # Check if user is logged in by Flask-Login
            self.assertEqual(sess['_user_id'], self.test_user_id)
            self.assertEqual(sess['user_data']['email'], self.test_user_email)

    def test_05_home_page_requires_login(self):
        response = self.client.get('/home', follow_redirects=False)
        self.assertEqual(response.status_code, 302) # Redirect to login_page
        self.assertTrue('/login_page' in response.location)

    def test_06_home_page_loads_when_logged_in(self):
        # Manually log in a user for this test
        with self.client.session_transaction() as sess:
            sess['user_data'] = self.user_data
            # Flask-Login uses _user_id to track logged-in user
            # We also need to ensure the user_loader can find this user
            # For this test, User.get relies on session['user_data']
            sess['_user_id'] = self.test_user_id
            sess['_fresh'] = True # Mark session as fresh

        response = self.client.get('/home')
        self.assertEqual(response.status_code, 200)
        # Check for new home page content
        self.assertIn(bytes(f'Welcome, {self.test_user_name}!', 'utf-8'), response.data)
        self.assertIn(b"Character Creation", response.data)
        self.assertIn(b"Admin", response.data)
        self.assertIn(b"1. Choose a Race", response.data) # Character creation step
        self.assertIn(b"Enter REST API URL", response.data) # Admin tab content

    def test_07_logout(self):
        # First, log in the user
        self._simulate_login() # Use helper

        # Verify user is logged in by accessing home
        response = self.client.get('/home', follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes(f'Welcome, {self.test_user_name}!', 'utf-8'), response.data)


        # Then, log out
        response = self.client.get('/logout', follow_redirects=True) # Follow redirect to index then to login_page
        self.assertEqual(response.status_code, 200) # Final page is login_page
        self.assertIn(b'Login with Google', response.data)


        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('_user_id'))
            self.assertIsNone(sess.get('user_data'))

        # Verify current_user is anonymous after logout
        # This needs to be in a request context, self.client provides this
        with self.client:
            # current_user is proxied, direct access might not work as expected outside a view
            # A simple way is to check a protected route redirects
            home_response = self.client.get('/home', follow_redirects=False)
            self.assertEqual(home_response.status_code, 302) # Should redirect to login


    @patch('app.OAuth2Session')
    def test_08_google_callback_token_fetch_failure(self, mock_oauth_session):
        mock_session_instance = MagicMock()
        mock_session_instance.fetch_token.side_effect = Exception("Token fetch error")
        mock_oauth_session.return_value = mock_session_instance

        with self.client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state_error'

        response = self.client.get('/auth/google/authorized?state=test_state_error&code=auth_code') # Updated path
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Error during authentication", response.data)

    @patch('app.OAuth2Session')
    def test_09_google_callback_user_info_fetch_failure(self, mock_oauth_session):
        mock_session_instance = MagicMock()
        mock_session_instance.fetch_token.return_value = {'access_token': 'fake_token'}

        mock_get_response = MagicMock()
        mock_get_response.raise_for_status.side_effect = Exception("User info fetch error") # Simulate HTTP error
        mock_session_instance.get.return_value = mock_get_response

        mock_oauth_session.return_value = mock_session_instance

        with self.client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state_user_info_error'

        response = self.client.get('/auth/google/authorized?state=test_state_user_info_error&code=auth_code') # Updated path
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Error fetching user information", response.data)

    # --- New tests for Admin page structure fetching ---
    @patch('app.requests.get') # Mock the requests.get call within app.py
    def test_10_admin_get_structure_success(self, mock_get):
        self._simulate_login()

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"key1": "value1", "nested": {"key2": "value2"}}
        mock_api_response.raise_for_status.return_value = None # Simulate no HTTP error
        mock_get.return_value = mock_api_response

        target_url = "http://fakeapi.com/data"
        response = self.client.get(f'/admin/get_structure?url={target_url}')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["key1"], "value1")
        self.assertEqual(data["nested"]["key2"], "value2")
        mock_get.assert_called_once_with(target_url)

    @patch('app.requests.get')
    def test_10a_admin_get_structure_pagination(self, mock_get):
        self._simulate_login()

        # Mock responses for pagination
        mock_response_page1 = MagicMock()
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = {
            "count": 2,
            "next": "http://fakeapi.com/data?page=2",
            "previous": None,
            "results": [{"id": 1, "name": "Item 1"}]
        }
        mock_response_page1.raise_for_status.return_value = None

        mock_response_page2 = MagicMock()
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = {
            "count": 2, # Original count might still be there
            "next": None,
            "previous": "http://fakeapi.com/data?page=1",
            "results": [{"id": 2, "name": "Item 2"}]
        }
        mock_response_page2.raise_for_status.return_value = None

        # Configure mock_get to return page1 then page2
        mock_get.side_effect = [mock_response_page1, mock_response_page2]

        initial_url = "http://fakeapi.com/data"
        response = self.client.get(f'/admin/get_structure?url={initial_url}')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Verify calls to requests.get
        self.assertEqual(mock_get.call_count, 2)
        mock_get.assert_any_call(initial_url)
        mock_get.assert_any_call("http://fakeapi.com/data?page=2")

        # Check combined results
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["name"], "Item 1")
        self.assertEqual(data["results"][1]["name"], "Item 2")
        self.assertEqual(data["count"], 2) # Updated count
        self.assertIsNone(data.get("next")) # 'next' should be removed or None
        # 'previous' from the first page is preserved by current logic if not explicitly removed
        # self.assertIsNone(data.get("previous"))

    @patch('app.requests.get')
    def test_11_admin_get_structure_handles_request_exception(self, mock_get):
        self._simulate_login()

        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        target_url = "http://fakeapi.com/data_error"
        response = self.client.get(f'/admin/get_structure?url={target_url}')

        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Network error")

    @patch('app.requests.get')
    def test_12_admin_get_structure_handles_http_error_status(self, mock_get):
        self._simulate_login()

        mock_api_response = MagicMock()
        mock_api_response.status_code = 404 # Simulate Not Found
        mock_api_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error: Not Found for url")
        mock_get.return_value = mock_api_response

        target_url = "http://fakeapi.com/nonexistent"
        response = self.client.get(f'/admin/get_structure?url={target_url}')

        self.assertEqual(response.status_code, 500) # Our handler returns 500 for upstream errors
        data = response.get_json()
        self.assertIn("error", data)
        # The error message comes from requests.exceptions.HTTPError
        self.assertTrue("404 Client Error: Not Found for url" in data["error"])


    @patch('app.requests.get')
    def test_13_admin_get_structure_handles_invalid_json(self, mock_get):
        self._simulate_login()

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.raise_for_status.return_value = None
        mock_api_response.json.side_effect = ValueError("Decoding JSON has failed") # Simulate invalid JSON
        mock_get.return_value = mock_api_response

        target_url = "http://fakeapi.com/badjson"
        response = self.client.get(f'/admin/get_structure?url={target_url}')

        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Invalid JSON response")

    def test_14_admin_get_structure_missing_url_parameter(self):
        self._simulate_login()
        response = self.client.get('/admin/get_structure') # No URL parameter
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "URL parameter is missing")

    def test_15_admin_get_structure_requires_login(self):
        # Ensure user is logged out for this test
        with self.client.session_transaction() as sess:
            sess.clear()

        response = self.client.get('/admin/get_structure?url=http://test.com', follow_redirects=False)
        self.assertEqual(response.status_code, 302) # Redirect to login
        self.assertTrue('/login_page' in response.location)


if __name__ == '__main__':
    # Create instance folder and a dummy config if they don't exist, for tests to run standalone
    instance_dir = os.path.join(os.path.dirname(__file__), '..', 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)

    dummy_config_path = os.path.join(instance_dir, 'config.py')
    if not os.path.exists(dummy_config_path):
        with open(dummy_config_path, 'w') as f:
            f.write("GOOGLE_CLIENT_ID = 'TEST_CLIENT_ID_FROM_RUNNER'\n")
            f.write("GOOGLE_CLIENT_SECRET = 'TEST_CLIENT_SECRET_FROM_RUNNER'\n")
            f.write("GEMINI_API_KEY = 'TEST_GEMINI_KEY_FROM_RUNNER'\n")
            f.write("ADMIN_EMAIL = 'admin_runner@example.com'\n")
            f.write("SECRET_KEY = 'testrunnerkey'\n")

    unittest.main()
