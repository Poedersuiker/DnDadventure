import unittest
from app import app, db, User
import os

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance')
        os.makedirs(instance_path, exist_ok=True)
        self.config_path = os.path.join(instance_path, 'config.py')
        with open(self.config_path, 'w') as f:
            f.write("SECRET_KEY = 'test-secret-key'\n")
            f.write("GOOGLE_CLIENT_ID = 'test'\n")
            f.write("GOOGLE_CLIENT_SECRET = 'test'\n")
            f.write("GOOGLE_REDIRECT_URI = 'http://localhost:5000/authorize'\n")

        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SERVER_NAME'] = 'localhost:5000'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        os.remove(self.config_path)

    def test_login_page(self):
        with app.app_context():
            response = self.app.get('/login')
            self.assertEqual(response.status_code, 302)

    def test_unauthorized_access(self):
        with app.app_context():
            response = self.app.get('/')
            self.assertEqual(response.status_code, 302)

if __name__ == '__main__':
    unittest.main()
