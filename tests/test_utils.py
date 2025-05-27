import unittest
from unittest.mock import patch, MagicMock
from app import app # Your Flask app instance
from app.utils import list_gemini_models, parse_coinage # Updated import
# If google.generativeai is not easily importable for error types,
# you can mock a generic Exception for the API error test.

class MockModel:
    def __init__(self, name, supported_generation_methods):
        self.name = name
        self.supported_generation_methods = supported_generation_methods

class TestUtils(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        # Store original config values to restore them in tearDown
        self.original_gemini_api_key = app.config.get('GEMINI_API_KEY')
        # Set a default test API key, can be overridden in specific tests
        app.config['GEMINI_API_KEY'] = 'default_test_api_key' 

    def tearDown(self):
        # Restore original config values
        app.config['GEMINI_API_KEY'] = self.original_gemini_api_key
        self.app_context.pop()

    @patch('app.utils.genai') # Patching 'genai' where it's used in app.utils
    def test_list_gemini_models_success(self, mock_genai_module):
        app.config['GEMINI_API_KEY'] = 'fake_valid_key' # Specific key for this test
        
        # Configure mock return values for genai.list_models()
        mock_genai_module.list_models.return_value = [
            MockModel(name='models/gemini-pro', supported_generation_methods=['generateContent', 'embedContent']),
            MockModel(name='models/gemini-pro-vision', supported_generation_methods=['generateContent']),
            MockModel(name='models/embedding-001', supported_generation_methods=['embedContent'])
        ]
        
        result = list_gemini_models()
        
        mock_genai_module.configure.assert_called_once_with(api_key='fake_valid_key')
        self.assertEqual(result, ['models/gemini-pro', 'models/gemini-pro-vision'])

    @patch('app.utils.genai')
    @patch('app.utils.logging') # Patch logging in app.utils
    def test_list_gemini_models_no_api_key(self, mock_logging, mock_genai_module):
        app.config['GEMINI_API_KEY'] = None
        result = list_gemini_models()
        self.assertEqual(result, [])
        mock_genai_module.configure.assert_not_called()
        mock_logging.warning.assert_called_with("GEMINI_API_KEY is not configured or is set to the placeholder.")
        
        mock_logging.reset_mock() # Reset mock for the next call

        app.config['GEMINI_API_KEY'] = 'YOUR_GEMINI_API_KEY_HERE' # Placeholder
        result = list_gemini_models()
        self.assertEqual(result, [])
        mock_genai_module.configure.assert_not_called()
        mock_logging.warning.assert_called_with("GEMINI_API_KEY is not configured or is set to the placeholder.")

    @patch('app.utils.genai')
    @patch('app.utils.logging') # Patch logging in app.utils
    def test_list_gemini_models_api_error(self, mock_logging, mock_genai_module):
        app.config['GEMINI_API_KEY'] = 'fake_valid_key_for_error_test'
        
        # genai.configure should not raise an error for this test path
        mock_genai_module.configure.return_value = None 
        
        # Simulate an error during genai.list_models()
        simulated_error_message = "Simulated API Error"
        mock_genai_module.list_models.side_effect = Exception(simulated_error_message)

        result = list_gemini_models()
        
        mock_genai_module.configure.assert_called_once_with(api_key='fake_valid_key_for_error_test')
        self.assertEqual(result, [])
        mock_logging.error.assert_called_with(f"Error listing Gemini models: {simulated_error_message}")

class TestParseCoinage(unittest.TestCase): # Renamed class
    def test_parse_coinage_gold_only(self):
        self.assertEqual(parse_coinage("pouch containing 15 gp."), {'Gold': 15, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("10 Gold Pieces and some lint"), {'Gold': 10, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("5g in pocket"), {'Gold': 5, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("Received 100 gold"), {'Gold': 100, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("A note mentioning 50gp but it's fake."), {'Gold': 50, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("25 gp"), {'Gold': 25, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("0gp"), {'Gold': 0, 'Silver': 0, 'Copper': 0})

    def test_parse_coinage_silver_only(self):
        self.assertEqual(parse_coinage("Some silver pieces (10 sp)"), {'Gold': 0, 'Silver': 10, 'Copper': 0})
        self.assertEqual(parse_coinage("20 silver"), {'Gold': 0, 'Silver': 20, 'Copper': 0})
        self.assertEqual(parse_coinage("100 SP"), {'Gold': 0, 'Silver': 100, 'Copper': 0})

    def test_parse_coinage_copper_only(self):
        self.assertEqual(parse_coinage("Just 5 copper."), {'Gold': 0, 'Silver': 0, 'Copper': 5})
        self.assertEqual(parse_coinage("Bag of 200 cp"), {'Gold': 0, 'Silver': 0, 'Copper': 200})
        self.assertEqual(parse_coinage("1 copper piece"), {'Gold': 0, 'Silver': 0, 'Copper': 1})
        
    def test_parse_coinage_mixed_denominations(self):
        self.assertEqual(parse_coinage("10gp, 5sp, 20cp"), {'Gold': 10, 'Silver': 5, 'Copper': 20})
        self.assertEqual(parse_coinage("5 silver pieces and 100 gold"), {'Gold': 100, 'Silver': 5, 'Copper': 0})
        self.assertEqual(parse_coinage("A pouch with 15 g, 25 sP, and 50 Copper Pieces."), {'Gold': 15, 'Silver': 25, 'Copper': 50})
        self.assertEqual(parse_coinage("20 cp and 5 gp."), {'Gold': 5, 'Silver': 0, 'Copper': 20}) # Order doesn't matter
        self.assertEqual(parse_coinage("1 gold, 1 silver, 1 copper"), {'Gold': 1, 'Silver': 1, 'Copper': 1})

    def test_parse_coinage_no_coins(self):
        self.assertEqual(parse_coinage("No coins here!"), {'Gold': 0, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("A pouch with nothing in it."), {'Gold': 0, 'Silver': 0, 'Copper': 0})

    def test_parse_coinage_edge_cases(self):
        self.assertEqual(parse_coinage(""), {'Gold': 0, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage(None), {'Gold': 0, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("100"), {'Gold': 0, 'Silver': 0, 'Copper': 0}) # No currency type
        self.assertEqual(parse_coinage("gp 100"), {'Gold': 0, 'Silver': 0, 'Copper': 0}) # Number must come first
        self.assertEqual(parse_coinage("My horse cost 200 gold pieces."), {'Gold': 200, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("A treasure map leading to 1000 Gold."), {'Gold': 1000, 'Silver': 0, 'Copper': 0})
        self.assertEqual(parse_coinage("1g p 2 s p 3 c p"), {'Gold': 1, 'Silver': 2, 'Copper': 3}) # Spaced out
        self.assertEqual(parse_coinage("1gp2sp3cp"), {'Gold': 1, 'Silver': 2, 'Copper': 3}) # No spaces
        self.assertEqual(parse_coinage("1gold2silver3copper"), {'Gold': 1, 'Silver': 2, 'Copper': 3})

if __name__ == '__main__':
    unittest.main()
