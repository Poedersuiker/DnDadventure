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
        
        # Simulate login for the user for most tests
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
        test_api_key_val = "test_gemini_key_for_chat_route_db"
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key_val, 'DEFAULT_GEMINI_MODEL': 'db_should_override'}
        mock_gemini_current_app.logger = MagicMock()

        test_model_name_from_db = "model-from-db"
        mock_db_setting_instance = MagicMock(spec=Setting)
        mock_db_setting_instance.value = test_model_name_from_db
        mock_main_routes_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance

        mock_model_instance = MagicMock()
        mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="AI test reply from DB model")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance

        with patch('app.gemini.Setting.query') as mock_gemini_setting_query: 
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


    @patch('app.gemini.Setting.query') 
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

        mock_gemini_setting_query.filter_by.return_value.first.return_value = None 
        
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

    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')    
    @patch('app.gemini.current_app') 
    def test_send_chat_model_from_hardcoded_fallback(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key_val = "test_gemini_key_for_chat_route_hardcoded"
        
        mock_gemini_current_app.config = {
            'GEMINI_API_KEY': test_api_key_val, 
            'DEFAULT_GEMINI_MODEL': None 
        }
        mock_gemini_current_app.logger = MagicMock()
        
        mock_gemini_setting_query.filter_by.return_value.first.return_value = None 
        
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
            model_name="gemini-1.5-flash", 
            safety_settings=ANY
        )
        mock_gemini_genai_module.configure.assert_called_once_with(api_key=test_api_key_val)
        mock_gemini_current_app.logger.error.assert_called_with("DEFAULT_GEMINI_MODEL not found in database or config.py.")
        mock_gemini_current_app.logger.warning.assert_called_with("Critial: Using hardcoded fallback Gemini model: gemini-1.5-flash.")


    def test_clear_character_progress(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['_fresh'] = True

        char_to_clear = Character(
            name='ProgressChar', user_id=self.user.id, race_id=self.test_race.id,
            class_id=self.test_class.id, level=5, strength=10, dexterity=10, constitution=14, 
            max_hp=30, hp=20, adventure_log=json.dumps([{'text': 'old log'}]),
            speed=30, current_proficiencies='{}', current_equipment='{}' 
        )
        char_to_clear.known_spells.extend([self.cantrip, self.lvl2_spell])
        db.session.add(char_to_clear)
        db.session.commit()

        response = self.client.post(url_for('main.clear_character_progress', character_id=char_to_clear.id), follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        updated_char = Character.query.get(char_to_clear.id)
        self.assertEqual(updated_char.level, 1)
        self.assertEqual(json.loads(updated_char.adventure_log), [])
        self.assertEqual(updated_char.max_hp, 8) 
        self.assertEqual(updated_char.hp, 8)
        self.assertEqual(len(updated_char.known_spells), 0)
        self.assertIn(b'Adventure progress cleared.', response.data)

    def test_roll_dice_from_sheet(self):
        roll_data = {"dice_formula": "1d20", "modifier": 3, "roll_name": "STR Check"}
        response = self.client.post(url_for('main.roll_dice_from_sheet'), json=roll_data)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['total'], data['subtotal'] + 3)


    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')         
    @patch('app.gemini.current_app')   
    def test_initial_gemini_prompt(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key = "test_key_initial_prompt"
        test_model_name = "test_model_initial_prompt"
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key, 'DEFAULT_GEMINI_MODEL': test_model_name}
        mock_gemini_current_app.logger = MagicMock()
        mock_db_setting_instance = MagicMock(spec=Setting); mock_db_setting_instance.value = test_model_name 
        mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance
        mock_model_instance = MagicMock(); mock_chat_instance = MagicMock()
        mock_response_instance = MagicMock(text="Initial AI reply")
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance
        
        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': '__START_ADVENTURE__'}
        )
        self.assertEqual(response.status_code, 200)
        actual_prompt = mock_chat_instance.send_message.call_args[0][0]
        self.assertIn("If the character description or background is 'Not specified' or very brief", actual_prompt)
        self.assertIn("When a situation requires a dice roll, please ask me to make a specific roll", actual_prompt)
        self.assertIn("If I state I am making a roll that seems inappropriate", actual_prompt) 
        self.assertIn("When you need information from me, please ask only one question at a time", actual_prompt)
        self.assertIn("You will also need to keep track of my character's experience points (XP)", actual_prompt)

    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')         
    @patch('app.gemini.current_app')   
    def test_send_chat_message_refactored(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key = "test_key_refactored_chat"; test_model_name = "test_model_refactored_chat"
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key, 'DEFAULT_GEMINI_MODEL': test_model_name}
        mock_gemini_current_app.logger = MagicMock()
        mock_db_setting_instance = MagicMock(spec=Setting); mock_db_setting_instance.value = test_model_name
        mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance
        mock_model_instance = MagicMock(); mock_chat_instance = MagicMock()
        mocked_ai_reply = "Refactored AI says hello!"
        mock_response_instance = MagicMock(text=mocked_ai_reply)
        mock_chat_instance.send_message.return_value = mock_response_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance
        user_message_text = "Hello DM, test refactored chat."
        self.character.adventure_log = json.dumps([])
        db.session.commit()

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': user_message_text}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json().get('reply'), mocked_ai_reply)
        mock_chat_instance.send_message.assert_called_once_with(user_message_text)
        updated_character = Character.query.get(self.character.id)
        log_entries = json.loads(updated_character.adventure_log)
        self.assertEqual(log_entries, [{"sender": "user", "text": user_message_text}, {"sender": "dm", "text": mocked_ai_reply}])

    # --- NEW TEST FOR ADVENTURE PAGE INITIAL DM MESSAGE ---
    @patch('app.main.routes.geminiai') # Patching where geminiai is *called from* in the adventure route
    def test_adventure_page_loads_with_initial_dm_message_for_new_character(self, mock_geminiai_call_in_adventure_route):
        # 1. Setup a new user and character with an empty adventure_log
        new_user_adventure_test = User(id=2, email="new_adventure_user@example.com", google_id="new_adventure_user_google_id")
        db.session.add(new_user_adventure_test)
        db.session.commit()

        new_character_adventure_test = Character(
            id=2, name="NewAdventurer", user_id=new_user_adventure_test.id,
            race_id=self.test_race.id, class_id=self.test_class.id, level=1,
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10,
            hp=10, max_hp=10, armor_class=10, speed=30,
            adventure_log=None # Explicitly None for empty log
        )
        db.session.add(new_character_adventure_test)
        db.session.commit()

        # 2. Configure the mock for the geminiai call within the adventure route
        initial_dm_reply_text = "Welcome to your brand new adventure!"
        mock_geminiai_call_in_adventure_route.return_value = {'reply': initial_dm_reply_text}

        # 3. Simulate login for the new user
        with self.client.session_transaction() as sess:
            sess['user_id'] = new_user_adventure_test.id # Use the new user's ID
            sess['_fresh'] = True
        
        # 4. Make a GET request to the adventure page for the new character
        response = self.client.get(url_for('main.adventure', character_id=new_character_adventure_test.id))

        # 5. Assertions
        self.assertEqual(response.status_code, 200, "Adventure page should load successfully.")
        
        # Assert geminiai was called correctly by the adventure route
        mock_geminiai_call_in_adventure_route.assert_called_once_with(
            character_id=new_character_adventure_test.id,
            user_message="__START_ADVENTURE__",
            current_user_id=new_user_adventure_test.id
        )

        # Assert that the initial DM message is in the response data (rendered template)
        # The template prepends "DM: " so we check for that too.
        self.assertIn(f"DM: {initial_dm_reply_text}".encode('utf-8'), response.data, 
                      "Initial DM message not found in rendered page.")

        # Assert that the character's adventure_log in DB was updated
        updated_character_from_db = Character.query.get(new_character_adventure_test.id)
        self.assertIsNotNone(updated_character_from_db.adventure_log, 
                             "Adventure log should have been updated in the database.")
        
        log_entries = json.loads(updated_character_from_db.adventure_log)
        self.assertEqual(len(log_entries), 1, "Adventure log should contain one entry.")
        self.assertEqual(log_entries[0]['sender'], 'dm', "First message sender should be 'dm'.")
        self.assertEqual(log_entries[0]['text'], initial_dm_reply_text, 
                         "The text of the first message should be the initial DM reply.")

if __name__ == '__main__':
    unittest.main()
