import unittest
import json
from unittest.mock import patch, MagicMock, ANY 
from flask import current_app, url_for
from app import app, db
from app.models import User, Character, Race, Class, Setting # Added Setting

class TestMainRoutes(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False # If using Flask-WTF
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SERVER_NAME'] = 'localhost' # For url_for
        app.config['LOGIN_DISABLED'] = False # Ensure login is not globally disabled for this test

        # Store original config to restore later
        self.original_gemini_api_key = app.config.get('GEMINI_API_KEY')
        self.original_default_gemini_model = app.config.get('DEFAULT_GEMINI_MODEL')

        db.create_all()
        self.client = app.test_client()

        # Create a dummy race and class for character creation
        self.test_race = Race(id=1, name="TestHuman", speed=30, ability_score_increases='[]', languages='[]', traits='[]', size_description='', age_description='', alignment_description='')
        # Modify class for predictable HP calc (d6 hit die like a Wizard)
        self.test_class = Class(id=1, name="TestWizard", hit_die="d6", 
                                proficiency_saving_throws='["INT", "WIS"]', 
                                skill_proficiencies_option_count=2, skill_proficiencies_options='["Arcana", "History", "Investigation"]', 
                                starting_equipment='[]', proficiencies_armor='[]', proficiencies_weapons='[]', 
                                proficiencies_tools='[]', spellcasting_ability="INT")
        db.session.add_all([self.test_race, self.test_class])
        
        # Create dummy Spells
        self.cantrip = Spell(id=1, index='test-cantrip', name='Test Cantrip', description='[]', level=0, school='TestSchool', classes_that_can_use='["TestWizard"]')
        self.lvl2_spell = Spell(id=2, index='test-spell2', name='Test Spell L2', description='[]', level=2, school='TestSchool', classes_that_can_use='["TestWizard"]')
        db.session.add_all([self.cantrip, self.lvl2_spell])
        db.session.commit()

        self.user = User(id=1, email="test@example.com", google_id="test_google_id_main")
        db.session.add(self.user)
        db.session.commit()
        
        # This character is for general route testing, not specifically for clear_progress
        self.character = Character(id=1, name="TestChar", user_id=self.user.id, race_id=self.test_race.id, class_id=self.test_class.id, level=1, strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10, hp=10, max_hp=10, armor_class=10, speed=30)
        db.session.add(self.character)
        db.session.commit()
        
        # Simulate login for the user
        # Using self.client.post('/login') is more robust if you have a login route
        # For direct session manipulation:
        with self.client.session_transaction() as sess:
            sess['user_id'] = str(self.user.id) # Flask-Login typically uses string user_ids
            sess['_fresh'] = True
            # If your user_loader uses get(int(user_id)), ensure it's an int or adjust user_loader.
            # The current setup in routes.py's user_loader likely expects int. Let's stick to int for user_id.
            sess['user_id'] = self.user.id


    def tearDown(self):
        # It's good practice to ensure all mock patches are stopped in tearDown if they were started in setUp
        # For patches started with @patch decorator, they are automatically handled.
        db.session.remove()
        db.drop_all()
        # Restore original config
        app.config['GEMINI_API_KEY'] = self.original_gemini_api_key
        app.config['DEFAULT_GEMINI_MODEL'] = self.original_default_gemini_model
        self.app_context.pop()

    # Removed old test_send_chat_message_uses_configured_api_key_and_model

    @patch('app.main.routes.Setting.query') 
    @patch('app.main.routes.genai')    
    @patch('app.main.routes.current_app.logger')
    def test_send_chat_model_from_db(self, mock_logger, mock_genai_module, mock_setting_query):
        test_api_key = "test_gemini_key_for_chat_route_db"
        current_app.config['GEMINI_API_KEY'] = test_api_key

        test_model_name_from_db = "model-from-db"
        
        mock_db_setting_instance = MagicMock(spec=Setting)
        mock_db_setting_instance.value = test_model_name_from_db
        mock_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from DB model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_genai_module.GenerativeModel.return_value = mock_model_instance

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': 'Hello DM from DB test'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI test reply from DB model")

        mock_setting_query.filter_by.assert_called_once_with(key='DEFAULT_GEMINI_MODEL')
        mock_genai_module.GenerativeModel.assert_called_once_with(
            model_name=test_model_name_from_db, 
            safety_settings=ANY
        )
        mock_genai_module.configure.assert_called_once_with(api_key=test_api_key)
        # Optional: Check that no warning/error was logged for model selection
        # mock_logger.warning.assert_not_called() 
        # mock_logger.error.assert_not_called()


    @patch('app.main.routes.Setting.query')
    @patch('app.main.routes.genai')
    @patch('app.main.routes.current_app.logger') 
    def test_send_chat_model_from_config_fallback(self, mock_logger, mock_genai_module, mock_setting_query):
        test_api_key = "test_gemini_key_for_chat_route_config"
        current_app.config['GEMINI_API_KEY'] = test_api_key

        test_model_name_from_config = "model-from-config-py"
        current_app.config['DEFAULT_GEMINI_MODEL'] = test_model_name_from_config

        mock_setting_query.filter_by.return_value.first.return_value = None # Simulate Not in DB
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from config model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_genai_module.GenerativeModel.return_value = mock_model_instance

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': 'Hello DM from config fallback test'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI test reply from config model")

        mock_setting_query.filter_by.assert_called_once_with(key='DEFAULT_GEMINI_MODEL')
        mock_genai_module.GenerativeModel.assert_called_once_with(
            model_name=test_model_name_from_config, 
            safety_settings=ANY
        )
        mock_genai_module.configure.assert_called_once_with(api_key=test_api_key)
        mock_logger.warning.assert_called_with(
            f"Using DEFAULT_GEMINI_MODEL '{test_model_name_from_config}' from config.py (not found in DB or DB value empty)."
        )


    def test_clear_character_progress(self):
        # 1. Setup Character with progress
        # Ensure the user is "logged in" for this operation
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['_fresh'] = True

        char_to_clear = Character(
            name='ProgressChar',
            user_id=self.user.id,
            race_id=self.test_race.id,
            class_id=self.test_class.id, # Uses TestWizard (d6 hit die)
            level=5,
            strength=10, dexterity=10, constitution=14, # CON 14 -> +2 mod
            intelligence=10, wisdom=10, charisma=10,
            # L5 HP (Wizard d6: 6 (L1) + 4*3.5 (avg roll for L2-5) + 5*2 (CON mod*level) = 6 + 14 + 10 = 30)
            # Note: hit die avg for d6 is 3.5. Some use 4 (round up). Let's use 3.5 for calculation.
            # L1: 6 (hit die) + 2 (CON) = 8
            # L2-5: 4 levels * (3.5 avg hit + 2 CON) = 4 * 5.5 = 22
            # Total: 8 + 22 = 30
            max_hp=30, 
            hp=20,
            adventure_log=json.dumps([{'sender': 'user', 'text': 'old log entry'}, {'sender': 'dm', 'text': 'dm reply'}]),
            speed=30, # Ensure speed is set, it's a non-nullable field in model
            current_proficiencies='{}', # Assuming empty or default profs for simplicity
            current_equipment='{}' # Assuming empty or default equipment for simplicity
        )
        char_to_clear.known_spells.extend([self.cantrip, self.lvl2_spell])
        db.session.add(char_to_clear)
        db.session.commit()

        # 2. Test Action
        response = self.client.post(url_for('main.clear_character_progress', character_id=char_to_clear.id), follow_redirects=True)

        # 3. Assertions
        self.assertEqual(response.status_code, 200, "Response should be 200 OK after redirect.")
        
        updated_char = Character.query.get(char_to_clear.id)
        self.assertIsNotNone(updated_char, "Character should still exist.")
        self.assertEqual(updated_char.level, 1, "Character level should be reset to 1.")
        
        loaded_log = json.loads(updated_char.adventure_log)
        self.assertEqual(loaded_log, [], "Adventure log should be an empty list.")
        
        # Expected L1 Max HP for TestWizard (d6) with CON 14 (+2): 6 (hit die max at L1) + 2 (CON mod) = 8
        self.assertEqual(updated_char.max_hp, 8, "Max HP should be recalculated for level 1.") 
        self.assertEqual(updated_char.hp, updated_char.max_hp, "Current HP should be equal to max HP after reset.")
        
        self.assertEqual(len(updated_char.known_spells), 0, "Known spells should be cleared.")
        
        self.assertIn(b'Adventure progress cleared. Your character has been reset to level 1.', response.data, "Flash message not found in response.")


    @patch('app.main.routes.Setting.query')
    @patch('app.main.routes.genai')
    @patch('app.main.routes.current_app.logger')
    def test_send_chat_model_from_hardcoded_fallback(self, mock_logger, mock_genai_module, mock_setting_query):
        test_api_key = "test_gemini_key_for_chat_route_hardcoded"
        current_app.config['GEMINI_API_KEY'] = test_api_key
        
        current_app.config['DEFAULT_GEMINI_MODEL'] = None # Ensure not in config

        mock_setting_query.filter_by.return_value.first.return_value = None # Simulate Not in DB
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from hardcoded model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_genai_module.GenerativeModel.return_value = mock_model_instance

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': 'Hello DM from hardcoded fallback test'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI test reply from hardcoded model")

        mock_setting_query.filter_by.assert_called_once_with(key='DEFAULT_GEMINI_MODEL')
        mock_genai_module.GenerativeModel.assert_called_once_with(
            model_name="gemini-1.5-flash", # Hardcoded fallback
            safety_settings=ANY
        )
        mock_genai_module.configure.assert_called_once_with(api_key=test_api_key)
        mock_logger.error.assert_called_with("DEFAULT_GEMINI_MODEL not found in database or config.py.")
        mock_logger.warning.assert_called_with("Critial: Using hardcoded fallback Gemini model: gemini-1.5-flash.")


if __name__ == '__main__':
    unittest.main()
