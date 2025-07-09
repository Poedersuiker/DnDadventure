import os
from flask import Flask, redirect, url_for, session, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables from .env if it exists, for local development
if os.path.exists('.env'):
    load_dotenv()

# Initialize Flask app object globally, but configure within create_app
app = Flask(__name__, instance_relative_config=True)

# --- Default Configuration Loading (before create_app) ---
if not os.path.exists('config_default.py'):
    with open('config_default.py', 'w') as f:
        f.write("# Default configuration values (can be empty)\n")
app.config.from_object('config_default')

# --- Instance Configuration Loading (before create_app) ---
# This helps ensure that app.config is populated early,
# though for app factory pattern, it's often done inside create_app.
# We'll also do it inside create_app to ensure it's definitely loaded for the app instance.
try:
    app.config.from_pyfile('config.py', silent=True) # Load instance config if available
except FileNotFoundError:
    print("INFO: Instance configuration 'instance/config.py' not found. Will rely on defaults or env vars.")


# --- Initialize Extensions (globally, to be initialized with app in create_app) ---
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'login' # Route name for the login page
oauth = OAuth()
google = None # Will be initialized by initialize_oauth

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

# --- Google OAuth Client Initialization Function ---
def initialize_oauth_client(current_app):
    global google
    google = oauth.register(
        name='google',
        client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        access_token_url='https://accounts.google.com/o/oauth2/token',
        client_kwargs={'scope': 'openid email profile'},
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
    )

# --- Google Authorization View Function (no decorator here) ---
def google_authorize_view():
    try:
        token = google.authorize_access_token()
    except Exception as e:
        flash(f"Authorization with Google failed: {str(e)}", "error")
        print(f"OAuth Error during token authorization: {e}")
        return redirect(url_for('login'))

    if not token: # Simpler check, userinfo might be fetched later or be part of id_token
        flash("Authorization with Google failed: No token received.", "error")
        return redirect(url_for('login'))

    # Fetch userinfo using the token. Authlib typically handles this via server_metadata_url
    # or by parsing the id_token which is often included.
    try:
        # user_info = token.get('userinfo') # if userinfo is directly in the token (OIDC compliant)
        # if not user_info and 'id_token' in token: # try parsing id_token
        #     user_info = google.parse_id_token(token) # This is a common way
        user_info = google.userinfo(token=token) # Preferred way if client supports it
    except Exception as e:
        flash(f"Failed to fetch user information from Google: {str(e)}", "error")
        print(f"OAuth Error during userinfo fetch: {e}")
        return redirect(url_for('login'))

    if not user_info:
        flash("Failed to fetch user information from Google.", "error")
        return redirect(url_for('login'))

    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name', email)

    if not google_id or not email:
        flash("Could not retrieve Google ID or email from Google. Please try again.", "error")
        return redirect(url_for('login'))

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

# --- App Factory ---
def create_app_instance(flask_app_obj):
    # Ensure instance folder exists
    try:
        os.makedirs(flask_app_obj.instance_path, exist_ok=True)
    except OSError as e:
        print(f"Error creating instance path {flask_app_obj.instance_path}: {e}")

    # Load instance config again, explicitly for this app instance
    try:
        flask_app_obj.config.from_pyfile('config.py', silent=False)
        print(f"Successfully loaded instance config from: {os.path.join(flask_app_obj.instance_path, 'config.py')}")
    except FileNotFoundError:
        print(f"IMPORTANT: Configuration file 'instance/config.py' not found. "
              f"Application may not work correctly. Please create it from 'instance/config.py.example'.")
    except Exception as e:
        print(f"Error loading instance config: {e}")


    # Ensure SECRET_KEY is set after instance config loading
    if not flask_app_obj.config.get('SECRET_KEY'):
        print("WARNING: SECRET_KEY is not set in instance/config.py. Using a default insecure key.")
        flask_app_obj.config['SECRET_KEY'] = 'dev_secret_key_please_change_in_production_if_not_set_in_config'

    # --- Database URI Construction (moved inside create_app_instance) ---
    db_type = flask_app_obj.config.get('DB_TYPE', 'sqlite')
    flask_app_obj.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if db_type == 'sqlite':
        db_path_config = flask_app_obj.config.get('DB_PATH', 'development.db')
        if not os.path.isabs(db_path_config):
            db_full_path = os.path.join(flask_app_obj.instance_path, db_path_config)
        else:
            db_full_path = db_path_config
        flask_app_obj.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_full_path}'
    # ... (other DB types - mysql, postgresql - logic remains similar) ...
    elif db_type in ['mysql', 'mariadb', 'mysql+pymysql']:
        user = flask_app_obj.config.get('DB_USER')
        password = flask_app_obj.config.get('DB_PASSWORD')
        host = flask_app_obj.config.get('DB_HOST')
        port = flask_app_obj.config.get('DB_PORT')
        dbname = flask_app_obj.config.get('DB_NAME')
        if not all([user, password, host, port, dbname]):
            print(f"WARNING: Missing MySQL/MariaDB config. SQLALCHEMY_DATABASE_URI not set.")
            flask_app_obj.config['SQLALCHEMY_DATABASE_URI'] = None
        else:
            flask_app_obj.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}'
    elif db_type in ['postgresql', 'postgresql+psycopg2']:
        user = flask_app_obj.config.get('DB_USER')
        password = flask_app_obj.config.get('DB_PASSWORD')
        host = flask_app_obj.config.get('DB_HOST')
        port = flask_app_obj.config.get('DB_PORT')
        dbname = flask_app_obj.config.get('DB_NAME')
        if not all([user, password, host, port, dbname]):
            print(f"WARNING: Missing PostgreSQL config. SQLALCHEMY_DATABASE_URI not set.")
            flask_app_obj.config['SQLALCHEMY_DATABASE_URI'] = None
        else:
            flask_app_obj.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'
    else:
        print(f"WARNING: Unsupported DB_TYPE: {db_type}. Falling back to default SQLite in instance folder.")
        db_full_path = os.path.join(flask_app_obj.instance_path, 'fallback_default.db')
        flask_app_obj.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_full_path}'

    print(f"Using database URI: {flask_app_obj.config.get('SQLALCHEMY_DATABASE_URI')}")


    # Initialize extensions with the app object
    if flask_app_obj.config.get('SQLALCHEMY_DATABASE_URI'):
        db.init_app(flask_app_obj)
    else:
        print("CRITICAL: SQLALCHEMY_DATABASE_URI is not set. Database functionality will be disabled.")

    login_manager.init_app(flask_app_obj)
    oauth.init_app(flask_app_obj)
    initialize_oauth_client(flask_app_obj) # Initialize Google OAuth client

    # Dynamically add the route for the Google callback
    redirect_uri_str = flask_app_obj.config.get('GOOGLE_REDIRECT_URI')
    if redirect_uri_str:
        try:
            parsed_uri = urlparse(redirect_uri_str)
            callback_path = parsed_uri.path
            if callback_path and callback_path.startswith('/'):
                # Using a fixed endpoint name 'google.authorize' for url_for()
                flask_app_obj.add_url_rule(callback_path, endpoint='google.authorize', view_func=google_authorize_view, methods=['GET', 'POST'])
                print(f"Dynamically added Google OAuth callback route: {callback_path} with endpoint 'google.authorize'")
            else:
                print(f"ERROR: Could not parse a valid path from GOOGLE_REDIRECT_URI: '{redirect_uri_str}'. Path was: '{callback_path}'")
        except Exception as e:
            print(f"ERROR: Exception while parsing GOOGLE_REDIRECT_URI ('{redirect_uri_str}'): {e}")
    else:
        print("ERROR: GOOGLE_REDIRECT_URI not found in config. Cannot set Google callback route dynamically. Login will likely fail.")


    with flask_app_obj.app_context():
        if flask_app_obj.config.get('SQLALCHEMY_DATABASE_URI'):
            try:
                db.create_all()
                print("Database tables created or already exist.")
            except Exception as e:
                print(f"Error during db.create_all(): {e}")
        else:
            print("Skipping db.create_all() because SQLALCHEMY_DATABASE_URI is not set.")

    return flask_app_obj

# Create the app using the factory, passing the global 'app' object
app = create_app_instance(app)

# --- Static Routes (defined after app is created and configured) ---
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
def login_google_route():
    if not app.config.get('GOOGLE_CLIENT_ID') or not app.config.get('GOOGLE_CLIENT_SECRET'):
        flash("Google OAuth is not configured on the server. Please check your instance/config.py.", "error")
        return redirect(url_for('login'))

    configured_redirect_uri = app.config.get('GOOGLE_REDIRECT_URI')
    if not configured_redirect_uri:
        flash("CRITICAL: GOOGLE_REDIRECT_URI is not configured in instance/config.py. Cannot initiate Google login.", "error")
        print("CRITICAL: GOOGLE_REDIRECT_URI is not configured.")
        return redirect(url_for('login'))

    if not configured_redirect_uri.startswith(('http://', 'https://')):
        flash("CRITICAL: GOOGLE_REDIRECT_URI in config must be an absolute URL (e.g., http://localhost:5000/authorize).", "error")
        print(f"CRITICAL: GOOGLE_REDIRECT_URI ('{configured_redirect_uri}') is not absolute.")
        return redirect(url_for('login'))

    # The redirect_uri for google.authorize_redirect must be the one Google sends the user back to,
    # which is exactly what's in GOOGLE_REDIRECT_URI.
    return google.authorize_redirect(configured_redirect_uri)


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
       not app.config.get('SQLALCHEMY_DATABASE_URI') or \
       not app.config.get('GOOGLE_REDIRECT_URI'):
        print("\n--- IMPORTANT STARTUP WARNINGS ---")
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            print("ERROR: Database is not configured. Check DB settings in instance/config.py.")
        if not app.config.get('GOOGLE_CLIENT_ID') or not app.config.get('GOOGLE_CLIENT_SECRET'):
            print("ERROR: Google OAuth client credentials missing in instance/config.py.")
        if not app.config.get('GOOGLE_REDIRECT_URI'):
            print("ERROR: GOOGLE_REDIRECT_URI is missing in instance/config.py. Google login will fail.")
        print("The application might not work correctly. Please configure it and restart.")
        print("--- END IMPORTANT STARTUP WARNINGS ---\n")

    app.run(debug=True, port=app.config.get("PORT", 5000))
