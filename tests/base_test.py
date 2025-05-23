import unittest
from app import create_app, db
from app.models import User, Character # Import your models
from app.config import TestConfig # Corrected import path

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all() # Create tables for the in-memory database
        self.client = self.app.test_client()

        # Optional: Create a helper to add a test user
        self.test_user = User(username='testuser', email='test@example.com')
        self.test_user.set_password('password123')
        db.session.add(self.test_user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # Helper method for login
    def login(self, username, password):
        return self.client.post('/auth/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    # Helper method for logout
    def logout(self):
        return self.client.get('/auth/logout', follow_redirects=True)
