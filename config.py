import os

# Default secret key (should be overridden in instance config for production or via env var)
SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_default_development_secret_key'

# Google OAuth Credentials (placeholders - should be overridden in instance config or via env var)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'YOUR_GOOGLE_CLIENT_ID_HERE'
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'YOUR_GOOGLE_CLIENT_SECRET_HERE'

# Database configuration (example, if you want to make it configurable)
# These are typically set directly in app/__init__.py for simpler setups,
# but can be moved here and loaded if more complex configuration is needed.

# Gemini API Key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or 'YOUR_GEMINI_API_KEY_HERE'
DEFAULT_GEMINI_MODEL = os.environ.get('DEFAULT_GEMINI_MODEL') or 'gemini-pro'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@example.com'
# SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dndadventure.db'
# SQLALCHEMY_TRACK_MODIFICATIONS = False
