import unittest
from unittest.mock import patch, MagicMock, call
import requests.exceptions # For simulating HTTPError
import json # For simulating JSONDecodeError

# It's good practice to import the specific things you need from your app
from app import app
from app import db as actual_db # Import your actual db for setup
from app.models import Class as ActualClass # Import your actual Class for setup
from app.scripts.populate_classes import populate_classes_data

# Helper to simulate requests.get responses
# This function will be used as the side_effect for the mocked requests.get
def mock_requests_get_side_effect(*args, **kwargs):
    url = args[0]
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock() # Default to no error for most calls

    if url == "https://www.dnd5eapi.co/api/classes":
        mock_response.json.return_value = {
            'results': [
                {'index': 'warrior', 'name': 'Warrior', 'url': '/api/classes/warrior'},
                {'index': 'mage', 'name': 'Mage', 'url': '/api/classes/mage'},
                {'index': 'rogue', 'name': 'Rogue', 'url': '/api/classes/rogue'}
            ]
        }
    elif url == "https://www.dnd5eapi.co/api/classes/warrior":
        mock_response.json.return_value = {
            'index': 'warrior', 'name': 'Warrior', 'hit_die': 10,
            'proficiencies': [{'name': 'Light armor'}, {'name': 'Shields'}], # Example data
            'saving_throws': [{'name': 'STR'}, {'name': 'CON'}],
            'proficiency_choices': [
                {
                    'desc': 'Skills: Choose two from Acrobatics, Animal Handling, Athletics...',
                    'choose': 2,
                    'from': {
                        'options': [
                            {'item': {'index': 'skill-athletics', 'name': 'Athletics'}},
                            {'item': {'index': 'skill-intimidation', 'name': 'Intimidation'}}
                        ]
                    }
                }
            ],
            'starting_equipment': [{'equipment': {'name': 'Longsword'}}],
            'spellcasting': None, 
        }
    elif url == "https://www.dnd5eapi.co/api/classes/mage":
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Simulated API Error for Mage")
    elif url == "https://www.dnd5eapi.co/api/classes/rogue":
        mock_response.json.return_value = {
            'index': 'rogue', 'name': 'Rogue', 'hit_die': 8,
            'proficiencies': [{'name': 'Light armor'}, {'name': 'Thieves Tools'}],
            'saving_throws': [{'name': 'DEX'}, {'name': 'INT'}],
            'proficiency_choices': [
                {
                    'desc': 'Skills: Choose four from Acrobatics, Athletics, Deception...',
                    'choose': 4,
                    'from': {
                        'options': [
                            {'item': {'index': 'skill-acrobatics', 'name': 'Acrobatics'}},
                            {'item': {'index': 'skill-stealth', 'name': 'Stealth'}}
                        ]
                    }
                }
            ],
            'starting_equipment': [{'equipment': {'name': 'Dagger', 'quantity': 2}}],
            'spellcasting': None,
        }
    elif "/api/classes/warrior/levels" in url:
        mock_response.json.return_value = [
            {'level': 1, 'prof_bonus': 2, 'features': [], 'spellcasting': {}},
            {'level': 2, 'prof_bonus': 2, 'features': [], 'spellcasting': {}},
        ]
    elif "/api/classes/rogue/levels" in url:
         mock_response.json.return_value = [
            {'level': 1, 'prof_bonus': 2, 'features': [], 'spellcasting': {}},
            {'level': 2, 'prof_bonus': 2, 'features': [], 'spellcasting': {}},
        ]
    elif "/api/classes/mage/levels" in url:
        mock_response.json.return_value = [] # Should not be called
    else:
        mock_response.raise_for_status.side_effect = Exception(f"Unexpected URL in mock_requests_get: {url}")
    return mock_response

class TestPopulateScripts(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Removed actual_db.init_app(app) to prevent RuntimeError
        
        actual_db.create_all()

    def tearDown(self):
        actual_db.session.remove()
        actual_db.drop_all()
        self.app_context.pop()

    @patch('app.scripts.populate_classes.print') 
    @patch('app.scripts.populate_classes.db') 
    @patch('app.scripts.populate_classes.Class') 
    @patch('app.scripts.populate_classes.requests.get', side_effect=mock_requests_get_side_effect)
    def test_populate_classes_handles_errors_and_continues(self, mock_api_get, MockClassModel, mock_db_in_script, mock_print_in_script):
        MockClassModel.query.filter_by.return_value.first.return_value = None
        
        mock_class_instances = []
        def mock_class_constructor(*args, **kwargs):
            instance = MagicMock(spec=ActualClass) 
            instance.name = kwargs.get('name') 
            mock_class_instances.append(instance)
            return instance
        MockClassModel.side_effect = mock_class_constructor
        
        populate_classes_data()

        expected_api_calls = [
            call('https://www.dnd5eapi.co/api/classes'),
            call('https://www.dnd5eapi.co/api/classes/warrior'),
            call('https://www.dnd5eapi.co/api/classes/warrior/levels'),
            call('https://www.dnd5eapi.co/api/classes/mage'),
            call('https://www.dnd5eapi.co/api/classes/rogue'),
            call('https://www.dnd5eapi.co/api/classes/rogue/levels')
        ]
        
        for expected_call in expected_api_calls:
            self.assertIn(expected_call, mock_api_get.call_args_list, f"Expected API call {expected_call} not found.")
        
        self.assertNotIn(call('https://www.dnd5eapi.co/api/classes/mage/levels'), mock_api_get.call_args_list,
                         "API call for mage levels should not have occurred due to prior error.")

        self.assertEqual(MockClassModel.call_count, 2, "Class constructor should be called for Warrior and Rogue only.")
        
        constructed_class_names = [instance.name for instance in mock_class_instances]
        self.assertIn('Warrior', constructed_class_names, "Warrior class should have been constructed.")
        self.assertNotIn('Mage', constructed_class_names, "Mage class should not have been constructed due to API error.")
        self.assertIn('Rogue', constructed_class_names, "Rogue class should have been constructed.")
        
        self.assertEqual(mock_db_in_script.session.add.call_count, 2, "db.session.add should be called twice.")
        
        added_instance_names = [add_call_args[0][0].name for add_call_args in mock_db_in_script.session.add.call_args_list]
        self.assertIn('Warrior', added_instance_names, "Warrior instance should have been added to session.")
        self.assertIn('Rogue', added_instance_names, "Rogue instance should have been added to session.")

        mock_db_in_script.session.commit.assert_called_once_with()

        mage_error_logged = any(
            "error fetching details for mage" in str(p_call_args).lower() and "simulated api error for mage" in str(p_call_args).lower()
            for p_call_args in mock_print_in_script.call_args_list
        )
        self.assertTrue(mage_error_logged, "Error message for 'Mage' class processing was not logged correctly.")

        rogue_added_log = any(
            "added 'rogue' to session" in str(p_call_args).lower()
            for p_call_args in mock_print_in_script.call_args_list
        )
        self.assertTrue(rogue_added_log, "Log message for adding 'Rogue' to session not found.")

        warrior_added_log = any(
            "added 'warrior' to session" in str(p_call_args).lower()
            for p_call_args in mock_print_in_script.call_args_list
        )
        self.assertTrue(warrior_added_log, "Log message for adding 'Warrior' to session not found.")

if __name__ == '__main__':
    unittest.main(verbosity=2)
