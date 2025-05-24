import unittest
from bs4 import BeautifulSoup # For CSRF token parsing
from tests.base_test import BaseTestCase
from app.models import User, Character, CLASS_DATA_MODEL # Added CLASS_DATA_MODEL
from app import db

class CharacterTestCase(BaseTestCase):

    def _get_csrf_token(self):
        """Helper method to get a CSRF token from a form page."""
        # Ensure user is logged in to access pages with CSRF tokens
        # Using create_character page as it's behind login and has a form
        response = self.client.get('/character/create_character')
        self.assertEqual(response.status_code, 200, "Failed to get /character/create_character for CSRF")
        soup = BeautifulSoup(response.data, 'html.parser')
        csrf_token_tag = soup.find('input', {'name': 'csrf_token'})
        self.assertIsNotNone(csrf_token_tag, "CSRF token not found on /character/create_character")
        self.assertIn('value', csrf_token_tag.attrs, "CSRF token input has no value attribute")
        return csrf_token_tag['value']

    def setUp(self):
        super().setUp()
        # Login the default test user for character tests
        self.login_response = self.login('testuser', 'password123') # Store login response if needed
        self.test_user = User.query.filter_by(username='testuser').first() # Fetch the user object

        # Create a standard character for this user for route testing
        # Ensure XP_THRESHOLDS and CLASS_DATA_MODEL are available if not already imported
        from app.models import XP_THRESHOLDS, CLASS_DATA_MODEL

        self.character = Character(
            name='Test Character for Rolls',
            race='Human',
            character_class='Fighter',
            level=3, # Some level to have proficiency bonus > 2
            strength=16, dexterity=14, constitution=15,
            intelligence=10, wisdom=12, charisma=8,
            owner=self.test_user,
            experience_points=XP_THRESHOLDS[2], # XP for level 3 (index 2 for level 3)
            spells_known="Test Spell, Fireball" # Added spells_known for self.character
        )
        # Set initial HP based on class and con for level 1
        class_info = CLASS_DATA_MODEL.get(self.character.character_class, CLASS_DATA_MODEL["Default"])
        con_modifier = self.character.get_modifier_for_ability('constitution')
        
        # Calculate HP for Level 1
        current_max_hp = class_info["hit_dice_type"] + con_modifier
        
        # Simulate leveling up to current level (e.g., 3) for HP and hit dice
        if self.character.level > 1:
            for i in range(1, self.character.level):
                hp_increase = class_info["avg_hp_gain_per_level"] + con_modifier
                current_max_hp += hp_increase
        
        self.character.max_hp = current_max_hp
        self.character.current_hp = self.character.max_hp # Full HP at current level
        self.character.hit_dice_type = class_info["hit_dice_type"]
        self.character.hit_dice_max = self.character.level 
        self.character.hit_dice_current = self.character.level


        db.session.add(self.character)
        db.session.commit()


    def test_character_creation_page_loads(self):
        response = self.client.get('/character/create_character')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Create New Character', response.data)

    def test_successful_character_creation(self):
        initial_char_count = Character.query.filter_by(user_id=self.test_user.id).count()
        csrf_token = self._get_csrf_token() # Fetch CSRF token
        response = self.client.post('/character/create_character', data=dict(
            name='GandalfTheTester', # Changed name slightly to avoid potential clashes if test reruns
            race='Human', # Using a standard valid choice
            character_class='Fighter', # Using a standard valid choice
            csrf_token=csrf_token # Add CSRF token to form data
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Should redirect to character selection page
        self.assertIn(b'Select Your Character', response.data) # Check for redirect to selection page
        
        new_char_count = Character.query.filter_by(user_id=self.test_user.id).count()
        self.assertEqual(new_char_count, initial_char_count + 1)
        
        character = Character.query.filter_by(name='GandalfTheTester').first()
        self.assertIsNotNone(character)
        self.assertEqual(character.owner, self.test_user)
        self.assertIn(b'GandalfTheTester', response.data) # Check if new character is listed

    def test_character_creation_missing_name(self):
        csrf_token = self._get_csrf_token() # Fetch CSRF token
        response = self.client.post('/character/create_character', data=dict(
            race='Hobbit',
            character_class='Burglar',
            csrf_token=csrf_token # Add CSRF token to form data
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Stays on creation page
        self.assertIn(b'Create New Character', response.data)
        self.assertIn(b'This field is required.', response.data) # WTForms default error

    def test_character_selection_page(self):
        # Create a character first
        char = Character(name='Bilbo', owner=self.test_user, race='Hobbit', character_class='Burglar')
        db.session.add(char)
        db.session.commit()

        response = self.client.get('/character/select_character')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Select Your Character', response.data)
        self.assertIn(b'Bilbo', response.data)

    def test_adventure_page_loads_for_own_character(self):
        char = Character(name='Aragorn', owner=self.test_user, race='Human', character_class='Ranger')
        db.session.add(char)
        db.session.commit()

        response = self.client.get(f'/character/adventure/{char.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Adventure with Aragorn', response.data)
        self.assertIn(b'Character Sheet', response.data) # Tab name

    def test_adventure_page_404_for_non_existent_character(self):
        response = self.client.get('/character/adventure/999') # Non-existent ID
        self.assertEqual(response.status_code, 404)

    def test_adventure_page_403_for_other_users_character(self):
        # Create another user and their character
        other_user = User(username='otheruser', email='other@example.com')
        other_user.set_password('password456')
        db.session.add(other_user)
        db.session.commit()
        
        other_char = Character(name='Legolas', owner=other_user, race='Elf', character_class='Archer')
        db.session.add(other_char)
        db.session.commit()

        # Current logged-in user (testuser) tries to access other_char's adventure page
        response = self.client.get(f'/character/adventure/{other_char.id}')
        self.assertEqual(response.status_code, 403) # Forbidden
        self.assertIn(b'Forbidden', response.data)

    def test_redirect_to_create_character_if_none_exist_on_login(self):
        # Ensure testuser has no characters initially for this test
        Character.query.filter_by(user_id=self.test_user.id).delete()
        db.session.commit()

        # Re-login to trigger the redirect logic
        self.logout()
        response = self.login('testuser', 'password123')
        self.assertEqual(response.status_code, 200)
        # current_user.characters.first() in main.routes will be None
        # main.index redirects to character.create_character
        # auth.routes redirects to character.select_character, which then links to create
        # Let's check the final landing page content
        self.assertIn(b'Create New Character', response.data)

    def test_successful_character_creation_with_all_fields(self):
        initial_char_count = Character.query.filter_by(user_id=self.test_user.id).count()
        csrf_token = self._get_csrf_token()
        
        character_data = {
            'name': 'ElaraMoonwhisper',
            'race': 'Elf',
            'character_class': 'Wizard',
            'strength': 10,
            'dexterity': 14,
            'constitution': 13, # Modifier +1
            'intelligence': 16, # Modifier +3
            'wisdom': 12,
            'charisma': 8,
            'spells_known': "Magic Missile, Shield, Mage Armor",
            'csrf_token': csrf_token
        }
        
        response = self.client.post('/character/create_character', data=character_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200, "Character creation failed.")
        self.assertIn(b'Select Your Character', response.data, "Did not redirect to character selection page.")
        
        new_char_count = Character.query.filter_by(user_id=self.test_user.id).count()
        self.assertEqual(new_char_count, initial_char_count + 1, "Character count did not increase.")
        
        created_character = Character.query.filter_by(name=character_data['name']).first()
        self.assertIsNotNone(created_character, "Character was not found in the database.")
        self.assertEqual(created_character.owner, self.test_user)
        
        self.assertEqual(created_character.race, character_data['race'])
        self.assertEqual(created_character.character_class, character_data['character_class'])
        self.assertEqual(created_character.strength, character_data['strength'])
        self.assertEqual(created_character.dexterity, character_data['dexterity'])
        self.assertEqual(created_character.constitution, character_data['constitution'])
        self.assertEqual(created_character.intelligence, character_data['intelligence'])
        self.assertEqual(created_character.wisdom, character_data['wisdom'])
        self.assertEqual(created_character.charisma, character_data['charisma'])
        self.assertEqual(created_character.spells_known, character_data['spells_known'])
        
        # HP Calculation Check (assuming new characters start at level 1)
        # In create_character route, level is set to 1.
        # Max HP is calculated as: class_info["hit_dice"] + con_modifier
        char_class_name = created_character.character_class
        class_info = CLASS_DATA_MODEL.get(char_class_name, CLASS_DATA_MODEL["Default"])
        expected_con_modifier = (created_character.constitution - 10) // 2
        expected_hp_at_level_1 = class_info["hit_dice_type"] + expected_con_modifier
        self.assertEqual(created_character.max_hp, expected_hp_at_level_1, "Max HP calculation is incorrect.")
        self.assertEqual(created_character.level, 1, "New character level should be 1.")

    def test_character_sheet_displays_new_fields(self):
        # self.character is created in setUp with ability scores and spells_known
        # Ensure user is logged in (done in setUp)
        
        response = self.client.get(f'/character/adventure/{self.character.id}')
        self.assertEqual(response.status_code, 200, "Failed to load adventure page.")
        
        response_data_str = response.data.decode('utf-8')

        # Check ability scores and modifiers
        # self.character setup: strength=16, dexterity=14, constitution=15, intelligence=10, wisdom=12, charisma=8
        # Modifiers: Str +3, Dex +2, Con +2, Int +0, Wis +1, Cha -1
        self.assertIn(f'<p class="score">{self.character.strength}</p>', response_data_str)
        self.assertIn(f'<p class="modifier">({self.character.get_modifier_for_ability("strength")})</p>', response_data_str)
        
        self.assertIn(f'<p class="score">{self.character.dexterity}</p>', response_data_str)
        self.assertIn(f'<p class="modifier">({self.character.get_modifier_for_ability("dexterity")})</p>', response_data_str)

        self.assertIn(f'<p class="score">{self.character.constitution}</p>', response_data_str)
        self.assertIn(f'<p class="modifier">({self.character.get_modifier_for_ability("constitution")})</p>', response_data_str)

        self.assertIn(f'<p class="score">{self.character.intelligence}</p>', response_data_str)
        self.assertIn(f'<p class="modifier">({self.character.get_modifier_for_ability("intelligence")})</p>', response_data_str)

        self.assertIn(f'<p class="score">{self.character.wisdom}</p>', response_data_str)
        self.assertIn(f'<p class="modifier">({self.character.get_modifier_for_ability("wisdom")})</p>', response_data_str)

        self.assertIn(f'<p class="score">{self.character.charisma}</p>', response_data_str)
        self.assertIn(f'<p class="modifier">({self.character.get_modifier_for_ability("charisma")})</p>', response_data_str)

        # Check spells_known
        # self.character.spells_known = "Test Spell, Fireball" (set in modified setUp)
        # The template uses a <pre> tag for spells_known
        self.assertIn(f"<pre>{self.character.spells_known}</pre>", response_data_str)
        self.assertIn("<h3>Spells Known", response_data_str) # Check section header

    # --- Dice Rolling Route Tests ---
    def test_roll_initiative_route(self):
        from app.models import AdventureLogEntry # Import here or at top of file
        self.assertIsNotNone(self.character, "Test character not created in setUp")
        with self.client: # Ensure client is used in a context for session handling
            csrf_token = self._get_csrf_token()
            response = self.client.post(
                f'/character/adventure/{self.character.id}/roll_initiative',
                headers={'X-CSRFToken': csrf_token},
                json={} # Send empty JSON payload
            )
            self.assertEqual(response.status_code, 200)
            json_response = response.get_json()
            self.assertIn('message', json_response)
            self.assertIn('roll_details', json_response)
            self.assertIn('Initiative', json_response['message'])
            
            # Verify log entry
            log_entry = AdventureLogEntry.query.filter_by(character_id=self.character.id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
            self.assertIsNotNone(log_entry)
            self.assertIn("Initiative", log_entry.message)
            self.assertIn(str(json_response['roll_details']['total_with_modifier']), log_entry.message)

    def test_roll_ability_check_route(self):
        from app.models import AdventureLogEntry
        self.assertIsNotNone(self.character, "Test character not created in setUp")
        with self.client:
            csrf_token = self._get_csrf_token()
            response = self.client.post(
                f'/character/adventure/{self.character.id}/roll_ability_check/strength',
                headers={'X-CSRFToken': csrf_token},
                json={}
            )
            self.assertEqual(response.status_code, 200)
            json_response = response.get_json()
            self.assertIn('message', json_response)
            self.assertIn('Strength Check', json_response['message'])
            log_entry = AdventureLogEntry.query.filter_by(character_id=self.character.id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
            self.assertIsNotNone(log_entry)
            self.assertIn("Strength Check", log_entry.message)

            # Test invalid ability
            # For invalid ability, CSRF token might not be strictly necessary if it fails before CSRF check,
            # but good practice to include it for POST requests.
            csrf_token_invalid = self._get_csrf_token() # Re-fetch if needed, or assume same token is fine
            response_invalid = self.client.post(
                f'/character/adventure/{self.character.id}/roll_ability_check/invalidstat',
                headers={'X-CSRFToken': csrf_token_invalid},
                json={}
            )
            self.assertEqual(response_invalid.status_code, 400)
            self.assertIn('Invalid ability name', response_invalid.get_json()['error'])

    def test_roll_saving_throw_route(self):
        from app.models import AdventureLogEntry
        self.assertIsNotNone(self.character, "Test character not created in setUp")
        with self.client:
            csrf_token = self._get_csrf_token()
            response = self.client.post(
                f'/character/adventure/{self.character.id}/roll_saving_throw/dexterity',
                headers={'X-CSRFToken': csrf_token},
                json={}
            )
            self.assertEqual(response.status_code, 200)
            json_response = response.get_json()
            self.assertIn('message', json_response)
            self.assertIn('Dexterity Save', json_response['message'])
            log_entry = AdventureLogEntry.query.filter_by(character_id=self.character.id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
            self.assertIsNotNone(log_entry)
            self.assertIn("Dexterity Save", log_entry.message)

            # Test invalid ability
            csrf_token_invalid = self._get_csrf_token()
            response_invalid = self.client.post(
                f'/character/adventure/{self.character.id}/roll_saving_throw/invalidstat',
                headers={'X-CSRFToken': csrf_token_invalid},
                json={}
            )
            self.assertEqual(response_invalid.status_code, 400)
            self.assertIn('Invalid ability name for saving throw', response_invalid.get_json()['error']) # Message updated in route
        
    def test_roll_skill_check_specific_route(self):
        from app.models import AdventureLogEntry
        self.assertIsNotNone(self.character, "Test character not created in setUp")
        with self.client:
            csrf_token = self._get_csrf_token()
            # Test a valid skill.
            response = self.client.post(
                f'/character/adventure/{self.character.id}/roll_skill_check/athletics/strength',
                headers={'X-CSRFToken': csrf_token},
                json={}
            )
            self.assertEqual(response.status_code, 200)
            json_response = response.get_json()
            self.assertIn('message', json_response)
            self.assertIn('Athletics check', json_response['message']) 
            log_entry = AdventureLogEntry.query.filter_by(character_id=self.character.id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
            self.assertIsNotNone(log_entry)
            self.assertIn("Athletics check", log_entry.message)

            # Test invalid skill
            csrf_token_invalid = self._get_csrf_token()
            response_invalid = self.client.post(
                f'/character/adventure/{self.character.id}/roll_skill_check/invalid_skill_name/strength',
                headers={'X-CSRFToken': csrf_token_invalid},
                json={}
            )
            self.assertEqual(response_invalid.status_code, 400) 
            self.assertIn('Invalid skill', response_invalid.get_json()['error'])

    def test_roll_attack_generic_route(self):
        from app.models import AdventureLogEntry
        self.assertIsNotNone(self.character, "Test character not created in setUp")
        with self.client:
            csrf_token = self._get_csrf_token()
            response = self.client.post(
                f'/character/adventure/{self.character.id}/roll_attack',
                headers={'X-CSRFToken': csrf_token},
                json={}
            )
            self.assertEqual(response.status_code, 200)
            json_response = response.get_json()
            self.assertIn('message', json_response)
            self.assertIn('attacks!', json_response['message'])
            log_entry = AdventureLogEntry.query.filter_by(character_id=self.character.id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
            self.assertIsNotNone(log_entry)
            self.assertIn("attacks!", log_entry.message)

    def test_roll_damage_generic_route(self):
        from app.models import AdventureLogEntry
        self.assertIsNotNone(self.character, "Test character not created in setUp")
        with self.client:
            csrf_token = self._get_csrf_token()
            # Valid damage roll
            payload = {'num_dice': 2, 'dice_type': 8, 'modifier_stat': 'strength'}
            response = self.client.post(
                f'/character/adventure/{self.character.id}/roll_damage',
                headers={'X-CSRFToken': csrf_token},
                json=payload
            )
            self.assertEqual(response.status_code, 200)
            json_response = response.get_json()
            self.assertIn('message', json_response)
            self.assertIn('deals damage!', json_response['message'])
            log_entry = AdventureLogEntry.query.filter_by(character_id=self.character.id, entry_type="action_roll").order_by(AdventureLogEntry.id.desc()).first()
            self.assertIsNotNone(log_entry)
            self.assertIn("deals damage!", log_entry.message)
            self.assertTrue(int(json_response['roll_details']['modifier']) == self.character.get_modifier_for_ability('strength'))


            # Valid damage roll with 'none' modifier
            csrf_token_none_mod = self._get_csrf_token()
            payload_none_mod = {'num_dice': 1, 'dice_type': 4, 'modifier_stat': 'none'}
            response_none_mod = self.client.post(
                f'/character/adventure/{self.character.id}/roll_damage',
                headers={'X-CSRFToken': csrf_token_none_mod},
                json=payload_none_mod
            )
            self.assertEqual(response_none_mod.status_code, 200)
            json_response_none_mod = response_none_mod.get_json()
            self.assertIn('message', json_response_none_mod)
            self.assertEqual(json_response_none_mod['roll_details']['modifier'], 0)


            # Test invalid payload - missing fields
            csrf_token_invalid_payload = self._get_csrf_token()
            response_invalid = self.client.post(
                f'/character/adventure/{self.character.id}/roll_damage',
                headers={'X-CSRFToken': csrf_token_invalid_payload},
                json={'num_dice': 1} # Missing dice_type
            )
            self.assertEqual(response_invalid.status_code, 400)
            self.assertIn('positive integers', response_invalid.get_json()['error'])

            # Test invalid payload - non-integer
            csrf_token_non_int = self._get_csrf_token()
            response_invalid_non_int = self.client.post(
                f'/character/adventure/{self.character.id}/roll_damage',
                headers={'X-CSRFToken': csrf_token_non_int},
                json={'num_dice': 'abc', 'dice_type': 6, 'modifier_stat': 'strength'}
            )
            self.assertEqual(response_invalid_non_int.status_code, 400)
            self.assertIn('positive integers', response_invalid_non_int.get_json()['error'])
            
            # Test invalid modifier_stat
            csrf_token_invalid_stat = self._get_csrf_token()
            payload_invalid_stat = {'num_dice': 1, 'dice_type': 6, 'modifier_stat': 'invalid_ability'}
            response_invalid_stat = self.client.post(
                f'/character/adventure/{self.character.id}/roll_damage',
                headers={'X-CSRFToken': csrf_token_invalid_stat},
                json=payload_invalid_stat
            )
            self.assertEqual(response_invalid_stat.status_code, 400)
            self.assertIn('Invalid modifier_stat', response_invalid_stat.get_json()['error'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
