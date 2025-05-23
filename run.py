import argparse
import os
from app import create_app

parser = argparse.ArgumentParser(description='Run the Flask app with configurable host and Google API Key.')
parser.add_argument('--host', default='127.0.0.1', help='The host IP address to run the app on.')
parser.add_argument('--google_api_key', help='Your Google API Key for Gemini.')
args = parser.parse_args()

if args.google_api_key:
    os.environ['GEMINI_API_KEY'] = args.google_api_key

app = create_app()

@app.cli.command("test")
def test():
    """Runs the unit tests."""
    import unittest
    import sys 
    loader = unittest.TestLoader()
    # Ensure the pattern matches files like test_auth.py, test_character.py
    tests = loader.discover('tests', pattern='test_*.py') 
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(tests)
    if result.wasSuccessful():
        sys.exit(0)
    sys.exit(1)

if __name__ == '__main__':
    app.run(host=args.host, debug=True)
