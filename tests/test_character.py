import unittest
from tests.base_test import BaseTestCase
from app.models import User, Character
from app import db

class CharacterTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        # Login the default test user for character tests
        self.login('testuser', 'password123')

    def test_character_creation_page_loads(self):
        response = self.client.get('/character/create_character')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Create New Character', response.data)

    def test_successful_character_creation(self):
        initial_char_count = Character.query.filter_by(user_id=self.test_user.id).count()
        response = self.client.post('/character/create_character', data=dict(
            name='Gandalf',
            race='Wizard', # Intentionally using 'Wizard' for race to see if it passes
            character_class='Istari'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Should redirect to character selection page
        self.assertIn(b'Select Your Character', response.data)
        
        new_char_count = Character.query.filter_by(user_id=self.test_user.id).count()
        self.assertEqual(new_char_count, initial_char_count + 1)
        
        character = Character.query.filter_by(name='Gandalf').first()
        self.assertIsNotNone(character)
        self.assertEqual(character.owner, self.test_user)
        self.assertIn(b'Gandalf', response.data) # Check if new character is listed

    def test_character_creation_missing_name(self):
        response = self.client.post('/character/create_character', data=dict(
            race='Hobbit',
            character_class='Burglar'
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
