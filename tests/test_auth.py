from tests.base_test import BaseTestCase
from app.models import User
from app import db
from bs4 import BeautifulSoup # For CSRF token parsing

class AuthTestCase(BaseTestCase):

    def _get_csrf_token(self, path='/auth/register'):
        """Helper method to get a CSRF token from a form page."""
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, f"Failed to get {path} for CSRF")
        soup = BeautifulSoup(response.data, 'html.parser')
        csrf_token_tag = soup.find('input', {'name': 'csrf_token'})
        self.assertIsNotNone(csrf_token_tag, f"CSRF token not found on {path}")
        self.assertIn('value', csrf_token_tag.attrs, "CSRF token input has no value attribute")
        return csrf_token_tag['value']

    def test_registration_page_loads(self):
        response = self.client.get('/auth/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Register', response.data)

    def test_successful_registration(self):
        csrf_token = self._get_csrf_token()
        response = self.client.post('/auth/register', data=dict(
            username='newuser',
            email='new@example.com',
            password='password123',
            password2='password123',
            csrf_token=csrf_token
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Should redirect to login
        self.assertIn(b'Sign In', response.data) # Now on login page
        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'new@example.com')

    def test_registration_existing_username(self):
        csrf_token = self._get_csrf_token()
        response = self.client.post('/auth/register', data=dict(
            username='testuser', # Existing user from BaseTestCase setUp
            email='new2@example.com',
            password='password123',
            password2='password123',
            csrf_token=csrf_token
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please use a different username.', response.data)

    def test_registration_existing_email(self):
        csrf_token = self._get_csrf_token()
        response = self.client.post('/auth/register', data=dict(
            username='anotheruser',
            email='test@example.com', # Existing email from BaseTestCase setUp
            password='password123',
            password2='password123',
            csrf_token=csrf_token
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please use a different email address.', response.data)

    def test_login_page_loads(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign In', response.data)

    def test_successful_login_logout(self):
        # Login
        response = self.login('testuser', 'password123')
        self.assertEqual(response.status_code, 200)
        # Should redirect to character selection if characters exist, or creation
        # For now, we just check that we are not on the login page anymore
        self.assertNotIn(b'Sign In', response.data) 
        self.assertIn(b'My Characters', response.data) # From base.html nav for logged-in user

        # Logout
        response = self.logout()
        self.assertEqual(response.status_code, 200)
        # Should redirect to login page after logout (current main.index behavior for unauth user)
        self.assertIn(b'Sign In', response.data) 

    def test_login_invalid_username(self):
        response = self.login('wronguser', 'password123')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)
        self.assertIn(b'Sign In', response.data) # Still on login page

    def test_login_invalid_password(self):
        response = self.login('testuser', 'wrongpassword')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)
        self.assertIn(b'Sign In', response.data) # Still on login page

    def test_access_required_route_not_logged_in(self):
        # /character/select_character is a login-required route
        response = self.client.get('/character/select_character', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign In', response.data) # Should be redirected to login

    def test_access_required_route_logged_in(self):
        self.login('testuser', 'password123')
        # /character/select_character is a login-required route
        response = self.client.get('/character/select_character')
        self.assertEqual(response.status_code, 200)
        # Check for content specific to select_character page
        self.assertIn(b'Select Your Character', response.data)

    def test_csrf_token_present_in_form(self):
        # self.client should be available if inheriting from a base test class
        # that sets up the Flask test client.
        # Ensure the app context is pushed if necessary, or that client does this.
        
        # Temporarily enable CSRF protection for this test
        original_csrf_enabled = self.app.config.get('WTF_CSRF_ENABLED', True) # Default to True if not set
        self.app.config['WTF_CSRF_ENABLED'] = True
        
        try:
            response = self.client.get('/test_csrf')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'name="csrf_token"', response.data) # Flask-WTF generates a hidden input with name="csrf_token"
            self.assertIn(b'id="csrf_token"', response.data)   # And id="csrf_token"
            self.assertIn(b'type="hidden"', response.data)
        finally:
            # Restore original CSRF setting
            self.app.config['WTF_CSRF_ENABLED'] = original_csrf_enabled

if __name__ == '__main__':
    unittest.main(verbosity=2)
