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

    @patch('app.send_to_gemini_with_retry')
    def test_handle_message_with_retry(self, mock_send_to_gemini):
        from app import handle_message, Message, Character, User

        # Simulate the behavior of send_to_gemini_with_retry
        # It should save the malformed response and the retry message to history
        def side_effect(model, history, max_retries=3):
            # The history passed in already has the user's message
            # Add the malformed model response
            history.append({'role': 'model', 'parts': ["[APPDATA]{'bad': json}[/APPDATA]"]})
            # Add the retry prompt from the user
            history.append({'role': 'user', 'parts': ["The response you just sent contained a malformed [APPDATA] block. Please correct the formatting of the JSON data and resend your message."]})
            # Return the final, good response
            return "This is the corrected response.", "This is the corrected response."

        mock_send_to_gemini.side_effect = side_effect

        with app.app_context():
            # Set up a fake user and character
            user = User(google_id='retry_user', email='retry@test.com', name='Retry User')
            db.session.add(user)
            db.session.commit()

            character = Character(user_id=user.id, ttrpg_type_id=1, character_name='Retry Character', charactersheet='{}')
            db.session.add(character)
            db.session.commit()

            # Set up the initial message in the database
            initial_message = Message(character_id=character.id, role='user', content='Hello')
            db.session.add(initial_message)
            db.session.commit()

            with app.test_request_context('/socket.io'):
                with patch('app.emit') as mock_emit:
                    handle_message({'message': 'test message', 'character_id': str(character.id)})

                    # Check that send_to_gemini_with_retry was called
                    self.assertEqual(mock_send_to_gemini.call_count, 1)

                    # Check that the final message emitted is the corrected one
                    mock_emit.assert_called_with('message', {'text': 'This is the corrected response.', 'sender': 'received', 'character_id': str(character.id)})

                    # Check the database state
                    messages = Message.query.filter_by(character_id=character.id).order_by(Message.timestamp).all()
                    self.assertEqual(len(messages), 3) # initial 'Hello', user's 'test message', final 'model' response
                    self.assertEqual(messages[0].content, 'Hello')
                    self.assertEqual(messages[1].content, 'test message')
                    self.assertEqual(messages[2].content, 'This is the corrected response.')

    def test_process_bot_response_dice_roll(self):
        bot_response = "[APPDATA]{\"DiceRoll\": {\"Title\": \"Roll for initiative!\", \"ButtonText\": \"Roll!\", \"Mechanic\": \"Classic\", \"Dice\": \"1d20\"}}[/APPDATA]"
        processed_response = process_bot_response(bot_response)
        self.assertIn('<div class="diceroll-container">', processed_response)
        self.assertIn('<h3>Roll for initiative!</h3>', processed_response)
        self.assertIn('<button onclick="rollDice(\'{&quot;Title&quot;: &quot;Roll for initiative!&quot;, &quot;ButtonText&quot;: &quot;Roll!&quot;, &quot;Mechanic&quot;: &quot;Classic&quot;, &quot;Dice&quot;: &quot;1d20&quot;}\')">Roll!</button>', processed_response)

    @patch('app.dice_roller.roll')
    @patch('app.send_to_gemini_with_retry')
    def test_handle_dice_roll(self, mock_send_to_gemini, mock_roll):
        from app import handle_dice_roll, Message, Character, User

        mock_roll.return_value = [{'total': 12, 'rolls': [12], 'dropped': []}]
        mock_send_to_gemini.return_value = ("Gemini says you rolled well.", "Gemini says you rolled well.")

        with app.app_context():
            user = User(google_id='dice_user', email='dice@test.com', name='Dice User')
            db.session.add(user)
            db.session.commit()

            character = Character(user_id=user.id, ttrpg_type_id=1, character_name='Dice Character', charactersheet='{}')
            db.session.add(character)
            db.session.commit()

            roll_params = {"Title": "Initiative", "Mechanic": "Classic", "Dice": "1d20"}
            data = {'character_id': str(character.id), 'roll_params': roll_params}

            with app.test_request_context('/socket.io'):
                with patch('app.emit') as mock_emit:
                    handle_dice_roll(data)

                    # Check that dice_roller.roll was called correctly
                    mock_roll.assert_called_once_with(
                        mechanic='Classic',
                        dice='1d20',
                        num_rolls=1,
                        advantage=False,
                        disadvantage=False
                    )

                    # Check that the result is emitted to the client
                    mock_emit.assert_any_call('dice_roll_result', {'results': [{'total': 12, 'rolls': [12], 'dropped': []}], 'character_id': str(character.id)})

                    # Check that send_to_gemini_with_retry was called
                    self.assertEqual(mock_send_to_gemini.call_count, 1)

                    # Check that the final message is emitted
                    mock_emit.assert_called_with('message', {'text': 'Gemini says you rolled well.', 'sender': 'received', 'character_id': str(character.id)})

                    # Check the database state
                    messages = Message.query.filter_by(character_id=character.id).order_by(Message.timestamp).all()
                    self.assertEqual(len(messages), 2)
                    self.assertEqual(messages[0].content, "I rolled for Initiative: (Total: 12, Rolls: [12])")
                    self.assertEqual(messages[1].content, 'Gemini says you rolled well.')

if __name__ == '__main__':
    unittest.main()
