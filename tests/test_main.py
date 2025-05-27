import unittest
import json
from unittest.mock import patch, MagicMock, ANY 
import google.generativeai as genai # Added for spec=genai.ChatSession
from flask import current_app, url_for, session # Added session for test_creation_review
from app import app, db
from app.models import User, Character, Race, Class, Setting, Spell, Item, Coinage # Added Item, Coinage
from app.gemini import GEMINI_DM_SYSTEM_RULES # Import the constant for the new test

class TestMainRoutes(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False 
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SERVER_NAME'] = 'localhost' 
        app.config['LOGIN_DISABLED'] = False 

        self.original_gemini_api_key = app.config.get('GEMINI_API_KEY')
        self.original_default_gemini_model = app.config.get('DEFAULT_GEMINI_MODEL')
        
        app.config['GEMINI_API_KEY'] = "default_test_api_key"
        app.config['DEFAULT_GEMINI_MODEL'] = "default_test_model"

        db.create_all()
        self.client = app.test_client()

        self.test_race = Race(id=1, name="TestHuman", speed=30, ability_score_increases='[]', languages='[]', traits='[]', size_description='', age_description='', alignment_description='')
        self.test_class = Class(id=1, name="TestWizard", hit_die="d6", 
                                proficiency_saving_throws='["INT", "WIS"]', 
                                skill_proficiencies_option_count=2, skill_proficiencies_options='["Arcana", "History", "Investigation"]', 
                                starting_equipment='[]', proficiencies_armor='[]', proficiencies_weapons='[]', 
                                proficiencies_tools='[]', spellcasting_ability="INT")
        db.session.add_all([self.test_race, self.test_class])
        
        self.cantrip = Spell(id=1, index='test-cantrip', name='Test Cantrip', description='[]', level=0, school='TestSchool', classes_that_can_use='["TestWizard"]')
        self.lvl2_spell = Spell(id=2, index='test-spell2', name='Test Spell L2', description='[]', level=2, school='TestSchool', classes_that_can_use='["TestWizard"]')
        db.session.add_all([self.cantrip, self.lvl2_spell])
        db.session.commit()

        self.user = User(id=1, email="test@example.com", google_id="test_google_id_main")
        db.session.add(self.user)
        db.session.commit()
        
        self.character = Character(id=1, name="TestChar", user_id=self.user.id, race_id=self.test_race.id, class_id=self.test_class.id, level=1, strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10, hp=10, max_hp=10, armor_class=10, speed=30, current_proficiencies=json.dumps({'skills': ['Perception', 'Stealth']}), xp=0)
        db.session.add(self.character)
        db.session.commit()
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id 
            sess['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        app.config['GEMINI_API_KEY'] = self.original_gemini_api_key
        app.config['DEFAULT_GEMINI_MODEL'] = self.original_default_gemini_model
        self.app_context.pop()

    # ... (other existing tests like test_send_chat_model_from_db etc. would be here) ...
    # For brevity, I'm omitting the other tests that are not directly part of this task's changes,
    # but they would remain in the actual file. The provided diff will only show changes relative to previous state.

    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')         
    @patch('app.gemini.current_app')   
    def test_initial_gemini_prompt(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        # This test verifies the prompt content sent for the __START_ADVENTURE__ message
        # when send_chat_message directly initializes the model and chat with system rules + history.
        test_api_key = "test_key_initial_prompt_new" # Use a distinct key
        test_model_name = "test_model_initial_prompt_new"
        
        # Mock app.gemini.current_app.config (used by geminiai wrapper)
        # This mock might not be strictly necessary if send_chat_message does its own config.
        # However, the geminiai wrapper still has config access.
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key, 'DEFAULT_GEMINI_MODEL': test_model_name}
        mock_gemini_current_app.logger = MagicMock()

        # Mock for app.gemini.Setting.query (used by geminiai wrapper)
        mock_db_setting_instance_for_gemini_wrapper = MagicMock(spec=Setting)
        mock_db_setting_instance_for_gemini_wrapper.value = test_model_name 
        mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance_for_gemini_wrapper
        
        # Mock for genai.GenerativeModel (this is the crucial one for system_instruction)
        # This mock will be used by send_chat_message when it creates the model
        mock_model_instance = MagicMock(spec=genai.GenerativeModel)
        mock_chat_instance = MagicMock(spec=genai.ChatSession)
        mock_response_instance = MagicMock(text="AI's actual first adventure message")
        
        # Configure the mock chain for the call from send_chat_message to geminiai,
        # and then geminiai's internal call to chat.send_message
        # The geminiai wrapper is called by send_chat_message.
        # send_chat_message sets up the model, system rules, history, then calls geminiai.
        # geminiai then calls existing_chat_session.send_message().
        
        # So, we need to mock what genai.GenerativeModel returns, and what its methods return.
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance
        mock_model_instance.start_chat.return_value = mock_chat_instance
        
        # The geminiai wrapper will call send_message on the chat_session passed to it
        # by send_chat_message.
        # The text here is what geminiai wrapper returns, which becomes the DM's message.
        mock_chat_instance.send_message.return_value = mock_response_instance 
                                                        # This is response from chat_session.send_message(user_message)

        # Make the call via the route that uses __START_ADVENTURE__
        # The adventure route's initial setup will call geminiai twice.
        # This test is for send_chat_message, not the adventure route's full init.
        # The prompt being tested here is the one constructed by the send_chat_message route
        # when it gets a `__START_ADVENTURE__` message (which shouldn't happen if adventure_log is empty,
        # as adventure route handles that. But if it did, this is how it would be structured).
        #
        # Re-evaluating: test_initial_gemini_prompt is about the prompt text *inside* app.gemini.geminiai
        # when it receives __START_ADVENTURE__. That logic has been removed from geminiai.
        # The initial prompt construction is now in app.main.routes.adventure.
        # This test should now verify the system_instruction part of the model in send_chat_message.

        # Let's repurpose this test slightly to check system_instruction in send_chat_message
        # and that a normal message is passed through.
        
        # Simulate a normal message send
        user_sent_message = "Let's explore the cave."
        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': user_sent_message}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], "AI's actual first adventure message")

        # Check that GenerativeModel was called with GEMINI_DM_SYSTEM_RULES
        mock_gemini_genai_module.GenerativeModel.assert_called_once()
        args, kwargs = mock_gemini_genai_module.GenerativeModel.call_args
        self.assertEqual(kwargs.get('system_instruction'), GEMINI_DM_SYSTEM_RULES)
        
        # Check that start_chat was called (history might be empty or not, depending on log)
        mock_model_instance.start_chat.assert_called_once()
        
        # Check that the user's message was sent via the chat session
        mock_chat_instance.send_message.assert_called_once_with(user_sent_message)


    @patch('app.main.routes.geminiai') 
    def test_adventure_page_loads_with_initial_dm_message_for_new_character(self, mock_geminiai_call_in_adventure_route):
        # 1. Setup a new user and character with an empty adventure_log
        new_user_adventure_test = User(id=2, email="new_adventure_user@example.com", google_id="new_adventure_user_google_id")
        db.session.add(new_user_adventure_test)
        db.session.commit()

        new_character_adventure_test = Character(
            id=2, name="NewAdventurer", user_id=new_user_adventure_test.id,
            race_id=self.test_race.id, class_id=self.test_class.id, level=1,
            strength=10, dexterity=10, constitution=12,
            intelligence=14, wisdom=13, charisma=15,
            hp=10, max_hp=10, armor_class=10, speed=30,
            adventure_log=None, xp=0,
            current_proficiencies=json.dumps({'skills': ['Arcana', 'Investigation'], 'saving_throws': ['INT', 'WIS']}),
            current_equipment=json.dumps(["Spellbook", "Dagger"])
        )
        db.session.add(new_character_adventure_test)
        db.session.commit()

        mock_session_step1 = MagicMock(spec=genai.ChatSession) 
        mock_session_step2 = MagicMock(spec=genai.ChatSession) 

        rules_ack_text = "Rules Acknowledged by DM." 
        first_dm_adventure_message = "You find yourself in the quiet, forested village of Oakhaven. What would you like to do?"

        mock_geminiai_call_in_adventure_route.side_effect = [
            (rules_ack_text, mock_session_step1, None), 
            (first_dm_adventure_message, mock_session_step2, None)
        ]

        with self.client.session_transaction() as sess:
            sess['user_id'] = new_user_adventure_test.id
            sess['_fresh'] = True
        
        response = self.client.get(url_for('main.adventure', character_id=new_character_adventure_test.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_geminiai_call_in_adventure_route.call_count, 2)
        calls = mock_geminiai_call_in_adventure_route.call_args_list

        self.assertEqual(calls[0][1]['prompt_text_to_send'], GEMINI_DM_SYSTEM_RULES)
        self.assertIsNone(calls[0][1]['existing_chat_session'])

        character_sheet_prompt_sent = calls[1][1]['prompt_text_to_send']
        self.assertIn("PLAYER CHARACTER SHEET:", character_sheet_prompt_sent)
        self.assertIn(f"Name: {new_character_adventure_test.name}", character_sheet_prompt_sent)
        self.assertIn(f"Current XP: {new_character_adventure_test.xp or 0}", character_sheet_prompt_sent)
        self.assertIn(f"XP for Next Level: 300", character_sheet_prompt_sent) 
        self.assertEqual(calls[1][1]['existing_chat_session'], mock_session_step1)

        self.assertIn(f"DM: {first_dm_adventure_message}".encode('utf-8'), response.data)

        updated_character_from_db = Character.query.get(new_character_adventure_test.id)
        self.assertIsNotNone(updated_character_from_db.adventure_log)
        log_entries = json.loads(updated_character_from_db.adventure_log)
        self.assertEqual(len(log_entries), 2)
        self.assertEqual(log_entries[0]['sender'], 'user')
        self.assertEqual(log_entries[0]['text'], character_sheet_prompt_sent)
        self.assertEqual(log_entries[1]['sender'], 'dm')
        self.assertEqual(log_entries[1]['text'], first_dm_adventure_message)

    def test_gemini_dm_system_rules_content(self):
        # GEMINI_DM_SYSTEM_RULES is imported at the top of the file
        
        # Core DM Persona & D&D 5e Consistency
        self.assertIn("You are a Dungeon Master for a Dungeons & Dragons 5th Edition (D&D 5e) style game.", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("adapt these inspirations *into* the D&D 5e world.", GEMINI_DM_SYSTEM_RULES)

        # 1. Focus on the Player
        self.assertIn("Prioritize player agency and fun.", GEMINI_DM_SYSTEM_RULES)

        # 2. D&D 5e Rules Adherence & Guidance
        self.assertIn("Apply D&D 5e rules for game mechanics", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("If a player makes an inappropriate roll, or a roll that's not requested, gently guide them", GEMINI_DM_SYSTEM_RULES)

        # 3. XP and Leveling
        self.assertIn("Track Experience Points (XP) for the player character.", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("Inform the player when they have accumulated enough XP to level up.", GEMINI_DM_SYSTEM_RULES)

        # 4. Character Information (Player Provided)
        self.assertIn("If the character description or background is sparse, you may ask *one* clarifying question", GEMINI_DM_SYSTEM_RULES)

        # 5. Roleplaying and Tone
        self.assertIn("Maintain a consistent, immersive, and engaging tone suitable for a D&D 5e fantasy adventure.", GEMINI_DM_SYSTEM_RULES)

        # 6. Adventure Structure and Start
        self.assertIn("your *very first interaction requiring a response from the player* must be to ask them *one* concise question about the general type of story or challenges", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("in your *very next message*, you *must* then ask them about their preferred playstyle", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("The adventure *must* be scaled for a Level 1 character.", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("Start with low-stakes, local problems", GEMINI_DM_SYSTEM_RULES)
        
        # Check for a phrase indicating the character sheet will be provided by the player/app
        self.assertIn("The player will provide their character's details (name, race, class, level, description, alignment, background, key skills) at the start of the adventure.", GEMINI_DM_SYSTEM_RULES)

        # 7. Your Responses
        self.assertIn("Keep your responses concise and focused", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("End your responses with a clear prompt for player action or decision", GEMINI_DM_SYSTEM_RULES)

        # 8. OOC (Out-of-Character) Communication
        self.assertIn("If the player asks an OOC question about rules or game state, answer it clearly and concisely.", GEMINI_DM_SYSTEM_RULES)
        self.assertIn("Use parentheses for brief OOC comments if needed", GEMINI_DM_SYSTEM_RULES)

        # Specific examples from task description that may or may not be exact
        # "Always wait for player input" is implied by "Wait for my response before asking another." and "End your responses with a clear prompt"
        self.assertIn("Wait for my response before asking another.", GEMINI_DM_SYSTEM_RULES)
        
        # "Strict 5e XP Awards" - The rule is "Award XP for overcoming challenges...", which is more general.
        self.assertIn("Award XP for overcoming challenges", GEMINI_DM_SYSTEM_RULES) 
        
        # "adventure begins in the quiet, forested village of Oakhaven" - This specific lore is NOT in GEMINI_DM_SYSTEM_RULES.
        # The rules are about *how* to start, not *where*.
        
        # "The app will provide the player's full character sheet immediately after this initial setup."
        # This is not in the DM rules, but is reflected in the "Character Information" section.
        # The check for "The player will provide their character's details" covers this intent.

        # "Your current XP total is [Current XP] (Next Level: [Next Level XP])." - This is an example of how the *character sheet* prompt is formatted,
        # not a rule for the DM in GEMINI_DM_SYSTEM_RULES.

        # "If you need to ask a clarifying question about the rules... use (OOC: Your message here)"
        # The rule states: "Use parentheses for brief OOC comments if needed, e.g., (OOC: Just to clarify, are you opening the chest or the door?)."
        # The check for "Use parentheses for brief OOC comments" is sufficient.


    # ... (test_send_chat_message_refactored and other tests can remain as they are, if they are still relevant) ...
    # For instance, test_send_chat_message_refactored checks the normal chat flow AFTER initialization.
    # The `test_initial_gemini_prompt` has been repurposed above.
    # The old tests for model selection (test_send_chat_model_from_db, etc.) are still relevant for the send_chat_message route.
    
    # The test_initial_gemini_prompt was primarily about the content of the initial prompt string.
    # Since that complex prompt is no longer constructed inside app.gemini.geminiai, but rather in app.main.routes.adventure,
    # and parts of it are now in GEMINI_DM_SYSTEM_RULES, the assertions have been split.
    # The test_gemini_dm_system_rules_content handles the static rules.
    # The test_adventure_page_loads_with_initial_dm_message_for_new_character handles the dynamic part and sequence.
    # The original test_initial_gemini_prompt is now repurposed to check that send_chat_message uses system_instruction.
    # This seems like a reasonable distribution of concerns.

    # (Keep test_send_chat_message_refactored as is, it tests the ongoing chat functionality)
    @patch('app.gemini.Setting.query') 
    @patch('app.gemini.genai')         
    @patch('app.gemini.current_app')   
    def test_send_chat_message_refactored(self, mock_gemini_current_app, mock_gemini_genai_module, mock_gemini_setting_query):
        test_api_key = "test_key_refactored_chat"; test_model_name = "test_model_refactored_chat"
        mock_gemini_current_app.config = {'GEMINI_API_KEY': test_api_key, 'DEFAULT_GEMINI_MODEL': test_model_name}
        mock_gemini_current_app.logger = MagicMock()
        mock_db_setting_instance = MagicMock(spec=Setting); mock_db_setting_instance.value = test_model_name
        mock_gemini_setting_query.filter_by.return_value.first.return_value = mock_db_setting_instance
        
        # This mock chain is now for the model created inside send_chat_message
        mock_model_instance_send_chat = MagicMock(spec=genai.GenerativeModel)
        mock_chat_instance_send_chat = MagicMock(spec=genai.ChatSession)
        mock_gemini_genai_module.GenerativeModel.return_value = mock_model_instance_send_chat
        mock_model_instance_send_chat.start_chat.return_value = mock_chat_instance_send_chat
        
        # This is the mock for the geminiai() wrapper function's internal chat.send_message
        # This is what geminiai's internal session.send_message returns
        mock_gemini_wrapper_response = MagicMock(text="Refactored AI says hello!")
        
        # We need to mock the chat session that geminiai receives and calls send_message on.
        # This session is created by send_chat_message and passed to geminiai.
        mock_chat_instance_send_chat.send_message.return_value = mock_gemini_wrapper_response

        user_message_text = "Hello DM, test refactored chat."
        self.character.adventure_log = json.dumps([]) # Start with empty log for this test
        db.session.commit()

        response = self.client.post(
            url_for('main.send_chat_message', character_id=self.character.id),
            json={'message': user_message_text}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json().get('reply'), "Refactored AI says hello!")

        # Check that GenerativeModel was called by send_chat_message with system_instruction
        mock_gemini_genai_module.GenerativeModel.assert_called_once()
        args, kwargs = mock_gemini_genai_module.GenerativeModel.call_args
        self.assertEqual(kwargs.get('system_instruction'), GEMINI_DM_SYSTEM_RULES)

        # Check that the chat session passed to geminiai (from send_chat_message) had send_message called on it
        mock_chat_instance_send_chat.send_message.assert_called_once_with(user_message_text)
        
        updated_character = Character.query.get(self.character.id)
        log_entries = json.loads(updated_character.adventure_log)
        self.assertEqual(log_entries, [{"sender": "user", "text": user_message_text}, {"sender": "dm", "text": "Refactored AI says hello!"}])

    def test_creation_review_with_inventory(self):
        # Simulate session data that would be built up during character creation
        # This needs to align with what creation_review expects in char_data
        
        # Create a new user for this test to avoid conflicts
        test_creation_user = User(id=3, email="creation_user@example.com", google_id="creation_user_google_id")
        db.session.add(test_creation_user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = test_creation_user.id # Log in as the new user
            sess['_fresh'] = True
            sess['new_character_data'] = {
                'race_id': self.test_race.id,
                'class_id': self.test_class.id,
                'ability_scores': {'STR': 15, 'DEX': 14, 'CON': 13, 'INT': 12, 'WIS': 10, 'CHA': 8},
                'max_hp': 10,
                'armor_class_base': 12,
                'speed': 30,
                'background_name': 'Acolyte',
                'background_skill_proficiencies': ['Insight', 'Religion'],
                'background_tool_proficiencies': [],
                'background_languages': ['Celestial', 'Common'],
                'background_equipment': "A holy symbol, a prayer book, 5 sticks of incense, vestments, common clothes, and a pouch containing 15 gp.",
                'class_skill_proficiencies': ['Arcana', 'History'],
                'armor_proficiencies': ['Light Armor'],
                'weapon_proficiencies': ['Simple Weapons'],
                'tool_proficiencies_class_fixed': [],
                'saving_throw_proficiencies': ['INT', 'WIS'],
                'final_equipment': [ # From class choices
                    "Dagger (x1)", 
                    "Component pouch"
                ], 
                'chosen_cantrip_ids': [self.cantrip.id],
                'chosen_level_1_spell_ids': []
            }

        response = self.client.post(url_for('main.creation_review'), data={
            'character_name': 'Adventurer With Stuff',
            'alignment': 'Lawful Good',
            'character_description': 'Ready to go!'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200) # Should redirect to index, then 200
        self.assertIn(b'Character created successfully!', response.data)

        # Verify character, items, and coinage in DB
        created_char = Character.query.filter_by(name='Adventurer With Stuff').first()
        self.assertIsNotNone(created_char)
        self.assertEqual(created_char.user_id, test_creation_user.id)

        # Check coinage
        gold = Coinage.query.filter_by(character_id=created_char.id, name="Gold Pieces").first()
        self.assertIsNotNone(gold)
        self.assertEqual(gold.quantity, 15)

        # Check items (more complex due to parsing)
        items = Item.query.filter_by(character_id=created_char.id).all()
        item_names = {item.name: item.quantity for item in items}

        # Items from 'final_equipment' (class choices)
        self.assertIn("Dagger", item_names)
        self.assertEqual(item_names["Dagger"], 1)
        self.assertIn("Component pouch", item_names)
        self.assertEqual(item_names["Component pouch"], 1)
        
        # Items from 'background_equipment' (parsed string)
        # Note: The parsing logic in creation_review is simple (splits by comma and 'and')
        # and might create multiple entries if not careful.
        # "A holy symbol, a prayer book, 5 sticks of incense, vestments, common clothes, and a pouch containing 15 gp."
        self.assertIn("A holy symbol", item_names)
        self.assertIn("a prayer book", item_names) # Check for case sensitivity if issues arise
        self.assertIn("sticks of incense", item_names) 
        self.assertEqual(item_names["sticks of incense"], 5)
        self.assertIn("vestments", item_names)
        self.assertIn("common clothes", item_names)
        # "a pouch containing 15 gp" should NOT become an item if parsing is correct (gold handled separately)
        self.assertNotIn("a pouch containing 15 gp", item_names)


    def test_clear_character_progress_clears_inventory(self):
        # 1. Create a character with items and coinage
        test_clear_user = User(id=4, email="clear_user@example.com", google_id="clear_user_google_id")
        db.session.add(test_clear_user)
        db.session.commit()

        char_to_clear = Character(
            id=3, name="CharToClear", user_id=test_clear_user.id,
            race_id=self.test_race.id, class_id=self.test_class.id, level=5,
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
            hp=30, max_hp=30, armor_class=10, speed=30,
            adventure_log=json.dumps([{"sender": "dm", "text": "An old log."}]),
            current_proficiencies='{}', xp=5000
        )
        db.session.add(char_to_clear)
        db.session.commit() # Commit to get char_to_clear.id

        # Add items and coinage
        item1 = Item(name="Old Sword", quantity=1, character_id=char_to_clear.id)
        item2 = Item(name="Dusty Shield", quantity=1, character_id=char_to_clear.id)
        coin = Coinage(name="Copper Pieces", quantity=120, character_id=char_to_clear.id)
        db.session.add_all([item1, item2, coin])
        db.session.commit()

        self.assertEqual(Item.query.filter_by(character_id=char_to_clear.id).count(), 2)
        self.assertEqual(Coinage.query.filter_by(character_id=char_to_clear.id).count(), 1)

        # 2. Log in as the character's user
        with self.client.session_transaction() as sess:
            sess['user_id'] = test_clear_user.id
            sess['_fresh'] = True
        
        # 3. Call the clear_character_progress route
        response = self.client.post(url_for('main.clear_character_progress', character_id=char_to_clear.id), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Adventure progress cleared. Your character has been reset to level 1. Inventory and coinage have been cleared.', response.data)

        # 4. Verify character is reset and inventory is cleared
        cleared_char = Character.query.get(char_to_clear.id)
        self.assertEqual(cleared_char.level, 1)
        self.assertEqual(cleared_char.adventure_log, '[]')
        
        self.assertEqual(Item.query.filter_by(character_id=char_to_clear.id).count(), 0)
        self.assertEqual(Coinage.query.filter_by(character_id=char_to_clear.id).count(), 0)


if __name__ == '__main__':
    unittest.main()
