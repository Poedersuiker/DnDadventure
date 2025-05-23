from tests.base_test import BaseTestCase
from app.models import User
from app import db

class AuthTestCase(BaseTestCase):

    def test_registration_page_loads(self):
        response = self.client.get('/auth/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Register', response.data)

    def test_successful_registration(self):
        response = self.client.post('/auth/register', data=dict(
            username='newuser',
            email='new@example.com',
            password='password123',
            password2='password123'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Should redirect to login
        self.assertIn(b'Sign In', response.data) # Now on login page
        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'new@example.com')

    def test_registration_existing_username(self):
        response = self.client.post('/auth/register', data=dict(
            username='testuser', # Existing user from BaseTestCase setUp
            email='new2@example.com',
            password='password123',
            password2='password123'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please use a different username.', response.data)

    def test_registration_existing_email(self):
        response = self.client.post('/auth/register', data=dict(
            username='anotheruser',
            email='test@example.com', # Existing email from BaseTestCase setUp
            password='password123',
            password2='password123'
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

if __name__ == '__main__':
    unittest.main(verbosity=2)
