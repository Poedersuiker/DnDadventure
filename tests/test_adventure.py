import unittest
from unittest.mock import patch, MagicMock
from tests.base_test import BaseTestCase
from app.models import User, Character, AdventureLogEntry
from app import db
from app.utils.dice_roller import roll_dice # For direct utility testing

# --- Mocks for Gemini Service ---
class MockGeminiResponse:
    def __init__(self, text):
        self.text = text
        self.parts = [] # Add parts attribute
        self.candidates = [MagicMock(finish_reason='STOP')] # Add candidates attribute


class MockGeminiModel:
    def generate_content(self, prompt_text):
        if "error_test_for_gemini" in prompt_text: # Specific trigger for errors
            raise Exception("Mock Gemini Service Error")
        return MockGeminiResponse("Mocked DM response based on: " + prompt_text[:70])

# --- Test Case ---
class AdventureTestCase(BaseTestCase):
    def setUp(self):
        super().setUp() # Call BaseTestCase.setUp
        self.login('testuser', 'password123')
        # Create a character for self.test_user
        self.character = Character(name='TestHero', race='Elf', character_class='Ranger', owner=self.test_user, strength=14, dexterity=15, constitution=13, intelligence=10, wisdom=12, charisma=8)
        db.session.add(self.character)
        db.session.commit()
        self.character_id = self.character.id

    # --- Test Dice Roller Utility Directly ---
    def test_roll_dice_valid_simple(self):
        result = roll_dice(sides=20, num_dice=1)
        self.assertIsInstance(result, dict)
        self.assertIn('rolls', result)
        self.assertIsInstance(result['rolls'], list)
        self.assertEqual(len(result['rolls']), 1)
        self.assertTrue(1 <= result['rolls'][0] <= 20)
        self.assertEqual(result['raw_total'], result['rolls'][0])
        self.assertEqual(result['modifier'], 0)
        self.assertEqual(result['total_with_modifier'], result['raw_total'])
        self.assertEqual(result['description'], "1d20")

    def test_roll_dice_valid_multiple_with_modifier(self):
        result = roll_dice(sides=6, num_dice=2, modifier=2)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result['rolls']), 2)
        self.assertTrue(1 <= result['rolls'][0] <= 6)
        self.assertTrue(1 <= result['rolls'][1] <= 6)
        self.assertEqual(result['raw_total'], sum(result['rolls']))
        self.assertEqual(result['modifier'], 2)
        self.assertEqual(result['total_with_modifier'], result['raw_total'] + 2)
        self.assertEqual(result['description'], "2d6+2")
        # Check range of total_with_modifier: min 2*1+2=4, max 2*6+2=14
        self.assertTrue(4 <= result['total_with_modifier'] <= 14)

    def test_roll_dice_valid_with_negative_modifier(self):
        result = roll_dice(sides=10, num_dice=1, modifier=-1)
        self.assertEqual(result['modifier'], -1)
        self.assertEqual(result['total_with_modifier'], result['raw_total'] - 1)
        self.assertEqual(result['description'], "1d10-1")

    def test_roll_dice_invalid_sides(self):
        with self.assertRaises(ValueError):
            roll_dice(sides=0, num_dice=1)

    def test_roll_dice_invalid_num_dice(self):
        with self.assertRaises(ValueError):
            roll_dice(sides=6, num_dice=0)

    # --- Test Character Action Rolls (Endpoint) ---
    def test_roll_action_skill_check_dexterity(self):
        payload = {'action_type': 'skill_check', 'stat_name': 'dexterity', 'skill_name': 'Acrobatics'}
        response = self.client.post(f'/character/adventure/{self.character_id}/roll_action', json=payload)
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('message', json_data)
        self.assertIn('roll_details', json_data)
        self.assertIn(f'{self.character.name} attempts a Acrobatic', json_data['message'])
        # Dexterity mod for 15 is +2
        expected_modifier = self.character.get_modifier_for_ability('dexterity') # Should be +2
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").first()
        self.assertIsNotNone(log_entry)
        self.assertIn('Acrobatics', log_entry.message)
        self.assertIn(str(expected_modifier), log_entry.roll_details) # Modifier should be in the details

    def test_roll_action_attack_roll(self):
        # Default attack uses strength (14 -> +2 mod)
        expected_modifier = self.character.get_modifier_for_ability('strength') # Should be +2
        response = self.client.post(f'/character/adventure/{self.character_id}/roll_action', json={'action_type': 'attack'})
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn(f'{self.character.name} attacks!', json_data['message'])
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").first()
        self.assertIsNotNone(log_entry)
        self.assertIn('attacks!', log_entry.message)

    def test_roll_action_saving_throw_constitution(self):
        expected_modifier = self.character.get_modifier_for_ability('constitution') # 13 -> +1
        payload = {'action_type': 'saving_throw', 'stat_name': 'constitution'}
        response = self.client.post(f'/character/adventure/{self.character_id}/roll_action', json=payload)
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn(f'{self.character.name} makes a Constitution saving throw!', json_data['message'])
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").first()
        self.assertIsNotNone(log_entry)
        self.assertIn('Constitution saving throw', log_entry.message)

    def test_roll_action_damage_roll(self):
        # 2d8+StrMod (Str 14 -> +2)
        expected_modifier = self.character.get_modifier_for_ability('strength')
        payload = {'action_type': 'damage', 'dice_type': 8, 'num_dice': 2, 'modifier': expected_modifier}
        response = self.client.post(f'/character/adventure/{self.character_id}/roll_action', json=payload)
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn(f'{self.character.name} deals damage!', json_data['message'])
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        self.assertIn('2d8', json_data['roll_details']['description'])
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").first()
        self.assertIsNotNone(log_entry)
        self.assertIn('deals damage!', log_entry.message)

    def test_roll_action_invalid_action_type(self):
        response = self.client.post(f'/character/adventure/{self.character_id}/roll_action', json={'action_type': 'fly_to_the_moon'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('Invalid action_type', json_data['error'])

    def test_roll_action_skill_check_missing_stat_name(self):
        response = self.client.post(f'/character/adventure/{self.character_id}/roll_action', json={'action_type': 'skill_check'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('Missing stat_name for skill_check', json_data['error'])

    # --- Test Chat Functionality (Mocking Gemini) ---
    @patch('app.services.gemini_service.get_gemini_model')
    def test_chat_with_mocked_gemini_success(self, mock_get_gemini_model_func):
        mock_model_instance = MockGeminiModel()
        mock_get_gemini_model_func.return_value = mock_model_instance

        response = self.client.post(f'/character/adventure/{self.character_id}/chat', json={'message': 'Hello DM, this is a test.'})
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('Mocked DM response based on: You are a Dungeon Master', json_data['reply']) # Check part of the mocked response

        log_entries = AdventureLogEntry.query.filter_by(character_id=self.character_id).order_by(AdventureLogEntry.timestamp.asc()).all()
        self.assertEqual(len(log_entries), 2)
        self.assertEqual(log_entries[0].entry_type, 'user_message')
        self.assertEqual(log_entries[0].message, 'Hello DM, this is a test.')
        self.assertEqual(log_entries[0].actor_name, self.character.name)
        self.assertEqual(log_entries[1].entry_type, 'gemini_response')
        self.assertIn('Mocked DM response', log_entries[1].message)
        self.assertEqual(log_entries[1].actor_name, 'DM')

    @patch('app.services.gemini_service.get_gemini_model')
    def test_chat_with_mocked_gemini_api_error(self, mock_get_gemini_model_func):
        mock_model_instance = MockGeminiModel()
        mock_get_gemini_model_func.return_value = mock_model_instance
        
        # Test the case where Gemini service itself raises an error
        response = self.client.post(f'/character/adventure/{self.character_id}/chat', json={'message': 'trigger error_test_for_gemini'})
        self.assertEqual(response.status_code, 500) # Route catches general Exception
        json_data = response.get_json()
        self.assertIn('An unexpected error occurred with the storyteller.', json_data['reply'])
        
        # Ensure user message was rolled back and not saved
        log_entries_count = AdventureLogEntry.query.filter_by(character_id=self.character_id).count()
        self.assertEqual(log_entries_count, 0)

    @patch('app.services.gemini_service.get_gemini_model')
    def test_chat_with_gemini_api_key_missing(self, mock_get_gemini_model_func):
        # Configure the mock to raise ValueError, simulating missing API key
        mock_get_gemini_model_func.side_effect = ValueError("GEMINI_API_KEY not set.")

        response = self.client.post(f'/character/adventure/{self.character_id}/chat', json={'message': 'Test without API key'})
        self.assertEqual(response.status_code, 503) # Service Unavailable
        json_data = response.get_json()
        self.assertIn('GEMINI_API_KEY not set.', json_data['reply'])

        # Ensure user message was rolled back
        log_entries_count = AdventureLogEntry.query.filter_by(character_id=self.character_id).count()
        self.assertEqual(log_entries_count, 0)

    # --- Test Adventure Log Loading ---
    @patch('app.services.gemini_service.get_gemini_model')
    def test_adventure_log_loading_on_page(self, mock_get_gemini_model_func):
        mock_model_instance = MockGeminiModel()
        mock_get_gemini_model_func.return_value = mock_model_instance

        # 1. Perform a chat action
        self.client.post(f'/character/adventure/{self.character_id}/chat', json={'message': 'First message from user'})
        
        # 2. Perform a roll action
        self.client.post(f'/character/adventure/{self.character_id}/roll_action', json={'action_type': 'skill_check', 'stat_name': 'wisdom', 'skill_name': 'Perception'})

        # 3. Reload the adventure page
        response = self.client.get(f'/character/adventure/{self.character_id}')
        self.assertEqual(response.status_code, 200)
        
        # Check that the HTML contains the messages from the log
        response_text = response.get_data(as_text=True)
        self.assertIn('First message from user', response_text)
        self.assertIn('Mocked DM response based on: You are a Dungeon Master', response_text) # From Gemini mock
        self.assertIn(f'{self.character.name} attempts a Perception check.', response_text) # From action roll

        # Check the number of log entries in HTML (basic check for presence)
        # This depends on how formatLogEntry structures them.
        # Example: assuming each log entry <p> has class 'log-entry'
        self.assertTrue(response_text.count('class="log-entry user_message"') >= 1)
        self.assertTrue(response_text.count('class="log-entry gemini_response"') >= 1)
        self.assertTrue(response_text.count('class="log-entry action_roll"') >= 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
