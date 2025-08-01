import unittest
from unittest.mock import patch
from app import app, db, User, process_bot_response
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
        app.config['GEMINI_API_KEY'] = 'test-api-key'
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

    @patch('flask_login.utils._get_user')
    def test_admin_page_unauthorized(self, _get_user):
        with app.app_context():
            # Create a non-admin user
            user = User(google_id='12345', email='test@example.com', name='Test User')
            db.session.add(user)
            db.session.commit()
            _get_user.return_value = user

            response = self.app.get('/admin')
            self.assertEqual(response.status_code, 401)

    @patch('google.generativeai.list_models')
    @patch('flask_login.utils._get_user')
    def test_admin_page_authorized(self, _get_user, list_models):
        with app.app_context():
            # Create an admin user
            admin_user = User(google_id='admin123', email='admin@example.com', name='Admin User')
            db.session.add(admin_user)
            db.session.commit()
            _get_user.return_value = admin_user

            # Set ADMIN_EMAIL in config
            app.config['ADMIN_EMAIL'] = 'admin@example.com'

            # Mock the list_models call
            class MockModel:
                def __init__(self, name, display_name):
                    self.name = name
                    self.display_name = display_name
                    self.supported_generation_methods = ['generateContent']
            list_models.return_value = [MockModel('models/gemini-pro', 'Gemini Pro')]


            response = self.app.get('/admin')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Admin', response.data)

    def test_process_bot_response_ordered_list(self):
        bot_response = "Here are your ability scores. Please assign them to your abilities. [APPDATA]{ \"OrderedList\": { \"Title\": \"Assign Ability Scores\", \"Items\": [ { \"Name\": \"Strength\" }, { \"Name\": \"Dexterity\" } ], \"Values\": [ 15, 14 ] } }[/APPDATA]"
        processed_response = process_bot_response(bot_response)
        self.assertIn('<div class="ordered-list-container">', processed_response)
        self.assertIn('<h3>Assign Ability Scores</h3>', processed_response)
        self.assertIn('<li class="sortable-item first-item" data-name="Strength">Strength<div class="value-card" draggable="true" ondragstart="drag(event)" id="val-0"><span class="value">15</span><span class="arrows"><span class="up-arrow" onclick="moveValueUp(this)">&#8593;</span><span class="down-arrow" onclick="moveValueDown(this)">&#8595;</span></span><span class="drag-handle">&#9776;</span></div></li>', processed_response)
        self.assertIn('<li class="sortable-item last-item" data-name="Dexterity">Dexterity<div class="value-card" draggable="true" ondragstart="drag(event)" id="val-1"><span class="value">14</span><span class="arrows"><span class="up-arrow" onclick="moveValueUp(this)">&#8593;</span><span class="down-arrow" onclick="moveValueDown(this)">&#8595;</span></span><span class="drag-handle">&#9776;</span></div></li>', processed_response)
        self.assertIn('<button onclick="confirmOrderedList()">Confirm</button>', processed_response)

    def test_process_bot_response_mismatched_tags(self):
        from app import MalformedAppDataError
        bot_response = "Some text [APPDATA]{'key': 'value'}"
        with self.assertRaises(MalformedAppDataError):
            process_bot_response(bot_response)

    def test_process_bot_response_invalid_json(self):
        from app import MalformedAppDataError
        bot_response = "[APPDATA]{'key': 'value',,}[/APPDATA]"
        with self.assertRaises(MalformedAppDataError):
            process_bot_response(bot_response)

    @patch('app.genai.GenerativeModel')
    def test_handle_message_with_retry(self, MockGenerativeModel):
        from app import MalformedAppDataError, conversations

        # Mock the response from the generative model
        class MockResponse:
            def __init__(self, text):
                self.text = text
                self.parts = [self]

        # Simulate a sequence of responses: 1st is malformed, 2nd is valid
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content.side_effect = [
            MockResponse("[APPDATA]{'bad': json}[/APPDATA]"),
            MockResponse("This is the corrected response.")
        ]

        # Set up a fake conversation
        character_id = '1'
        conversations[character_id] = [{'role': 'user', 'parts': ['Hello']}]

        with app.test_request_context('/socket.io'):
            # We need to manually call the handler since we are in a test context
            from app import handle_message

            # Since handle_message uses emit, we need to patch it
            with patch('app.emit') as mock_emit:
                handle_message({'message': 'test message', 'character_id': character_id})

                # Check that generate_content was called twice (initial + 1 retry)
                self.assertEqual(mock_model_instance.generate_content.call_count, 2)

                # Check that the final message emitted to the user is the corrected one
                mock_emit.assert_called_once_with('message', {'text': 'This is the corrected response.', 'sender': 'other', 'character_id': '1'})

                # Check that the history was updated correctly with the retry context
                history = conversations[character_id]
                self.assertEqual(len(history), 5) # user, user, model(bad), user(fix), model(good)
                self.assertEqual(history[-2]['parts'][0], "The response you just sent contained a malformed [APPDATA] block. Please correct the formatting of the JSON data and resend your message.")


if __name__ == '__main__':
    unittest.main()
