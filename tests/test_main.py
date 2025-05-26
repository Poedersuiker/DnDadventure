import unittest
import json
from unittest.mock import patch, MagicMock, ANY # Added ANY
from flask import current_app, url_for
from app import app, db
from app.models import User, Character, Race, Class # Add other necessary models

class TestMainRoutes(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False # If using Flask-WTF
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SERVER_NAME'] = 'localhost' # For url_for

        # Store original config to restore later
        self.original_gemini_api_key = app.config.get('GEMINI_API_KEY')
        self.original_default_gemini_model = app.config.get('DEFAULT_GEMINI_MODEL')

        db.create_all()
        self.client = app.test_client()

        # Create a dummy race and class for character creation
        test_race = Race(id=1, name="Human", speed=30, ability_score_increases='[]', languages='[]', traits='[]', size_description='', age_description='', alignment_description='')
        test_class = Class(id=1, name="Warrior", hit_die="d10", proficiency_saving_throws='[]', skill_proficiencies_option_count=0, skill_proficiencies_options='[]', starting_equipment='[]', proficiencies_armor='[]', proficiencies_weapons='[]', proficiencies_tools='[]', spellcasting_ability=None)
        db.session.add_all([test_race, test_class])
        db.session.commit()

        self.user = User(id=1, email="test@example.com", google_id="test_google_id_main")
        db.session.add(self.user)
        db.session.commit()
        
        self.character = Character(id=1, name="TestChar", user_id=self.user.id, race_id=test_race.id, class_id=test_class.id, level=1, strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10, hp=10, max_hp=10, armor_class=10, speed=30)
        db.session.add(self.character)
        db.session.commit()
        
        # Simulate login for the user
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            # Flask-Login typically uses '_fresh' and '_user_id' in session
            # For basic @login_required, setting 'user_id' is often enough if user_loader is simple.
            # Let's ensure essential keys for Flask-Login are present if it's more strict.
            sess['_fresh'] = True 
            # sess['_user_id'] = str(self.user.id) # Some setups might need this as string

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Restore original config
        app.config['GEMINI_API_KEY'] = self.original_gemini_api_key
        app.config['DEFAULT_GEMINI_MODEL'] = self.original_default_gemini_model
        self.app_context.pop()

    @patch('app.main.routes.genai') # Target 'genai' where it's imported in routes
    def test_send_chat_message_uses_configured_api_key_and_model(self, mock_genai_module):
        test_api_key = "test_gemini_key_for_chat_route"
        test_model_name = "test-gemini-model-for-chat"
        
        current_app.config['GEMINI_API_KEY'] = test_api_key
        current_app.config['DEFAULT_GEMINI_MODEL'] = test_model_name

        # Configure the mock chain for genai
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock()
        mock_response_instance.text = "AI test reply"

        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_genai_module.GenerativeModel.return_value = mock_model_instance
        
        # Make the call
        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': 'Hello DM'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI test reply")

        # Assertions
        mock_genai_module.configure.assert_called_once_with(api_key=test_api_key)
        mock_genai_module.GenerativeModel.assert_called_once_with(
            model_name=test_model_name,
            safety_settings=ANY # Using ANY from unittest.mock
        )

if __name__ == '__main__':
    unittest.main()
