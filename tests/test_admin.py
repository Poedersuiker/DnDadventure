import unittest
from unittest.mock import patch
from app import app, db, User  # Assuming User is directly accessible from app
from flask import current_app, session

class AdminTestCase(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # If using Flask-WTF for forms
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Use in-memory DB for tests
        app.config['ADMIN_EMAIL'] = 'admin@test.com'
        app.config['GEMINI_API_KEY'] = 'test_gemini_api_key' # Dummy key for tests
        app.config['DEFAULT_GEMINI_MODEL'] = 'gemini-default'
        app.config['SERVER_NAME'] = 'localhost.localdomain' # Required for url_for outside of request context

        self.client = app.test_client()
        db.create_all()

        # Create users
        self.admin_user = User(email=app.config['ADMIN_EMAIL'], google_id="admin_google_id_test")
        self.non_admin_user = User(email="testuser@example.com", google_id="user_google_id_test")
        db.session.add_all([self.admin_user, self.non_admin_user])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email):
        """Helper function to simulate user login by setting session."""
        user = User.query.filter_by(email=email).first()
        if user:
            with self.client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['_fresh'] = True # Common for Flask-Login
        return user

    def logout(self):
        """Helper function to simulate user logout."""
        with self.client.session_transaction() as sess:
            sess.clear()

    # --- Test Cases Will Go Here ---

    # Step 2: Tests for Admin Route Access Control
    def test_admin_routes_unauthenticated_redirect(self):
        """Test that accessing /admin/general without logging in redirects to the login page."""
        response = self.client.get('/admin/general', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        # Assuming your login page is at '/login' or similar, check the redirect location
        # For Flask-Login, it redirects to login_manager.login_view which is 'main.login_page'
        # This will depend on your app's routing and login manager setup.
        # For now, checking for 302 is a good start.
        # A more specific check might be:
        # self.assertTrue(response.location.endswith(url_for('main.login_page', _external=False)))
        # However, url_for requires request context or SERVER_NAME, which is set in setUp.
        # Let's assume 'main.login_page' translates to something like '/login' or '/auth/login'
        # We can check if the location contains 'login' as a basic check.
        self.assertIn('/login', response.location.lower())


    def test_admin_routes_non_admin_forbidden(self):
        """Test that accessing /admin/general as a non-admin user results in a 403 Forbidden status."""
        self.login(email="testuser@example.com")
        response = self.client.get('/admin/general')
        self.assertEqual(response.status_code, 403)
        self.logout()

    def test_admin_routes_admin_accessible(self):
        """Test that accessing /admin/general as an admin user results in a 200 OK status."""
        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.get('/admin/general') # /admin/ redirects to /admin/general
        self.assertEqual(response.status_code, 200)
        self.logout()

    # Step 3: Tests for General Settings Tab (/admin/general)
    @patch('app.utils.list_gemini_models')
    def test_general_settings_page_load(self, mock_list_models):
        """Test that the general settings page loads correctly for an admin."""
        mock_list_models.return_value = ['gemini-test-model', 'gemini-pro', app.config['DEFAULT_GEMINI_MODEL']]
        self.login(email=app.config['ADMIN_EMAIL'])
        
        response = self.client.get('/admin/general')
        self.assertEqual(response.status_code, 200)
        
        response_data = response.get_data(as_text=True)
        self.assertIn('gemini-test-model', response_data)
        self.assertIn('gemini-pro', response_data)
        # Check if the current default model is selected
        self.assertIn(f'<option value="{app.config["DEFAULT_GEMINI_MODEL"]}" selected', response_data)
        self.logout()

    @patch('app.utils.list_gemini_models')
    def test_general_settings_update_model(self, mock_list_models):
        """Test updating the default Gemini model."""
        mock_list_models.return_value = ['gemini-test-model', 'gemini-pro', 'new-gemini-model']
        self.login(email=app.config['ADMIN_EMAIL'])
        
        new_model_to_set = 'new-gemini-model'
        response = self.client.post('/admin/general', 
                                    data={'gemini_model': new_model_to_set}, 
                                    follow_redirects=False) # Test redirect separately
        
        self.assertEqual(response.status_code, 302) # Should redirect
        self.assertIn('/admin/general', response.location)
        self.assertEqual(current_app.config['DEFAULT_GEMINI_MODEL'], new_model_to_set)

        # Check for flash message - this requires follow_redirects=True or checking session
        with self.client.session_transaction() as sess:
            flashed_messages = dict(sess.get('_flashes', []))
            self.assertIn('success', flashed_messages) # Check if 'success' category exists
            self.assertIn(f"Default Gemini Model updated to {new_model_to_set}", flashed_messages['success'])
        
        self.logout()

    # Step 4: Tests for Registered Users Tab (/admin/users)
    def test_registered_users_page_load(self):
        """Test that the registered users page loads correctly for an admin and displays users."""
        self.login(email=app.config['ADMIN_EMAIL'])
        
        response = self.client.get('/admin/users')
        self.assertEqual(response.status_code, 200)
        
        response_data = response.get_data(as_text=True)
        self.assertIn(app.config['ADMIN_EMAIL'], response_data) # Admin user
        self.assertIn("testuser@example.com", response_data)   # Non-admin user
        self.assertIn("Registered Users", response_data)
        self.logout()

    # Step 5: Tests for Database Population Tab (/admin/db-populate)
    def test_db_population_page_load(self):
        """Test that the DB population page loads correctly for an admin."""
        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.get('/admin/db-populate')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Database Population", response.get_data(as_text=True))
        self.assertIn("Populate Races", response.get_data(as_text=True))
        self.assertIn("Populate Classes", response.get_data(as_text=True))
        self.assertIn("Populate Spells", response.get_data(as_text=True))
        self.logout()

    @patch('app.admin.routes.populate_races_data')
    def test_run_populate_races(self, mock_populate_races):
        """Test triggering the populate_races_data script."""
        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.post('/admin/db-populate/races', follow_redirects=False)
        
        self.assertEqual(response.status_code, 302) # Should redirect
        self.assertIn('/admin/db-populate', response.location)
        mock_populate_races.assert_called_once()
        
        with self.client.session_transaction() as sess:
            flashed_messages = dict(sess.get('_flashes', []))
            self.assertIn('info', flashed_messages) # Check for initial info message
            # The success message is added *after* the script runs,
            # so we'd need to check it on the redirected page or mock the script to add it before returning
            # For simplicity, here we just check the info message and that the script was called.
            # To test the success message properly, you might need a more complex setup or to check the session *after* redirect.
            # For this test, let's assume the script adds its own flash for completion if necessary or relies on the route.
            # The route *does* add a success flash, so we check it after redirection.
        
        # Follow redirect to check for success flash
        response_redirect = self.client.get(response.location)
        with self.client.session_transaction() as sess_redirect: # Need to re-access session for the new request
            flashed_messages_redirect = dict(sess_redirect.get('_flashes', []))
            self.assertIn('success', flashed_messages_redirect, "Success flash for race population missing after redirect")
            self.assertIn("Race population script finished successfully.", flashed_messages_redirect['success'])

        self.logout()

    @patch('app.admin.routes.populate_classes_data')
    def test_run_populate_classes(self, mock_populate_classes):
        """Test triggering the populate_classes_data script."""
        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.post('/admin/db-populate/classes', follow_redirects=True) # Follow redirect for flash
        
        self.assertEqual(response.status_code, 200) # After redirect
        mock_populate_classes.assert_called_once()
        
        with self.client.session_transaction() as sess:
            flashed_messages = dict(sess.get('_flashes', []))
            # Order of flashes might matter, or if one overwrites another.
            # Typically, flash messages are consumed after being displayed.
            # Let's check for the final success message.
            self.assertIn('success', flashed_messages)
            self.assertIn("Class population script finished successfully.", flashed_messages['success'])
        self.logout()

    @patch('app.admin.routes.populate_spells_data')
    def test_run_populate_spells(self, mock_populate_spells):
        """Test triggering the populate_spells_data script."""
        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.post('/admin/db-populate/spells', follow_redirects=True) # Follow redirect for flash
        
        self.assertEqual(response.status_code, 200) # After redirect
        mock_populate_spells.assert_called_once()

        with self.client.session_transaction() as sess:
            flashed_messages = dict(sess.get('_flashes', []))
            self.assertIn('success', flashed_messages)
            self.assertIn("Spell population script finished successfully.", flashed_messages['success'])
        self.logout()

    # Step 6: Tests for Server Logging Tab (/admin/server-logs)
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="INFO: Log line 1\nERROR: Log line 2")
    def test_server_logs_page_load(self, mock_open_file, mock_path_exists):
        """Test that the server logs page loads correctly and displays log content."""
        mock_path_exists.return_value = True # Simulate log file exists
        app.config['APP_LOG_FILE'] = '/fake/instance/app.log' # Ensure this is set
        
        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.get('/admin/server-logs')
        
        self.assertEqual(response.status_code, 200)
        response_data = response.get_data(as_text=True)
        self.assertIn("Server Logs", response_data)
        self.assertIn("INFO: Log line 1", response_data)
        self.assertIn("ERROR: Log line 2", response_data)
        mock_open_file.assert_called_once_with(app.config['APP_LOG_FILE'], 'r')
        self.logout()

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_clear_logs(self, mock_open_file, mock_path_exists):
        """Test clearing the log file."""
        mock_path_exists.return_value = True # Simulate log file exists
        app.config['APP_LOG_FILE'] = '/fake/instance/app.log'

        self.login(email=app.config['ADMIN_EMAIL'])
        response = self.client.get('/admin/server-logs/clear', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200) # After redirect
        mock_open_file.assert_called_once_with(app.config['APP_LOG_FILE'], 'w')
        
        with self.client.session_transaction() as sess:
            flashed_messages = dict(sess.get('_flashes', []))
            self.assertIn('success', flashed_messages)
            self.assertIn("Log file cleared successfully.", flashed_messages['success'])
        self.logout()

if __name__ == '__main__':
    unittest.main()
