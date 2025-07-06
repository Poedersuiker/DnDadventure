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


# It's important to configure the app for testing BEFORE importing it if it initializes extensions at import time.
# However, our app.py initializes extensions (like LoginManager) at the module level.
# This makes it tricky. A better approach is an app factory pattern.
# For now, we will try to work with the existing structure.

# Apply test configurations globally before app import for some settings if possible,
# or ensure they are applied before the first request.
# This is a common challenge with Flask app testing without a factory.

from app import app, User # login_manager is already configured in app.py

# Apply test configurations. This should ideally be done before the app is fully "used".
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing forms if any
app.config['SECRET_KEY'] = 'test_secret_key_for_unittest' # Ensure a consistent secret key for session for tests
app.config['SERVER_NAME'] = 'localhost.test' # Required for url_for outside of request context in some cases

# Override sensitive or environment-specific configs for tests
# Ensure these are applied before any test client makes requests.
app.config['GOOGLE_CLIENT_ID'] = 'TEST_CLIENT_ID_FOR_UNITTEST'
app.config['GOOGLE_CLIENT_SECRET'] = 'TEST_CLIENT_SECRET_FOR_UNITTEST'
app.config['ADMIN_EMAIL'] = 'test_admin_for_unittest@example.com'
app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost.test/auth/google/authorized' # Test specific redirect URI with new path
# The dummy config.py created by app.py might overwrite these if not careful.
# It's better if tests manage their config explicitly.

class AuthTestCase(unittest.TestCase):

    def setUp(self):
        # The app is already configured with TESTING = True etc. from above.
        # Create a new test client for each test.
        self.client = app.test_client()

        # Create a dummy user for login simulation
        self.test_user_id = '12345'
        self.test_user_name = 'Test User'
        self.test_user_email = 'test@example.com'
        self.user_data = {'id': self.test_user_id, 'name': self.test_user_name, 'email': self.test_user_email}

    def tearDown(self):
        with self.client.session_transaction() as sess:
            sess.clear()

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
        self.assertIn(bytes(f'Hello, {self.test_user_name}!', 'utf-8'), response.data)

    def test_07_logout(self):
        # First, log in the user
        with self.client.session_transaction() as sess:
            sess['user_data'] = self.user_data
            sess['_user_id'] = self.test_user_id
            sess['_fresh'] = True

        # Verify user is logged in by accessing home
        response = self.client.get('/home', follow_redirects=False)
        self.assertEqual(response.status_code, 200)

        # Then, log out
        response = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login_page' in response.location or '/' in response.location) # Redirects to index, which then redirects to login_page

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('_user_id'))
            self.assertIsNone(sess.get('user_data'))

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
