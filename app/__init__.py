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

# These can remain if not intended to be overridden by root/instance config.py by default,
# or they can be moved to config.py as well. For now, keeping them here.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dndadventure.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db) # Initialized Flask-Migrate

login_manager = LoginManager(app)
login_manager.login_view = 'main.login_page' # Updated as per Step 6

from .models import User
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from . import models # models is already imported above for User, keep for db registration

# Import and register blueprints
from .auth import auth_bp
app.register_blueprint(auth_bp)

from app.main import bp as main_bp # Import main blueprint
app.register_blueprint(main_bp) # Register main blueprint

# Near other blueprint registrations
from app.admin import admin_bp
app.register_blueprint(admin_bp)
