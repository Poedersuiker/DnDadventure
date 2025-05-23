from app import create_app

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
    app.run(debug=True)
