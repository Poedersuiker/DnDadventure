import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from app.services.gemini_service import get_story_response, get_gemini_model
# Assuming Character model is needed for dummy data
from app.models import Character 

class TestGeminiService(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['GEMINI_API_KEY'] = 'test_api_key' # Set a dummy API key for tests
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @patch('app.services.gemini_service.genai.GenerativeModel')
    def test_get_story_response_formats_markdown(self, MockGenerativeModel):
        # Configure the mock model and its response
        mock_model_instance = MockGenerativeModel.return_value
        mock_gemini_response = MagicMock()
        
        # Test case 1: Newlines
        mock_gemini_response.text = "Hello\nWorld\n\nThis is a new paragraph."
        mock_model_instance.generate_content.return_value = mock_gemini_response
        
        # Create a dummy character (only fields used by get_story_response are needed)
        dummy_character = Character(name="Dummy", race="Human", character_class="Tester", level=1, alignment="N", background="Test Background")
        
        response_html = get_story_response(dummy_character, "User says something")
        # markdown2 typically wraps paragraphs in <p> and converts \n within a line to <br /> if not double \n
        # For "Hello\nWorld", it might be "<p>Hello<br />\nWorld</p>"
        # For "Hello\n\nWorld", it would be "<p>Hello</p>\n<p>World</p>"
        self.assertIn("<p>Hello<br />\nWorld</p>", response_html) # Check for <br />
        self.assertIn("<p>This is a new paragraph.</p>", response_html) # Check for separate paragraph

        # Test case 2: Bold and Italic
        mock_gemini_response.text = "*bold* and _italic_ text"
        mock_model_instance.generate_content.return_value = mock_gemini_response
        response_html_format = get_story_response(dummy_character, "User says something else")
        self.assertIn("<p><em>bold</em> and <em>italic</em> text</p>", response_html_format) # markdown2 uses <em> for both * and _

        # Test case 3: Headers (e.g., # Header)
        mock_gemini_response.text = "# My Header\nSome text."
        mock_model_instance.generate_content.return_value = mock_gemini_response
        response_html_header = get_story_response(dummy_character, "User input header")
        self.assertIn("<h1>My Header</h1>", response_html_header)
        self.assertIn("<p>Some text.</p>", response_html_header)

        # Test case 4: Unordered List
        mock_gemini_response.text = "* Item 1\n* Item 2"
        mock_model_instance.generate_content.return_value = mock_gemini_response
        response_html_list = get_story_response(dummy_character, "User input list")
        self.assertIn("<ul>\n<li>Item 1</li>\n<li>Item 2</li>\n</ul>", response_html_list)


    @patch('app.services.gemini_service.genai.GenerativeModel')
    def test_get_story_response_empty_text(self, MockGenerativeModel):
        mock_model_instance = MockGenerativeModel.return_value
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = None # Simulate empty text from Gemini
        mock_gemini_response.parts = [] # No parts
        # Simulate no "STOP" reason, but no specific filtering reason either
        mock_candidate = MagicMock()
        mock_candidate.finish_reason = 'MAX_TOKENS' # or some other non-STOP reason
        mock_gemini_response.candidates = [mock_candidate]
        mock_model_instance.generate_content.return_value = mock_gemini_response
        
        dummy_character = Character(name="Dummy", race="Human", character_class="Tester", level=1, alignment="N", background="Test Background")
        
        with self.assertRaisesRegex(Exception, "Gemini returned no response text."):
            get_story_response(dummy_character, "User input for empty response")

    @patch('app.services.gemini_service.genai.GenerativeModel')
    def test_get_story_response_filtered_content(self, MockGenerativeModel):
        mock_model_instance = MockGenerativeModel.return_value
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = None # Filtered content often has no text
        mock_gemini_response.parts = [] # No parts
        
        # Simulate safety filtering
        mock_candidate_filtered = MagicMock()
        mock_candidate_filtered.finish_reason = 'SAFETY' # Critical part for this test
        mock_gemini_response.candidates = [mock_candidate_filtered]
        mock_model_instance.generate_content.return_value = mock_gemini_response
        
        dummy_character = Character(name="Dummy", race="Human", character_class="Tester", level=1, alignment="N", background="Test Background")
        
        with self.assertRaisesRegex(Exception, "Gemini content filtered or empty"):
            get_story_response(dummy_character, "User input for filtered response")

    def test_get_gemini_model_no_key(self):
        # Temporarily unset the API key for this test
        original_key = self.app.config.get('GEMINI_API_KEY')
        self.app.config['GEMINI_API_KEY'] = None
        with self.assertRaises(ValueError) as context:
            get_gemini_model()
        self.assertTrue("GEMINI_API_KEY not set" in str(context.exception))
        # Restore the original key if it existed
        if original_key:
            self.app.config['GEMINI_API_KEY'] = original_key
        else: # If it was None originally, ensure it's set back to None or removed
            del self.app.config['GEMINI_API_KEY']


if __name__ == '__main__':
    unittest.main()
