import os
from flask import Flask, redirect, url_for, session, render_template, flash, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from urllib.parse import urlparse
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.exc import OperationalError, ArgumentError

# Load environment variables from .env if it exists, for local development
if os.path.exists('.env'):
    load_dotenv()

# Initialize Flask app object globally, but configure within create_app
app = Flask(__name__, instance_relative_config=True)
socketio = SocketIO(app)

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
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def get_id(self): # Required by Flask-Login
        return str(self.id)

# --- Race and Trait Models ---
class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    desc = db.Column(db.Text, nullable=True)
    is_subrace = db.Column(db.Boolean, default=False)
    document = db.Column(db.String(255), nullable=True) # URL to the document
    subrace_of_key = db.Column(db.String(100), db.ForeignKey('race.key'), nullable=True) # Foreign key to self for subraces

    traits = db.relationship('Trait', backref='race', lazy=True, cascade="all, delete-orphan")
    subraces = db.relationship('Race', backref=db.backref('parent_race', remote_side=[key]), lazy='dynamic')


class Trait(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    desc = db.Column(db.Text, nullable=False)

# --- D&D Class and Archetype Models ---
class DndClass(db.Model):
    __tablename__ = 'dnd_class' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    desc = db.Column(db.Text, nullable=True)
    hit_dice = db.Column(db.String(50), nullable=True)
    hp_at_1st_level = db.Column(db.String(255), nullable=True)
    hp_at_higher_levels = db.Column(db.String(255), nullable=True)
    prof_armor = db.Column(db.String(255), nullable=True)
    prof_weapons = db.Column(db.String(255), nullable=True)
    prof_tools = db.Column(db.String(255), nullable=True)
    prof_saving_throws = db.Column(db.String(255), nullable=True)
    prof_skills = db.Column(db.Text, nullable=True) # Can be long
    equipment = db.Column(db.Text, nullable=True)
    table = db.Column(db.Text, nullable=True) # For class progression tables
    spellcasting_ability = db.Column(db.String(50), nullable=True)
    subtypes_name = db.Column(db.String(100), nullable=True) # e.g., "Primal Paths"
    document_slug = db.Column(db.String(100), nullable=True)
    document_title = db.Column(db.String(255), nullable=True)
    # document_license_url = db.Column(db.String(255), nullable=True) # Not critical for now
    # document_url = db.Column(db.String(255), nullable=True) # Not critical for now

    archetypes = db.relationship('Archetype', backref='dnd_class', lazy=True, cascade="all, delete-orphan")

# --- Background and Benefit Models ---
class Background(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    desc = db.Column(db.Text, nullable=True)
    document = db.Column(db.String(255), nullable=True) # URL to the document

    benefits = db.relationship('Benefit', backref='background', lazy=True, cascade="all, delete-orphan")

class Benefit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    background_id = db.Column(db.Integer, db.ForeignKey('background.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    desc = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(100), nullable=True) # e.g., "ability_score", "skill_proficiency"


class Archetype(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dnd_class_slug = db.Column(db.String(100), db.ForeignKey('dnd_class.slug'), nullable=False)
    slug = db.Column(db.String(100), nullable=False) # Archetype specific slug
    name = db.Column(db.String(255), nullable=False)
    desc = db.Column(db.Text, nullable=True)
    document_slug = db.Column(db.String(100), nullable=True)
    document_title = db.Column(db.String(255), nullable=True)
    # document_license_url = db.Column(db.String(255), nullable=True)
    # document_url = db.Column(db.String(255), nullable=True)

    __table_args__ = (db.UniqueConstraint('dnd_class_slug', 'slug', name='uq_archetype_class_slug'),)


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
        # authorize_url is discovered via server_metadata_url
        # access_token_url is discovered via server_metadata_url
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
            # Explicitly define expected issuer for the ID token to resolve 'invalid_claim: Invalid claim 'iss'' errors.
            # Google's standard issuer is 'https://accounts.google.com'.
            'claims_options': {
                'iss': {'essential': True, 'values': ['https://accounts.google.com']}
            }
        }
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
    admin_email_from_config = app.config.get('ADMIN_EMAIL')
    made_changes = False

    if not user:
        user = User(google_id=google_id, email=email, name=name)
        # Set admin status based on email match during creation
        if admin_email_from_config and email == admin_email_from_config:
            user.is_admin = True
        else:
            user.is_admin = False # Explicitly set for new users
        try:
            db.session.add(user)
            # No commit here yet, will commit after potential admin status update
            made_changes = True
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user in database: {str(e)}", "error")
            print(f"DB Error (create user): {e}")
            return redirect(url_for('login'))
    else:
        # User exists, check if admin status needs to be updated
        # This handles cases where ADMIN_EMAIL might change or was set after user creation
        should_be_admin = bool(admin_email_from_config and email == admin_email_from_config)
        if user.is_admin != should_be_admin:
            user.is_admin = should_be_admin
            made_changes = True

    if made_changes:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating user data in database: {str(e)}", "error")
            print(f"DB Error (update user): {e}")
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

# --- Admin Panel Page Route ---
@app.route('/admin_panel')
@login_required
def admin_panel_route():
    if not current_user.is_admin:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('index'))
    return render_template('admin_panel.html')

# --- Importer Panel Page Route ---
@app.route('/importer_panel')
@login_required
def importer_panel_route():
    if not current_user.is_admin:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('index'))
    return render_template('importer_panel.html')

# --- Admin API/Action Routes (still need protection) ---
@app.route('/admin/db_status')
@login_required
def admin_db_status():
    if not current_user.is_admin:
        return {"error": "Unauthorized"}, 403

    config_data = {
        "current_db_type": app.config.get('DB_TYPE'),
        "sqlite": {
            "path": app.config.get('DB_PATH')
        },
        "mariadb": {
            "host": app.config.get('DB_HOST'),
            "port": app.config.get('DB_PORT'),
            "user": app.config.get('DB_USER'),
            "name": app.config.get('DB_NAME'),
            # Password is intentionally omitted for security
        }
    }
    return config_data

@app.route('/admin/check_sqlite', methods=['POST'])
@login_required
def admin_check_sqlite():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    db_path_config = app.config.get('DB_PATH', 'default_check.db')
    instance_path = app.instance_path

    if not os.path.isabs(db_path_config):
        sqlite_db_full_path = os.path.join(instance_path, db_path_config)
    else:
        sqlite_db_full_path = db_path_config

    db_dir = os.path.dirname(sqlite_db_full_path)

    messages = []
    errors = []

    # Check 1: Directory path and permissions
    if not os.path.exists(db_dir):
        errors.append(f"Directory for SQLite database does not exist: {db_dir}")
    elif not os.access(db_dir, os.W_OK | os.X_OK): # Check for write and execute (needed for directory access)
        errors.append(f"Directory for SQLite database is not writable or accessible: {db_dir}")
    else:
        messages.append(f"SQLite directory exists and is accessible: {db_dir}")

    # Check 2: File path and permissions (if file exists)
    if os.path.exists(sqlite_db_full_path):
        messages.append(f"SQLite file found at: {sqlite_db_full_path}")
        if not os.access(sqlite_db_full_path, os.R_OK):
            errors.append(f"SQLite file is not readable: {sqlite_db_full_path}")
        if not os.access(sqlite_db_full_path, os.W_OK):
            errors.append(f"SQLite file is not writable: {sqlite_db_full_path}")
        else:
            messages.append(f"SQLite file appears readable and writable: {sqlite_db_full_path}")
    else:
        messages.append(f"SQLite file does not exist at: {sqlite_db_full_path}. Will be created if used.")
        # If the file doesn't exist, we primarily rely on directory writability.

    # Check 3: Attempt connection and simple query
    if not errors: # Only attempt if basic path checks are somewhat okay
        sqlite_uri = f'sqlite:///{sqlite_db_full_path}'
        try:
            engine = create_engine(sqlite_uri)
            with engine.connect() as connection:
                connection.execute(db.text("SELECT 1"))
            messages.append("Successfully connected to SQLite and executed a test query.")
        except OperationalError as e:
            errors.append(f"SQLite connection/query failed: {str(e)}")
        except ArgumentError as e: # Handles issues like malformed URI
            errors.append(f"SQLite configuration error (e.g. bad path): {str(e)}")
        except Exception as e:
            errors.append(f"An unexpected error occurred with SQLite: {str(e)}")

    if errors:
        return jsonify({"status": "error", "messages": errors, "details": messages}), 400
    else:
        return jsonify({"status": "success", "messages": messages})


@app.route('/admin/check_mariadb', methods=['POST'])
@login_required
def admin_check_mariadb():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    messages = []
    errors = []

    user = app.config.get('DB_USER')
    password = app.config.get('DB_PASSWORD')
    host = app.config.get('DB_HOST')
    port = app.config.get('DB_PORT')
    dbname = app.config.get('DB_NAME')

    if not all([user, host, port, dbname]): # Password can be empty for some setups
        errors.append("MariaDB/MySQL connection parameters (user, host, port, dbname) are not fully configured in instance/config.py.")
        return jsonify({"status": "error", "messages": errors}), 400

    #pymysql is specified in create_app_instance, so using it here too for consistency
    mariadb_uri = f'mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}'

    try:
        engine = create_engine(mariadb_uri, connect_args={'connect_timeout': 5}) # 5 second timeout
        with engine.connect() as connection:
            connection.execute(db.text("SELECT 1"))
        messages.append("Successfully connected to MariaDB/MySQL and executed a test query.")
    except OperationalError as e: # Catches incorrect password, host not found, db not found, access denied etc.
        errors.append(f"MariaDB/MySQL connection/query failed: {str(e)}")
    except ArgumentError as e: # Handles issues like malformed URI / driver not found
         errors.append(f"MariaDB/MySQL configuration error (e.g. driver issue): {str(e)}")
    except Exception as e:
        errors.append(f"An unexpected error occurred with MariaDB/MySQL: {str(e)}")

    if errors:
        return jsonify({"status": "error", "messages": errors, "details": messages}), 400
    else:
        return jsonify({"status": "success", "messages": messages})

# --- Database Helper Functions for Migration ---
def get_sqlite_engine(current_app):
    db_path_config = current_app.config.get('DB_PATH')
    if not db_path_config:
        raise ValueError("SQLite DB_PATH is not configured.")

    instance_path = current_app.instance_path
    if not os.path.isabs(db_path_config):
        sqlite_db_full_path = os.path.join(instance_path, db_path_config)
    else:
        sqlite_db_full_path = db_path_config

    sqlite_uri = f'sqlite:///{sqlite_db_full_path}'
    return create_engine(sqlite_uri)

def get_mariadb_engine(current_app):
    user = current_app.config.get('DB_USER')
    password = current_app.config.get('DB_PASSWORD')
    host = current_app.config.get('DB_HOST')
    port = current_app.config.get('DB_PORT')
    dbname = current_app.config.get('DB_NAME')

    if not all([user, host, port, dbname]): # Password can be empty
        raise ValueError("MariaDB/MySQL connection parameters are not fully configured.")

    mariadb_uri = f'mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}'
    return create_engine(mariadb_uri)

# --- Core Migration Logic ---
def perform_migration(source_engine, target_engine, app_context, log_callback):
    log_callback("Starting migration...")

    # We will use the tables defined in the Flask app's db.Model (db.metadata)
    # as the canonical schema for both source and target.
    with app_context: # Ensures db.metadata is correctly populated based on models
        # db.metadata.tables is an ImmutableProperties dictionary.
        # Convert to a regular dictionary for consistent iteration order if needed,
        # or just iterate directly if order isn't critical beyond SQLAlchemy's own handling.
        # For foreign key reasons, SQLAlchemy usually orders them correctly for create/drop.
        defined_tables_map = db.metadata.tables
        log_callback(f"Canonical tables defined in models: {list(defined_tables_map.keys())}")

        # Prepare target database: drop and recreate tables based on canonical schema
        log_callback(f"Preparing target database: dropping and recreating tables...")
        try:
            # Create a new MetaData object for target operations to avoid conflicts
            # if db.metadata is globally bound or used by the main app.
            # Then, reflect the app's table definitions into this new MetaData object.
            target_operation_metadata = MetaData()
            for table_name, table_obj in defined_tables_map.items():
                table_obj.to_metadata(target_operation_metadata) # This copies table definitions

            # Drop tables using the new metadata object, ensuring it's against the target_engine
            target_operation_metadata.drop_all(bind=target_engine, checkfirst=True)
            log_callback("Dropped existing tables in target.")

            # Recreate tables using the new metadata object
            target_operation_metadata.create_all(bind=target_engine, checkfirst=True)
            log_callback("Recreated tables in target based on current models.")

        except Exception as e:
            err_msg = f"Error preparing target database: {str(e)}"
            log_callback(err_msg)
            print(f"[Migration Error] {err_msg}") # Also print to console
            raise # Re-raise to stop migration if target prep fails

        # Transfer data for each table defined in our models
        total_rows_transferred = 0
        processed_tables_count = 0

        # Use a single connection for source and target for the duration of data copy
        with source_engine.connect() as s_conn, target_engine.connect() as t_conn:
            # It's often better to process tables in an order that respects dependencies,
            # though for simple cases or if all tables are independent, this might not be an issue.
            # SQLAlchemy's db.metadata.sorted_tables can be useful here if explicit order is needed.
            # For now, iterating through defined_tables_map.items() which has User as the only table.
            for table_name, table_obj_from_model in defined_tables_map.items():
                log_callback(f"Processing table: {table_name}...")
                print(f"[Migration] Processing table: {table_name}...")

                try:
                    # Fetch all data from the source table.
                    # The table_obj_from_model (from db.metadata) is used to construct the SELECT.
                    # This assumes the source table has at least these columns.
                    select_stmt = table_obj_from_model.select()
                    result = s_conn.execute(select_stmt)
                    rows = result.fetchall() # Fetches all rows as RowProxy objects

                    if not rows:
                        log_callback(f"Table {table_name} is empty in source. Skipping.")
                        print(f"[Migration] Table {table_name} is empty in source.")
                        processed_tables_count += 1
                        continue

                    log_callback(f"Fetched {len(rows)} rows from source table {table_name}.")
                    print(f"[Migration] Fetched {len(rows)} rows from source table {table_name}.")

                    # Convert RowProxy objects to dictionaries for insertion.
                    data_to_insert = [dict(row._mapping) for row in rows]

                    if data_to_insert:
                        # Perform insertion into the target table.
                        # The table_obj_from_model is also our target table schema.
                        transaction = t_conn.begin()
                        try:
                            # Using the table object from our models (db.metadata) for insert.
                            t_conn.execute(table_obj_from_model.insert(), data_to_insert)
                            transaction.commit()
                            log_callback(f"Successfully inserted {len(rows)} rows into target table {table_name}.")
                            print(f"[Migration] Successfully inserted {len(rows)} rows into target table {table_name}.")
                            total_rows_transferred += len(rows)
                        except Exception as e_insert:
                            transaction.rollback()
                            err_msg = f"Error inserting data into {table_name}: {str(e_insert)}. Rolled back changes for this table."
                            log_callback(err_msg)
                            print(f"[Migration Error] {err_msg}")
                    else:
                        log_callback(f"No data to insert for table {table_name} after processing fetched rows.")
                        print(f"[Migration] No data to insert for table {table_name}.")

                except Exception as e_table_process:
                    err_msg = f"Error processing table {table_name}: {str(e_table_process)}"
                    log_callback(err_msg)
                    print(f"[Migration Error] {err_msg}")

                processed_tables_count += 1
                log_callback(f"Progress: {processed_tables_count}/{len(defined_tables_map)} tables processed.")
                print(f"[Migration] Progress: {processed_tables_count}/{len(defined_tables_map)} tables processed.")

    log_callback(f"Migration finished. Total rows transferred: {total_rows_transferred}.")
    print(f"[Migration] Migration finished. Total rows transferred: {total_rows_transferred}.")

# --- Migration Routes ---
@app.route('/admin/migrate_to_mariadb', methods=['POST'])
@login_required
def admin_migrate_to_mariadb():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    logs = []
    def log_callback(message):
        logs.append(message)
        print(f"[MigrateToMariaDB] {message}") # Also print to server console

    try:
        log_callback("Attempting migration from SQLite to MariaDB/MySQL...")
        source_engine = get_sqlite_engine(app)
        target_engine = get_mariadb_engine(app)

        # Check source connection
        try:
            with source_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log_callback("Source SQLite engine connected successfully.")
        except Exception as e:
            log_callback(f"Failed to connect to source SQLite engine: {e}")
            return jsonify({"status": "error", "logs": logs, "message": f"Failed to connect to source SQLite: {e}"}), 500

        # Check target connection
        try:
            with target_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log_callback("Target MariaDB/MySQL engine connected successfully.")
        except Exception as e:
            log_callback(f"Failed to connect to target MariaDB/MySQL engine: {e}")
            return jsonify({"status": "error", "logs": logs, "message": f"Failed to connect to target MariaDB/MySQL: {e}"}), 500

        perform_migration(source_engine, target_engine, app.app_context(), log_callback)

        # IMPORTANT: After migration, the main app's db object is still using the OLD connection.
        # The app needs to be reconfigured to use the new DB_TYPE and re-initialize SQLAlchemy.
        # This is a complex step. For now, we'll just inform the user.
        log_callback("Migration process complete. IMPORTANT: You may need to update DB_TYPE in config.py to 'mysql' (or similar) and RESTART the application for it to use the new MariaDB/MySQL database.")
        return jsonify({"status": "success", "logs": logs, "message": "Migration to MariaDB/MySQL completed. Restart required."})

    except ValueError as ve: # From get_engine if config is missing
        log_callback(f"Configuration error: {str(ve)}")
        return jsonify({"status": "error", "logs": logs, "message": str(ve)}), 400
    except Exception as e:
        log_callback(f"Migration failed: {str(e)}")
        return jsonify({"status": "error", "logs": logs, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/admin/migrate_to_sqlite', methods=['POST'])
@login_required
def admin_migrate_to_sqlite():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    logs = []
    def log_callback(message):
        logs.append(message)
        print(f"[MigrateToSQLite] {message}") # Also print to server console

    try:
        log_callback("Attempting migration from MariaDB/MySQL to SQLite...")
        source_engine = get_mariadb_engine(app)
        target_engine = get_sqlite_engine(app)

        # Check source connection
        try:
            with source_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log_callback("Source MariaDB/MySQL engine connected successfully.")
        except Exception as e:
            log_callback(f"Failed to connect to source MariaDB/MySQL engine: {e}")
            return jsonify({"status": "error", "logs": logs, "message": f"Failed to connect to source MariaDB/MySQL: {e}"}), 500

        # Check target connection
        try:
            with target_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log_callback("Target SQLite engine connected successfully.")
        except Exception as e:
            log_callback(f"Failed to connect to target SQLite engine: {e}")
            return jsonify({"status": "error", "logs": logs, "message": f"Failed to connect to target SQLite: {e}"}), 500

        perform_migration(source_engine, target_engine, app.app_context(), log_callback)

        log_callback("Migration process complete. IMPORTANT: You may need to update DB_TYPE in config.py to 'sqlite' and RESTART the application for it to use the new SQLite database.")
        return jsonify({"status": "success", "logs": logs, "message": "Migration to SQLite completed. Restart required."})

    except ValueError as ve: # From get_engine if config is missing
        log_callback(f"Configuration error: {str(ve)}")
        return jsonify({"status": "error", "logs": logs, "message": str(ve)}), 400
    except Exception as e:
        log_callback(f"Migration failed: {str(e)}")
        return jsonify({"status": "error", "logs": logs, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Helper function for Race Importer ---
# (This function will be refactored from the original admin_import_races)
def _import_races_data(app_context):
    with app_context:
        app.logger.info("Starting race import process...")
        try:
            import requests # Ensure requests is imported

            api_url = "https://api.open5e.com/v2/races/"
            races_imported_count = 0
            traits_imported_count = 0
            total_races_api = 0
            page_num = 1

            # First, get the total count of races
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            total_races_api = data.get('count', 0)

            if total_races_api == 0:
                app.logger.warning("No races found in API during import.")
                return {"status": "warning", "message": "No races found in API.", "races_imported": 0, "traits_imported": 0, "total_races_api": 0}

            current_url = api_url
            while current_url:
                app.logger.info(f"Fetching races from: {current_url}")
                response = requests.get(current_url)
                response.raise_for_status()
                page_data = response.json()
                races_on_page = page_data.get('results', [])

                for race_data in races_on_page:
                    race_key = race_data.get('key')
                    if not race_key:
                        app.logger.warning(f"Skipping race with no key: {race_data.get('name')}")
                        continue

                    existing_race = Race.query.filter_by(key=race_key).first()
                    if existing_race:
                        app.logger.info(f"Race '{race_key}' already exists. Skipping.")
                        continue

                    new_race = Race(
                        url=race_data.get('url'),
                        key=race_key,
                        name=race_data.get('name'),
                        desc=race_data.get('desc'),
                        is_subrace=race_data.get('is_subrace', False),
                        document=race_data.get('document'),
                        subrace_of_key=race_data.get('subrace_of_key')
                    )
                    subrace_of_url = race_data.get('subrace_of')
                    if subrace_of_url and isinstance(subrace_of_url, str):
                        parsed_subrace_url = urlparse(subrace_of_url)
                        path_parts = parsed_subrace_url.path.strip('/').split('/')
                        if path_parts:
                            new_race.subrace_of_key = path_parts[-1]

                    db.session.add(new_race)
                    try:
                        db.session.commit()
                    except Exception as e_commit_race:
                        db.session.rollback()
                        app.logger.error(f"Error committing race {race_key}: {str(e_commit_race)}")
                        continue

                    races_imported_count += 1

                    for trait_data in race_data.get('traits', []):
                        new_trait = Trait(
                            race_id=new_race.id,
                            name=trait_data.get('name'),
                            desc=trait_data.get('desc')
                        )
                        db.session.add(new_trait)
                        traits_imported_count += 1

                try:
                    db.session.commit() # Commit traits for the page
                except Exception as e_commit_traits:
                    db.session.rollback()
                    app.logger.error(f"Error committing traits for page {page_num}: {str(e_commit_traits)}")

                current_url = page_data.get('next')
                page_num += 1

            # Second pass to link subraces (no changes needed here for now)
            all_races = Race.query.all()
            for race in all_races:
                if race.subrace_of_key:
                    parent = Race.query.filter_by(key=race.subrace_of_key).first()
                    if not parent:
                         app.logger.warning(f"Parent race with key '{race.subrace_of_key}' not found for subrace '{race.key}'.")
            db.session.commit()

            app.logger.info(f"Race import finished. Imported {races_imported_count} races and {traits_imported_count} traits.")
            return {
                "status": "success",
                "message": f"Imported {races_imported_count} races and {traits_imported_count} traits.",
                "races_imported": races_imported_count,
                "traits_imported": traits_imported_count,
                "total_races_api": total_races_api
            }

        except requests.exceptions.RequestException as e_req:
            app.logger.error(f"Race API request failed: {str(e_req)}")
            # Ensure db.session.rollback() is called if an error occurs mid-transaction
            db.session.rollback()
            return {"status": "error", "message": f"Race API request failed: {str(e_req)}"}
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"An error occurred during race import: {str(e)}")
            return {"status": "error", "message": f"An unexpected error occurred during race import: {str(e)}"}

# --- Helper function for Class Importer ---
def _import_classes_data(app_context):
    with app_context:
        app.logger.info("Starting D&D class import process...")
        try:
            import requests

            api_url = "https://api.open5e.com/v1/classes/"
            classes_imported_count = 0
            archetypes_imported_count = 0
            total_classes_api = 0
            page_num = 1

            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            total_classes_api = data.get('count', 0)

            if total_classes_api == 0:
                app.logger.warning("No D&D classes found in API during import.")
                return {"status": "warning", "message": "No D&D classes found in API.", "classes_imported": 0, "archetypes_imported": 0, "total_classes_api": 0}

            current_url = api_url
            while current_url:
                app.logger.info(f"Fetching D&D classes from: {current_url}")
                response = requests.get(current_url)
                response.raise_for_status()
                page_data = response.json()
                classes_on_page = page_data.get('results', [])

                for class_data in classes_on_page:
                    class_slug = class_data.get('slug')
                    if not class_slug:
                        app.logger.warning(f"Skipping D&D class with no slug: {class_data.get('name')}")
                        continue

                    existing_class = DndClass.query.filter_by(slug=class_slug).first()
                    if existing_class:
                        app.logger.info(f"D&D class '{class_slug}' already exists. Skipping.")
                        # To implement update logic, one might delete existing archetypes here before adding new ones,
                        # or perform a more granular update. For now, skipping.
                        continue

                    new_dnd_class = DndClass(
                        slug=class_slug,
                        name=class_data.get('name'),
                        desc=class_data.get('desc'),
                        hit_dice=class_data.get('hit_dice'),
                        hp_at_1st_level=class_data.get('hp_at_1st_level'),
                        hp_at_higher_levels=class_data.get('hp_at_higher_levels'),
                        prof_armor=class_data.get('prof_armor'),
                        prof_weapons=class_data.get('prof_weapons'),
                        prof_tools=class_data.get('prof_tools'),
                        prof_saving_throws=class_data.get('prof_saving_throws'),
                        prof_skills=class_data.get('prof_skills'),
                        equipment=class_data.get('equipment'),
                        table=class_data.get('table'),
                        spellcasting_ability=class_data.get('spellcasting_ability'),
                        subtypes_name=class_data.get('subtypes_name'),
                        document_slug=class_data.get('document__slug'),
                        document_title=class_data.get('document__title')
                    )
                    db.session.add(new_dnd_class)
                    # Commit here to ensure the class exists for archetype foreign key reference.
                    # Consider batching commits per page for performance if this becomes an issue.
                    try:
                        db.session.commit()
                    except Exception as e_commit_class:
                        db.session.rollback()
                        app.logger.error(f"Error committing D&D class {class_slug}: {str(e_commit_class)}")
                        continue

                    classes_imported_count += 1

                    for archetype_data in class_data.get('archetypes', []):
                        archetype_slug = archetype_data.get('slug')
                        if not archetype_slug:
                            app.logger.warning(f"Skipping archetype with no slug for class '{class_slug}': {archetype_data.get('name')}")
                            continue

                        existing_archetype = Archetype.query.filter_by(dnd_class_slug=class_slug, slug=archetype_slug).first()
                        if existing_archetype:
                            app.logger.info(f"Archetype '{archetype_slug}' for class '{class_slug}' already exists. Skipping.")
                            continue

                        new_archetype = Archetype(
                            dnd_class_slug=class_slug,
                            slug=archetype_slug,
                            name=archetype_data.get('name'),
                            desc=archetype_data.get('desc'),
                            document_slug=archetype_data.get('document__slug'),
                            document_title=archetype_data.get('document__title')
                        )
                        db.session.add(new_archetype)
                        archetypes_imported_count += 1

                try:
                    db.session.commit() # Commit archetypes for the page
                except Exception as e_commit_archetypes:
                    db.session.rollback()
                    app.logger.error(f"Error committing archetypes for D&D classes on page {page_num}: {str(e_commit_archetypes)}")

                current_url = page_data.get('next')
                page_num += 1

            app.logger.info(f"D&D Class import finished. Imported {classes_imported_count} classes and {archetypes_imported_count} archetypes.")
            return {
                "status": "success",
                "message": f"Imported {classes_imported_count} D&D classes and {archetypes_imported_count} archetypes.",
                "classes_imported": classes_imported_count,
                "archetypes_imported": archetypes_imported_count,
                "total_classes_api": total_classes_api
            }

        except requests.exceptions.RequestException as e_req:
            app.logger.error(f"D&D Class API request failed: {str(e_req)}")
            db.session.rollback()
            return {"status": "error", "message": f"D&D Class API request failed: {str(e_req)}"}
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"An error occurred during D&D class import: {str(e)}")
            return {"status": "error", "message": f"An unexpected error occurred during D&D class import: {str(e)}"}

# --- Helper function for Background Importer ---
def _import_backgrounds_data(app_context):
    with app_context:
        app.logger.info("Starting background import process...")
        try:
            import requests

            api_url = "https://api.open5e.com/v2/backgrounds/"
            backgrounds_imported_count = 0
            benefits_imported_count = 0
            total_backgrounds_api = 0
            page_num = 1

            # First, get the total count
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            total_backgrounds_api = data.get('count', 0)

            if total_backgrounds_api == 0:
                app.logger.warning("No backgrounds found in API during import.")
                return {"status": "warning", "message": "No backgrounds found in API.", "backgrounds_imported": 0, "benefits_imported": 0, "total_backgrounds_api": 0}

            current_url = api_url
            while current_url:
                app.logger.info(f"Fetching backgrounds from: {current_url}")
                response = requests.get(current_url)
                response.raise_for_status()
                page_data = response.json()
                backgrounds_on_page = page_data.get('results', [])

                for bg_data in backgrounds_on_page:
                    bg_key = bg_data.get('key')
                    if not bg_key:
                        app.logger.warning(f"Skipping background with no key: {bg_data.get('name')}")
                        continue

                    existing_bg = Background.query.filter_by(key=bg_key).first()
                    if existing_bg:
                        app.logger.info(f"Background '{bg_key}' already exists. Skipping.")
                        continue

                    new_bg = Background(
                        key=bg_key,
                        name=bg_data.get('name'),
                        desc=bg_data.get('desc'),
                        document=bg_data.get('document') # Assuming document is a URL string
                    )
                    db.session.add(new_bg)
                    try:
                        db.session.commit() # Commit background to get ID for benefits
                    except Exception as e_commit_bg:
                        db.session.rollback()
                        app.logger.error(f"Error committing background {bg_key}: {str(e_commit_bg)}")
                        continue

                    backgrounds_imported_count += 1

                    for benefit_data in bg_data.get('benefits', []):
                        new_benefit = Benefit(
                            background_id=new_bg.id,
                            name=benefit_data.get('name'),
                            desc=benefit_data.get('desc'),
                            type=benefit_data.get('type')
                        )
                        db.session.add(new_benefit)
                        benefits_imported_count += 1

                try:
                    db.session.commit() # Commit benefits for the page
                except Exception as e_commit_benefits:
                    db.session.rollback()
                    app.logger.error(f"Error committing benefits for backgrounds on page {page_num}: {str(e_commit_benefits)}")

                current_url = page_data.get('next')
                page_num += 1

            app.logger.info(f"Background import finished. Imported {backgrounds_imported_count} backgrounds and {benefits_imported_count} benefits.")
            return {
                "status": "success",
                "message": f"Imported {backgrounds_imported_count} backgrounds and {benefits_imported_count} benefits.",
                "backgrounds_imported": backgrounds_imported_count,
                "benefits_imported": benefits_imported_count,
                "total_backgrounds_api": total_backgrounds_api
            }

        except requests.exceptions.RequestException as e_req:
            app.logger.error(f"Background API request failed: {str(e_req)}")
            db.session.rollback()
            return {"status": "error", "message": f"Background API request failed: {str(e_req)}"}
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"An error occurred during background import: {str(e)}")
            return {"status": "error", "message": f"An unexpected error occurred during background import: {str(e)}"}


# --- Combined Data Importer Route ---
@app.route('/admin/import_data', methods=['POST'])
@login_required
def admin_import_data():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    race_import_results = _import_races_data(app.app_context())
    class_import_results = _import_classes_data(app.app_context())
    background_import_results = _import_backgrounds_data(app.app_context())

    # Combine results
    final_status = "success"
    messages = []

    if race_import_results["status"] == "error":
        final_status = "error" # Or "partial_error" / "partial_success"
        messages.append(f"Race import error: {race_import_results.get('message', 'Unknown error')}")
    else:
        messages.append(f"Race import: {race_import_results.get('message', 'Completed')}")

    if class_import_results["status"] == "error":
        final_status = "error" if final_status != "success" else "partial_error"
        messages.append(f"Class import error: {class_import_results.get('message', 'Unknown error')}")
    else:
        messages.append(f"Class import: {class_import_results.get('message', 'Completed')}")

    if background_import_results["status"] == "error":
        final_status = "error" if final_status != "success" else "partial_error"
        messages.append(f"Background import error: {background_import_results.get('message', 'Unknown error')}")
    else:
        messages.append(f"Background import: {background_import_results.get('message', 'Completed')}")

    combined_message = ". ".join(messages)
    http_status_code = 500 if final_status == "error" else 200 # Adjusted based on overall success

    return jsonify({
        "status": final_status,
        "message": combined_message,
        "races_imported": race_import_results.get("races_imported", 0),
        "traits_imported": race_import_results.get("traits_imported", 0),
        "total_races_api": race_import_results.get("total_races_api", 0),
        "classes_imported": class_import_results.get("classes_imported", 0),
        "archetypes_imported": class_import_results.get("archetypes_imported", 0),
        "total_classes_api": class_import_results.get("total_classes_api", 0),
        "backgrounds_imported": background_import_results.get("backgrounds_imported", 0),
        "benefits_imported": background_import_results.get("benefits_imported", 0),
        "total_backgrounds_api": background_import_results.get("total_backgrounds_api", 0)
    }), http_status_code


@socketio.on('message')
def handle_message(message):
    print('received message: ' + message)
    emit('message', message, broadcast=True)


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

    socketio.run(app, debug=True, port=app.config.get("PORT", 5000))
