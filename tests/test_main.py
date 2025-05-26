import unittest
import json
from unittest.mock import patch, MagicMock, ANY 
from flask import current_app, url_for
from app import app, db
from app.models import User, Character, Race, Class, Setting, Spell # Added Spell

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
        
        # Set default test values for keys used by app.gemini
        app.config['GEMINI_API_KEY'] = "default_test_api_key"
        app.config['DEFAULT_GEMINI_MODEL'] = "default_test_model"


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
        
        # This character is for general route testing
        self.character = Character(id=1, name="TestChar", user_id=self.user.id, race_id=self.test_race.id, class_id=self.test_class.id, level=1, strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10, hp=10, max_hp=10, armor_class=10, speed=30, current_proficiencies=json.dumps({'skills': ['Perception', 'Stealth']}))
        db.session.add(self.character)
        db.session.commit()
        
        # Simulate login for the user
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id 
            sess['_fresh'] = True


    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Restore original config
        app.config['GEMINI_API_KEY'] = self.original_gemini_api_key
        app.config['DEFAULT_GEMINI_MODEL'] = self.original_default_gemini_model
        self.app_context.pop()

    # Old tests for send_chat_message that might need updating/removal due to refactoring
    # For now, they are left as is, but their patch targets might be incorrect for deep logic testing.
    @patch('app.main.routes.Setting.query') 
    @patch('app.gemini.genai') # Patched app.gemini.genai for the call from routes
    @patch('app.gemini.current_app') # Patched app.gemini.current_app for the call from routes
    def test_send_chat_model_from_db(self, mock_gemini_current_app, mock_gemini_genai_module, mock_main_routes_setting_query):
        # This test is now more of an integration test for the route calling gemini module
        test_api_key_val = "test_gemini_key_for_chat_route_db"
        # mock_gemini_current_app.config.get('GEMINI_API_KEY').return_value = test_api_key_val
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key_val, 'DEFAULT_GEMINI_MODEL': 'db_should_override'}
        mock_gemini_current_app.logger = MagicMock()


        test_model_name_from_db = "model-from-db"
        
        mock_db_setting_instance = MagicMock(spec=Setting)
        mock_db_setting_instance.value = test_model_name_from_db
        # This Setting.query is from app.gemini, so the patch should be app.gemini.Setting.query for full effect
        # However, the route itself doesn't call Setting.query. The call is in app.gemini.geminiai
        # To make this specific test work as intended for model selection, the patch for Setting.query
        # should also be 'app.gemini.Setting.query'.
        # For now, the test ensures the route calls geminiai, and geminiai would do its logic.
        # The more detailed model selection tests are the new ones below.
        
        # If we want to test the model selection within gemini from this old test,
        # we'd mock 'app.gemini.Setting.query' instead of 'app.main.routes.Setting.query'
        # Let's assume this test now primarily checks the route's interaction with a mocked geminiai
        
        mock_main_routes_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance # This mock won't be hit by gemini.py

        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from DB model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance

        with patch('app.gemini.Setting.query') as mock_gemini_setting_query: # More specific patch for gemini's Setting query
            mock_gemini_db_setting_instance = MagicMock(spec=Setting)
            mock_gemini_db_setting_instance.value = test_model_name_from_db
            mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_gemini_db_setting_instance

            response = self.client.post(
                url_for('main.send_chat_message', character_id=self.character.id),
                json={'message': 'Hello DM from DB test'}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['reply'], "AI test reply from DB model")

            mock_gemini_setting_query.filter_by.assert_called_once_with(key='DEFAULT_GEMINI_MODEL')
            mock_gemini_genai_module.GenerativeModel.assert_called_once_with(
                model_name=test_model_name_from_db, 
                safety_settings=ANY
            )
            mock_gemini_genai_module.configure.assert_called_once_with(api_key=test_api_key_val)


    @patch('app.gemini.Setting.query') # Patched app.gemini.Setting.query
    @patch('app.gemini.genai')    
    @patch('app.gemini.current_app') 
    def test_send_chat_model_from_config_fallback(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key_val = "test_gemini_key_for_chat_route_config"
        test_model_name_from_config = "model-from-config-py"
        
        mock_gemini_current_app.config = {
            'GEMINI_API_KEY': test_api_key_val, 
            'DEFAULT_GEMINI_MODEL': test_model_name_from_config
        }
        mock_gemini_current_app.logger = MagicMock()

        mock_gemini_setting_query.filter_by.return_value.first.return_value = None # Simulate Not in DB
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from config model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': 'Hello DM from config fallback test'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI test reply from config model")

        mock_gemini_setting_query.filter_by.assert_called_once_with(key='DEFAULT_GEMINI_MODEL')
        mock_gemini_genai_module.GenerativeModel.assert_called_once_with(
            model_name=test_model_name_from_config, 
            safety_settings=ANY
        )
        mock_gemini_genai_module.configure.assert_called_once_with(api_key=test_api_key_val)
        mock_gemini_current_app.logger.warning.assert_called_with(
            f"Using DEFAULT_GEMINI_MODEL '{test_model_name_from_config}' from config.py (not found in DB or DB value empty)."
        )

    @patch('app.gemini.Setting.query') # Patched app.gemini.Setting.query
    @patch('app.gemini.genai')    
    @patch('app.gemini.current_app') 
    def test_send_chat_model_from_hardcoded_fallback(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key_val = "test_gemini_key_for_chat_route_hardcoded"
        
        mock_gemini_current_app.config = {
            'GEMINI_API_KEY': test_api_key_val, 
            'DEFAULT_GEMINI_MODEL': None # Ensure not in app.config explicitly for this test path
        }
        mock_gemini_current_app.logger = MagicMock()
        
        mock_gemini_setting_query.filter_by.return_value.first.return_value = None # Simulate Not in DB
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from hardcoded model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': 'Hello DM from hardcoded fallback test'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI test reply from hardcoded model")

        mock_gemini_setting_query.filter_by.assert_called_once_with(key='DEFAULT_GEMINI_MODEL')
        mock_gemini_genai_module.GenerativeModel.assert_called_once_with(
            model_name="gemini-1.5-flash", # Hardcoded fallback
            safety_settings=ANY
        )
        mock_gemini_genai_module.configure.assert_called_once_with(api_key=test_api_key_val)
        mock_gemini_current_app.logger.error.assert_called_with("DEFAULT_GEMINI_MODEL not found in database or config.py.")
        mock_gemini_current_app.logger.warning.assert_called_with("Critial: Using hardcoded fallback Gemini model: gemini-1.5-flash.")


    def test_clear_character_progress(self):
        # 1. Setup Character with progress
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['_fresh'] = True

        char_to_clear = Character(
            name='ProgressChar',
            user_id=self.user.id,
            race_id=self.test_race.id,
            class_id=self.test_class.id, 
            level=5,
            strength=10, dexterity=10, constitution=14, 
            max_hp=30, 
            hp=20,
            adventure_log=json.dumps([{'sender': 'user', 'text': 'old log entry'}, {'sender': 'dm', 'text': 'dm reply'}]),
            speed=30, 
            current_proficiencies='{}', 
            current_equipment='{}' 
        )
        char_to_clear.known_spells.extend([self.cantrip, self.lvl2_spell])
        db.session.add(char_to_clear)
        db.session.commit()

        response = self.client.post(url_for('main.clear_character_progress', character_id=char_to_clear.id), follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        updated_char = Character.query.get(char_to_clear.id)
        self.assertIsNotNone(updated_char)
        self.assertEqual(updated_char.level, 1)
        self.assertEqual(json.loads(updated_char.adventure_log), [])
        self.assertEqual(updated_char.max_hp, 8) 
        self.assertEqual(updated_char.hp, updated_char.max_hp)
        self.assertEqual(len(updated_char.known_spells), 0)
        self.assertIn(b'Adventure progress cleared. Your character has been reset to level 1.', response.data)

    def test_roll_dice_from_sheet(self):
        roll_data_s1 = {
            "roll_type": "stat", "roll_name": "Strength Check",
            "dice_formula": "1d20", "modifier": 3
        }
        response_s1 = self.client.post(url_for('main.roll_dice_from_sheet'), json=roll_data_s1)
        self.assertEqual(response_s1.status_code, 200)
        data_s1 = response_s1.get_json()
        self.assertEqual(data_s1['roll_name'], "Strength Check")
        self.assertEqual(data_s1['total'], data_s1['subtotal'] + 3)

        # ... (other scenarios for roll_dice_from_sheet can be kept concise or as is) ...
        roll_data_s4a = {"dice_formula": "invalid", "modifier": 0}
        response_s4a = self.client.post(url_for('main.roll_dice_from_sheet'), json=roll_data_s4a)
        self.assertEqual(response_s4a.status_code, 400)
        self.assertIn("Invalid dice formula: invalid. Expected format 'XdY'", response_s4a.get_json()['error'])


    # --- NEW TEST CASES FOR GEMINI PROMPT AND REFACTORED CHAT ---
    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')         
    @patch('app.gemini.current_app')   
    def test_initial_gemini_prompt(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key = "test_key_initial_prompt"
        test_model_name = "test_model_initial_prompt"
        
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key, 'DEFAULT_GEMINI_MODEL': test_model_name}
        mock_gemini_current_app.logger = MagicMock()

        mock_db_setting_instance = MagicMock(spec=Setting)
        mock_db_setting_instance.value = test_model_name 
        mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="Initial AI reply")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance
        
        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': '__START_ADVENTURE__'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "Initial AI reply")
        mock_chat_instance.send_message.assert_called_once()
        actual_prompt = mock_chat_instance.send_message.call_args[0][0]

        self.assertIn(f"My character is named {self.character.name}", actual_prompt)
        self.assertIn("If the character description or background is 'Not specified' or very brief, please ask me some questions to help flesh out my character's history and motivations. Ask only one question at a time regarding this.", actual_prompt)
        self.assertIn("When a situation requires a dice roll, please ask me to make a specific roll", actual_prompt)
        self.assertIn("If I state I am making a roll that seems inappropriate for the current situation", actual_prompt) 
        self.assertIn("ask me to make the correct roll or to clarify my action", actual_prompt)
        self.assertIn("When you need information from me, please ask only one question at a time", actual_prompt)
        self.assertIn("You will also need to keep track of my character's experience points (XP). Inform me when I have gained enough XP to level up", actual_prompt)
        
        mock_gemini_genai_module.configure.assert_called_once_with(api_key=test_api_key)
        mock_gemini_genai_module.GenerativeModel.assert_called_once_with(
            model_name=test_model_name, 
            safety_settings=ANY 
        )

    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')         
    @patch('app.gemini.current_app')   
    def test_send_chat_message_refactored(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key = "test_key_refactored_chat"
        test_model_name = "test_model_refactored_chat"

        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key, 'DEFAULT_GEMINI_MODEL': test_model_name}
        mock_gemini_current_app.logger = MagicMock()
        
        mock_db_setting_instance = MagicMock(spec=Setting)
        mock_db_setting_instance.value = test_model_name
        mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance
        
        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mocked_ai_reply = "Refactored AI says hello!"
        mock_response_instance = MagicMock(text=mocked_ai_reply)
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance

        user_message_text = "Hello DM, this is a test of refactored chat."
        
        # Clear adventure log before this test for cleaner assertion
        self.character.adventure_log = json.dumps([])
        db.session.commit()

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': user_message_text}
        )

        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertIsNotNone(response_json)
        self.assertEqual(response_json.get('reply'), mocked_ai_reply)

        mock_gemini_genai_module.configure.assert_called_once_with(api_key=test_api_key)
        mock_gemini_genai_module.GenerativeModel.assert_called_once_with(
            model_name=test_model_name, 
            safety_settings=ANY
        )
        mock_model_instance.start_chat.assert_called_once_with(history=[]) # Since log was cleared
        mock_chat_instance.send_message.assert_called_once_with(user_message_text)

        updated_character = Character.query.get(self.character.id)
        log_entries = json.loads(updated_character.adventure_log)
        expected_log = [
            {"sender": "user", "text": user_message_text},
            {"sender": "dm", "text": mocked_ai_reply}
        ]
        self.assertEqual(log_entries, expected_log)

if __name__ == '__main__':
    unittest.main()
