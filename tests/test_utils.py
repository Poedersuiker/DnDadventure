import unittest
import unittest
from unittest.mock import patch, MagicMock
from app import app # Your Flask app instance
from app.utils import list_gemini_models, _parse_gold # Imported _parse_gold
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

class TestParseGold(unittest.TestCase):
    def test_parse_gold_various_formats(self):
        self.assertEqual(_parse_gold("pouch containing 15 gp."), 15)
        self.assertEqual(_parse_gold("10 Gold Pieces and some lint"), 10)
        self.assertEqual(_parse_gold("5g in pocket"), 5)
        self.assertEqual(_parse_gold("Received 100 gold"), 100) # "gold" alone
        self.assertEqual(_parse_gold("No gold here!"), 0)
        self.assertEqual(_parse_gold("A note mentioning 50gp but it's fake."), 50)
        self.assertEqual(_parse_gold("25 gp"), 25)
        self.assertEqual(_parse_gold("0gp"), 0)

    def test_parse_gold_no_gold(self):
        self.assertEqual(_parse_gold("Some silver pieces (10 sp)"), 0)
        self.assertEqual(_parse_gold("A pouch with nothing in it."), 0)
        self.assertEqual(_parse_gold("Just some copper."), 0)

    def test_parse_gold_edge_cases(self):
        self.assertEqual(_parse_gold(""), 0)
        self.assertEqual(_parse_gold(None), 0)
        self.assertEqual(_parse_gold("100"), 0) # No "gp" or "gold"
        self.assertEqual(_parse_gold("gp 100"), 0) # Number must come first
        self.assertEqual(_parse_gold("My horse cost 200 gold pieces."), 200)
        self.assertEqual(_parse_gold("A treasure map leading to 1000 Gold."), 1000)


if __name__ == '__main__':
    unittest.main()
