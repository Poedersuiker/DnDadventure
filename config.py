import os

# Default secret key (should be overridden in instance config for production or via env var)
SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_default_development_secret_key'

# Google OAuth Credentials (placeholders - should be overridden in instance config or via env var)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'YOUR_GOOGLE_CLIENT_ID_HERE'
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'YOUR_GOOGLE_CLIENT_SECRET_HERE'

# Gemini API Key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or 'YOUR_GEMINI_API_KEY_HERE'
DEFAULT_GEMINI_MODEL = os.environ.get('DEFAULT_GEMINI_MODEL') or 'gemini-pro'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@example.com'

# Database configuration
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dndadventure.db'
# For SQLALCHEMY_TRACK_MODIFICATIONS, explicitly check for 'true' string from env var
SQLALCHEMY_TRACK_MODIFICATIONS = (os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS', 'False').lower() == 'true')

# Build information
GIT_BRANCH_DEFAULT = "unknown"
DEPLOYMENT_TIME_DEFAULT = "N/A"
GIT_BRANCH = GIT_BRANCH_DEFAULT
DEPLOYMENT_TIME = DEPLOYMENT_TIME_DEFAULT

# Path to build_info.py relative to config.py (project root)
# Assumes instance folder is at project root, alongside config.py
_build_info_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'build_info.py')

_build_info_vars = {}
if os.path.exists(_build_info_path):
    try:
        with open(_build_info_path, 'r') as f:
            exec(f.read(), _build_info_vars)
        GIT_BRANCH = _build_info_vars.get('GIT_BRANCH', GIT_BRANCH_DEFAULT)
        DEPLOYMENT_TIME = _build_info_vars.get('DEPLOYMENT_TIME', DEPLOYMENT_TIME_DEFAULT)
    except Exception:
        # In case of errors reading or exec-ing, keep defaults
        # Optionally, add logging here if a logger is configured
        pass
