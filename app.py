import os
from flask import Flask, redirect, url_for, session, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# Load environment variables from .env if it exists, for local development
# This is useful if you prefer to store secrets in a .env file in the root
# during development, instead of or in addition to instance/config.py
if os.path.exists('.env'):
    load_dotenv()

# Initialize Flask app
app = Flask(__name__, instance_relative_config=True)

# --- Configuration Loading ---
# 1. Default configuration (can be an empty file or have non-sensitive defaults)
# We'll create a dummy 'config_default.py' if it doesn't exist to avoid import errors.
if not os.path.exists('config_default.py'):
    with open('config_default.py', 'w') as f:
        f.write("# Default configuration values (can be empty)\n")
app.config.from_object('config_default')

# 2. Instance configuration (for sensitive data, not committed to VCS)
# This will load instance/config.py
try:
    app.config.from_pyfile('config.py', silent=False)
except FileNotFoundError:
    print(f"IMPORTANT: Configuration file 'instance/config.py' not found. "
          f"Please create it by copying 'instance/config.py.example' "
          f"and filling in your details.")
    # Optionally, exit or run with limited functionality if config is critical
    # For this example, we'll try to proceed but OAuth will likely fail.

# Ensure SECRET_KEY is set
if not app.config.get('SECRET_KEY'):
    print("WARNING: SECRET_KEY is not set in instance/config.py. Using a default insecure key.")
    app.config['SECRET_KEY'] = 'dev_secret_key_please_change_in_production'


# --- Database URI Construction ---
db_type = app.config.get('DB_TYPE', 'sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if db_type == 'sqlite':
    db_path_config = app.config.get('DB_PATH', 'development.db')
    # Ensure path is absolute or correctly relative to the instance folder
    if not os.path.isabs(db_path_config):
        db_full_path = os.path.join(app.instance_path, db_path_config)
    else:
        db_full_path = db_path_config
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_full_path}'
elif db_type in ['mysql', 'mariadb', 'mysql+pymysql']:
    user = app.config.get('DB_USER')
    password = app.config.get('DB_PASSWORD')
    host = app.config.get('DB_HOST')
    port = app.config.get('DB_PORT')
    dbname = app.config.get('DB_NAME')
    if not all([user, password, host, port, dbname]):
        print(f"WARNING: Missing one or more MySQL/MariaDB config variables (DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME).")
        app.config['SQLALCHEMY_DATABASE_URI'] = None # Or a default SQLite as fallback
    else:
        # Using pymysql as the driver, ensure it's installed (pip install pymysql)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}'
elif db_type in ['postgresql', 'postgresql+psycopg2']:
    user = app.config.get('DB_USER')
    password = app.config.get('DB_PASSWORD')
    host = app.config.get('DB_HOST')
    port = app.config.get('DB_PORT')
    dbname = app.config.get('DB_NAME')
    if not all([user, password, host, port, dbname]):
        print(f"WARNING: Missing one or more PostgreSQL config variables (DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME).")
        app.config['SQLALCHEMY_DATABASE_URI'] = None # Or a default SQLite as fallback
    else:
        # Using psycopg2 as the driver, ensure it's installed (pip install psycopg2-binary)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'
else:
    print(f"WARNING: Unsupported DB_TYPE: {db_type}. Falling back to default SQLite.")
    db_full_path = os.path.join(app.instance_path, 'fallback_default.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_full_path}'

# --- Initialize Extensions ---
db = SQLAlchemy() # Initialize SQLAlchemy without the app object first
login_manager = LoginManager()
login_manager.login_view = 'login' # Route name for the login page
oauth = OAuth()

# --- User Model ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)

    def get_id(self): # Required by Flask-Login
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Google OAuth Configuration ---
# We need to register the client after the app config is loaded
def initialize_oauth(current_app):
    global google # Make 'google' client accessible globally or within app context
    google = oauth.register(
        name='google',
        client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        access_token_url='https://accounts.google.com/o/oauth2/token',
        client_kwargs={'scope': 'openid email profile'},
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
    )

# --- App Factory Pattern (Optional but good practice) ---
# This part is more relevant if you want to create multiple app instances,
# but we can adapt it for initializing extensions.

def create_app():
    # Ensure instance folder exists (Flask does this automatically for instance_relative_config=True)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        print(f"Error creating instance path {app.instance_path}: {e}")
        # Handle error appropriately, maybe exit

    # Initialize extensions with the app object
    if app.config['SQLALCHEMY_DATABASE_URI']: # Only initialize if URI is set
        db.init_app(app)
    else:
        print("CRITICAL: SQLALCHEMY_DATABASE_URI is not set. Database functionality will be disabled.")

    login_manager.init_app(app)
    oauth.init_app(app)
    initialize_oauth(app) # Initialize Google OAuth client

    with app.app_context():
        if app.config['SQLALCHEMY_DATABASE_URI']:
            db.create_all() # Create database tables if they don't exist
        else:
            print("Skipping db.create_all() because SQLALCHEMY_DATABASE_URI is not set.")
    return app

# Create the app using the factory
app = create_app()


# --- Routes ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login/google')
def login_google_route(): # Renamed to avoid conflict with 'google' oauth client variable
    if not app.config.get('GOOGLE_CLIENT_ID') or not app.config.get('GOOGLE_CLIENT_SECRET'):
        flash("Google OAuth is not configured on the server. Please check your instance/config.py.", "error")
        return redirect(url_for('login'))

    # Use the configured redirect URI or dynamically generate one
    # The _external=True is important for generating an absolute URL
    redirect_uri_config = app.config.get('GOOGLE_REDIRECT_URI')
    if redirect_uri_config:
         # Ensure it's an absolute URL if it comes from config
        if not redirect_uri_config.startswith(('http://', 'https://')):
            flash("GOOGLE_REDIRECT_URI in config must be an absolute URL (e.g., http://localhost:5000/authorize).", "error")
            return redirect(url_for('login'))
        redirect_uri = redirect_uri_config
    else:
        redirect_uri = url_for('authorize', _external=True)

    return google.authorize_redirect(redirect_uri)


@app.route('/authorize') # This is the redirect URI for Google
def authorize():
    try:
        # The 'google' here refers to the oauth client registered earlier
        token = google.authorize_access_token()
    except Exception as e:
        flash(f"Authorization with Google failed: {str(e)}", "error")
        print(f"OAuth Error: {e}") # Log detailed error
        return redirect(url_for('login'))

    if not token or 'userinfo' not in token:
        # Authlib newer versions might directly put userinfo in token,
        # or you might need to fetch it like: user_info = google.parse_id_token(token)
        # For this example, assuming 'userinfo' is directly available or fetched by authorize_access_token
        user_info = oauth.google.userinfo(token=token) # Explicitly fetch userinfo
        if not user_info:
             flash("Failed to fetch user information from Google.", "error")
             return redirect(url_for('login'))
    else:
        user_info = token['userinfo']


    google_id = user_info.get('sub') # 'sub' is the standard OpenID Connect subject identifier
    email = user_info.get('email')
    name = user_info.get('name', email) # Use name if available, otherwise use email

    if not google_id or not email:
        flash("Could not retrieve Google ID or email from Google. Please try again.", "error")
        return redirect(url_for('login'))

    # Find or create user in the database
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(google_id=google_id, email=email, name=name)
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving user to database: {str(e)}", "error")
            print(f"DB Error: {e}")
            return redirect(url_for('login'))

    login_user(user, remember=True)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


if __name__ == '__main__':
    # Check if critical OAuth configs are present before trying to run
    if not app.config.get('GOOGLE_CLIENT_ID') or \
       not app.config.get('GOOGLE_CLIENT_SECRET') or \
       not app.config.get('SQLALCHEMY_DATABASE_URI'):
        print("\n--- IMPORTANT ---")
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            print("ERROR: Database is not configured. Check DB settings in instance/config.py.")
        if not app.config.get('GOOGLE_CLIENT_ID') or not app.config.get('GOOGLE_CLIENT_SECRET'):
            print("ERROR: Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) are missing in instance/config.py.")
        print("The application might not work correctly. Please configure it and restart.")
        print("--- END IMPORTANT ---\n")

    app.run(debug=True, port=app.config.get("PORT", 5000))
