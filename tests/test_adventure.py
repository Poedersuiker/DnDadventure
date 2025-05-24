import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup 
import json # Added import for json
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

    def _get_csrf_token(self):
        """Helper method to get a CSRF token."""
        # Fetch from a page that requires login and renders a form, like create_character,
        # to ensure session stability.
        response = self.client.get('/character/create_character') 
        self.assertEqual(response.status_code, 200, "Failed to get /character/create_character page for CSRF token")
        soup = BeautifulSoup(response.data, 'html.parser')
        csrf_token_tag = soup.find('input', {'name': 'csrf_token'})
        self.assertIsNotNone(csrf_token_tag, "CSRF token input tag not found on /test_csrf page")
        self.assertIn('value', csrf_token_tag.attrs, "CSRF token input tag has no value attribute")
        return csrf_token_tag['value']

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
    def test_roll_skill_check_acrobatics_dexterity(self): # Renamed for clarity
        csrf_token = self._get_csrf_token()
        # Payload for new specific endpoint might be empty if all info is in URL
        response = self.client.post(
            f'/character/adventure/{self.character_id}/roll_skill_check/acrobatics/dexterity', 
            json={}, # Empty payload
            headers={'X-CSRFToken': csrf_token}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('message', json_data)
        self.assertIn('roll_details', json_data)
        # Message format from _log_and_respond: "{name} attempts a {action} check: {total} ({desc})"
        self.assertIn(f'{self.character.name} attempts a Acrobatics check:', json_data['message'])
        expected_modifier = self.character.get_skill_bonus('acrobatics') # Uses combined skill bonus
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
        self.assertIsNotNone(log_entry)
        self.assertIn('Acrobatics check', log_entry.message) # Check action name in log
        roll_details_json = json.loads(log_entry.roll_details)
        self.assertEqual(roll_details_json['modifier'], expected_modifier)


    def test_roll_attack_roll_endpoint(self): # Renamed for clarity
        csrf_token = self._get_csrf_token()
        # Default attack: Str (14 -> +2 mod) + Prof (L1 -> +2) = +4
        expected_modifier = self.character.get_modifier_for_ability('strength') + self.character.get_proficiency_bonus()
        response = self.client.post(
            f'/character/adventure/{self.character_id}/roll_attack', 
            json={}, # Empty payload for this specific route
            headers={'X-CSRFToken': csrf_token}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        # Message format: "{name} attacks! Roll: {total} ({desc})"
        self.assertIn(f'{self.character.name} attacks! Roll:', json_data['message'])
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
        self.assertIsNotNone(log_entry)
        self.assertIn('attacks!', log_entry.message)
        roll_details_json = json.loads(log_entry.roll_details)
        self.assertEqual(roll_details_json['modifier'], expected_modifier)

    def test_roll_saving_throw_constitution_endpoint(self): # Renamed for clarity
        csrf_token = self._get_csrf_token()
        # Constitution Save: Con (13 -> +1 mod). Ranger L1 not proficient in CON saves.
        # Ranger saves: Strength, Dexterity.
        # So, modifier should be just Con_mod.
        expected_modifier = self.character.get_saving_throw_bonus('constitution') 
        response = self.client.post(
            f'/character/adventure/{self.character_id}/roll_saving_throw/constitution', 
            json={}, # Empty payload
            headers={'X-CSRFToken': csrf_token}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        # Message format: "{name} makes a {action}: {total} ({desc})"
        self.assertIn(f'{self.character.name} makes a Constitution Save:', json_data['message'])
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
        self.assertIsNotNone(log_entry)
        self.assertIn('Constitution Save', log_entry.message)
        roll_details_json = json.loads(log_entry.roll_details)
        self.assertEqual(roll_details_json['modifier'], expected_modifier)


    def test_roll_damage_roll_endpoint(self): # Renamed for clarity
        csrf_token = self._get_csrf_token()
        # Payload for damage: num_dice, dice_type, modifier_stat
        # Test with 2d8 + STR mod (Strength 14 -> +2)
        expected_modifier = self.character.get_modifier_for_ability('strength')
        payload = {'num_dice': 2, 'dice_type': 8, 'modifier_stat': 'strength'}
        response = self.client.post(
            f'/character/adventure/{self.character_id}/roll_damage', 
            json=payload,
            headers={'X-CSRFToken': csrf_token}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        # Message format: "{name} deals damage! Roll: {total} ({desc})"
        self.assertIn(f'{self.character.name} deals damage! Roll:', json_data['message'])
        self.assertEqual(json_data['roll_details']['modifier'], expected_modifier)
        self.assertIn('2d8', json_data['roll_details']['description']) # Should include bonus like 2d8+2
        self.assertIn(f"+{expected_modifier}" if expected_modifier > 0 else str(expected_modifier), json_data['roll_details']['description'])
        
        log_entry = AdventureLogEntry.query.filter_by(character_id=self.character_id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
        self.assertIsNotNone(log_entry)
        self.assertIn('deals damage!', log_entry.message)
        roll_details_json = json.loads(log_entry.roll_details)
        self.assertEqual(roll_details_json['modifier'], expected_modifier)

    # These tests might be obsolete or need to target new specific validation if applicable.
    # For example, trying to roll a skill_check with an invalid skill_name or ability_name
    # against the new specific endpoints.
    # def test_roll_action_invalid_action_type(self):
    #     csrf_token = self._get_csrf_token()
    #     response = self.client.post(
    #         f'/character/adventure/{self.character_id}/roll_action', 
    #         json={'action_type': 'fly_to_the_moon'},
    #         headers={'X-CSRFToken': csrf_token}
    #     )
    #     self.assertEqual(response.status_code, 400) # This old endpoint would be 404 now
    #     json_data = response.get_json()
    #     self.assertIn('Invalid action_type', json_data['error'])

    # def test_roll_action_skill_check_missing_stat_name(self):
    #     csrf_token = self._get_csrf_token()
    #     response = self.client.post(
    #         f'/character/adventure/{self.character_id}/roll_action', 
    #         json={'action_type': 'skill_check'}, # This would be missing ability and skill from URL
    #         headers={'X-CSRFToken': csrf_token}
    #     )
    #     self.assertEqual(response.status_code, 400) # This old endpoint would be 404 now
    #     json_data = response.get_json()
    #     self.assertIn('Missing stat_name for skill_check', json_data['error'])

    # --- Test Chat Functionality (Mocking Gemini) ---
    @patch('app.services.gemini_service.get_gemini_model')
    def test_chat_with_mocked_gemini_success(self, mock_get_gemini_model_func):
        csrf_token = self._get_csrf_token()
        mock_model_instance = MockGeminiModel()
        mock_get_gemini_model_func.return_value = mock_model_instance

        response = self.client.post(
            f'/character/adventure/{self.character_id}/chat', 
            json={'message': 'Hello DM, this is a test.'},
            headers={'X-CSRFToken': csrf_token}
        )
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
        csrf_token = self._get_csrf_token()
        mock_model_instance = MockGeminiModel()
        mock_get_gemini_model_func.return_value = mock_model_instance
        
        # Test the case where Gemini service itself raises an error
        response = self.client.post(
            f'/character/adventure/{self.character_id}/chat', 
            json={'message': 'trigger error_test_for_gemini'},
            headers={'X-CSRFToken': csrf_token}
        )
        self.assertEqual(response.status_code, 500) # Route catches general Exception
        json_data = response.get_json()
        self.assertIn('An unexpected error occurred with the storyteller.', json_data['reply'])
        
        # Ensure user message was rolled back and not saved
        log_entries_count = AdventureLogEntry.query.filter_by(character_id=self.character_id).count()
        self.assertEqual(log_entries_count, 0)

    @patch('app.services.gemini_service.get_gemini_model')
    def test_chat_with_gemini_api_key_missing(self, mock_get_gemini_model_func):
        csrf_token = self._get_csrf_token()
        # Configure the mock to raise ValueError, simulating missing API key
        mock_get_gemini_model_func.side_effect = ValueError("GEMINI_API_KEY not set.")

        response = self.client.post(
            f'/character/adventure/{self.character_id}/chat', 
            json={'message': 'Test without API key'},
            headers={'X-CSRFToken': csrf_token}
        )
        self.assertEqual(response.status_code, 503) # Service Unavailable
        json_data = response.get_json()
        self.assertIn('GEMINI_API_KEY not set.', json_data['reply'])

        # Ensure user message was rolled back
        log_entries_count = AdventureLogEntry.query.filter_by(character_id=self.character_id).count()
        self.assertEqual(log_entries_count, 0)

    # --- Test Adventure Log Loading ---
    @patch('app.services.gemini_service.get_gemini_model')
    def test_adventure_log_loading_on_page(self, mock_get_gemini_model_func):
        csrf_token = self._get_csrf_token()
        mock_model_instance = MockGeminiModel()
        mock_get_gemini_model_func.return_value = mock_model_instance

        # 1. Perform a chat action
        self.client.post(
            f'/character/adventure/{self.character_id}/chat', 
            json={'message': 'First message from user'},
            headers={'X-CSRFToken': csrf_token}
        )
        
        # 2. Perform a roll action (using a new specific endpoint)
        self.client.post(
            f'/character/adventure/{self.character_id}/roll_skill_check/perception/wisdom', 
            json={}, # Empty payload
            headers={'X-CSRFToken': csrf_token} 
        )

        # 3. Reload the adventure page
        response = self.client.get(f'/character/adventure/{self.character_id}')
        self.assertEqual(response.status_code, 200)
        
        # Check that the HTML contains the messages from the log
        response_text = response.get_data(as_text=True)
        self.assertIn('First message from user', response_text)
        self.assertIn('Mocked DM response based on: You are a Dungeon Master', response_text) # From Gemini mock
        self.assertIn(f'{self.character.name} attempts a Perception check:', response_text) # Message from new roll

        # Check the number of log entries in HTML (basic check for presence)
        # This depends on how formatLogEntry structures them.
        # The messages themselves being present in the script data block is a good check,
        # as the dynamic class assertion won't work on raw HTML.
        # So, the existing assertIn checks for messages are the primary validation here.
        pass # No change needed for class count, the message content checks are sufficient

if __name__ == '__main__':
    unittest.main(verbosity=2)
