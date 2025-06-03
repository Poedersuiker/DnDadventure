import json # Added for fromjson filter
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate # Added Migrate import
from werkzeug.middleware.proxy_fix import ProxyFix # Import ProxyFix
from flask_babel import Babel

# Modified to make instance folder easily accessible for config loading
app = Flask(__name__, instance_relative_config=True) 

# Apply ProxyFix to handle headers from reverse proxies
# This should be done early, but after app instantiation.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

babel = Babel()
babel.init_app(app)

# Load configurations:
# 1. Load defaults from project's root config.py
app.config.from_object('config') 
# 2. Load from instance/config.py (if it exists), overriding defaults.
# 'config.py' here is relative to the 'instance' folder due to instance_relative_config=True
app.config.from_pyfile('config.py', silent=True) 

# Note: SECRET_KEY is now loaded from config.py or instance/config.py
# app.config['SECRET_KEY'] = 'a_very_secret_key' # Removed, as it's loaded from files

# Configure Flask-Dance Google blueprint credentials from loaded config
# The blueprint is named "google" by default in make_google_blueprint
# These keys are what Flask-Dance expects (e.g., <BLUPRINT_NAME>_OAUTH_CLIENT_ID)
app.config['GOOGLE_OAUTH_CLIENT_ID'] = app.config.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = app.config.get('GOOGLE_CLIENT_SECRET')

# Logging Configuration
import logging
from logging.handlers import RotatingFileHandler
import os

# Ensure instance folder exists
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

log_file_path = os.path.join(app.instance_path, 'app.log')
file_handler = RotatingFileHandler(log_file_path,
                                   maxBytes=102400, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))

# Set level for the handler
file_handler.setLevel(logging.INFO)

# Get the Flask app's logger and add the handler
# app.logger.handlers.clear() # Cautious about clearing existing handlers
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO) # Set overall logger level
app.logger.info('Application logging configured to file.')

# Store log file path in app config for easy access in routes
app.config['APP_LOG_FILE'] = log_file_path

db = SQLAlchemy(app)
migrate = Migrate(app, db) # Initialized Flask-Migrate

login_manager = LoginManager(app)
login_manager.login_view = 'main.login_page' # Updated as per Step 6

from .models import User, Setting # Add Setting import
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from . import models # models is already imported above for User, keep for db registration

# Function to load/initialize settings from DB
def load_and_initialize_settings(current_app): # Restored signature
    with current_app.app_context(): # Uses current_app argument
        default_model_key = 'DEFAULT_GEMINI_MODEL'
        try:
            db_setting = Setting.query.filter_by(key=default_model_key).first()

            if db_setting and db_setting.value: # Check if db_setting.value is not None or empty
                current_app.config[default_model_key] = db_setting.value
                current_app.logger.info(f"Loaded '{default_model_key}' from database: {db_setting.value}")
            else:
                # Setting not in DB or value is empty, or db_setting itself is None
                # Initialize from config.py's value
                value_from_config = current_app.config.get(default_model_key) # This is the value from config.py or instance/config.py
                if value_from_config: # Ensure there's a value in config.py
                    if db_setting: # Setting key exists but value is empty/None
                        db_setting.value = value_from_config
                        current_app.logger.info(f"Updating empty DB setting for '{default_model_key}' from config.py: {value_from_config}")
                    else: # Setting key does not exist
                        db_setting = Setting(key=default_model_key, value=value_from_config)
                        db.session.add(db_setting)
                        current_app.logger.info(f"Initialized '{default_model_key}' in database from config.py: {value_from_config}")
                    
                    db.session.commit() # Commit changes (add or update)
                else:
                    current_app.logger.warning(f"'{default_model_key}' not found in config.py and not initialized in database.")
        except Exception as e: # Catch broader exceptions during DB operations
            db.session.rollback()
            current_app.logger.error(f"Database error during settings initialization for '{default_model_key}': {e}")
            current_app.logger.info(f"'{default_model_key}' will use the value from config.py if available: {current_app.config.get(default_model_key)}")

# Conditionally call the function after db is initialized and app config is loaded.
# This prevents it from running during test imports if app.config['TESTING'] is True.
if not app.config.get('TESTING', False):
    load_and_initialize_settings(app)

# Custom Jinja Filter for JSON
def from_json_filter(value):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [] # Return empty list on error, suitable for spell descriptions

app.jinja_env.filters['fromjson'] = from_json_filter

# Context Processors
from app.utils import inject_build_info

@app.context_processor
def _inject_build_info_context(): # Renamed to avoid potential clashes if inject_build_info was also directly decorated
    return inject_build_info()

# Import and register blueprints
from .auth import auth_bp
app.register_blueprint(auth_bp)

from app.main import bp as main_bp # Import main blueprint
app.register_blueprint(main_bp) # Register main blueprint

# Near other blueprint registrations
from app.admin import admin_bp
app.register_blueprint(admin_bp)

from .api.open5e_api import open5e_bp # Import Open5e API blueprint
app.register_blueprint(open5e_bp, url_prefix='/api') # Register Open5e API blueprint
