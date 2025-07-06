import os
from flask import Flask, redirect, url_for, session, render_template # Added render_template
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required # Added login_required
from requests_oauthlib import OAuth2Session

# Determine the absolute path to the instance folder
# This ensures that it works correctly whether run directly or as part of a larger project/test suite
INSTANCE_FOLDER_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

app = Flask(__name__, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)

# Create a dummy config.py in the instance folder for development if it doesn't exist
# In a production environment, this file would be created by Jenkins or a similar deployment tool.
config_file_path = os.path.join(app.instance_path, 'config.py')

if not os.path.exists(config_file_path):
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)
    with open(config_file_path, 'w') as f:
        f.write("GOOGLE_CLIENT_ID = 'YOUR_DUMMY_GOOGLE_CLIENT_ID'\n") # Use dummy values for auto-generated file
        f.write("GOOGLE_CLIENT_SECRET = 'YOUR_DUMMY_GOOGLE_CLIENT_SECRET'\n")
        f.write("GEMINI_API_KEY = 'YOUR_DUMMY_GEMINI_API_KEY'\n")
        f.write("ADMIN_EMAIL = 'dummy_admin@example.com'\n")
        f.write("SECRET_KEY = 'supersecretkey_dev_only_auto_generated'\n")
        app.logger.info(f"Created a dummy config.py at {config_file_path}")


# Load the configuration from instance/config.py
# silent=False means it will raise an error if config.py is missing (after attempting to create it)
# This helps catch issues if the config is truly missing and not auto-creatable.
try:
    app.config.from_pyfile('config.py', silent=False)
    app.logger.info(f"Loaded configuration from {config_file_path}")
except FileNotFoundError:
    app.logger.error(f"CRITICAL: instance/config.py not found and could not be auto-created. Please ensure it exists.")
    # Depending on strictness, you might want to exit or raise a more severe error.
    # For now, we'll let it proceed, but Flask-Login will fail without a SECRET_KEY.

# Ensure SECRET_KEY is set, as it's critical for sessions
if not app.config.get('SECRET_KEY'):
    app.logger.warning("SECRET_KEY not found in instance/config.py or not loaded. Using a default development key. THIS IS INSECURE FOR PRODUCTION.")
    app.config['SECRET_KEY'] = 'supersecretkey_dev_default_emergency' # Default if not in config

# Flask-Login requires a secret key to sign session cookies
if not app.config.get('SECRET_KEY'): # Check again, in case the default above also failed (which it shouldn't)
    # This state should ideally be unreachable if the above default is set.
    raise RuntimeError("The SECRET_KEY configuration variable must be set and was not found or auto-generated.")

# OAuth 2 client setup
client_id = app.config['GOOGLE_CLIENT_ID']
client_secret = app.config['GOOGLE_CLIENT_SECRET']
redirect_uri = 'http://localhost:5000/google/callback' # Make sure this matches the one in Google Console
auth_url = 'https://accounts.google.com/o/oauth2/auth'
token_url = 'https://accounts.google.com/o/oauth2/token'
scope = ['openid', 'email', 'profile']

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "show_login_page" # Where to redirect if user tries to access protected page

class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

    @staticmethod
    def get(user_id):
        # In a real app, you'd fetch the user from a database
        # For this example, we'll store the user in the session
        user_data = session.get('user_data')
        if user_data and user_data['id'] == user_id:
            return User(user_data['id'], user_data['name'], user_data['email'])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/login_page') # Renamed to avoid conflict with login function
def show_login_page():
    return render_template('login.html')

@app.route('/login/google') # Route to initiate Google OAuth
def login():
    google = OAuth2Session(client_id, scope=scope, redirect_uri=redirect_uri)
    authorization_url, state = google.authorization_url(auth_url, access_type='offline', prompt='select_account')
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/google/callback')
def callback():
    # Need to import request and render_template from flask
    from flask import request, render_template # Make sure render_template is imported
    google = OAuth2Session(client_id, redirect_uri=redirect_uri, state=session['oauth_state'])
    try:
        token = google.fetch_token(token_url, client_secret=client_secret, authorization_response=request.url)
    except Exception as e:
        # Log the error and show an error page or redirect
        app.logger.error(f"Error fetching token: {e}")
        app.logger.error(f"Request URL: {request.url}")
        # You might want to create an error.html template
        return "Error during authentication. Please try again. Check server logs for details.", 500


    # Fetch user info
    try:
        user_info_response = google.get('https://www.googleapis.com/oauth2/v1/userinfo')
        user_info_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        user_info = user_info_response.json()
    except Exception as e:
        app.logger.error(f"Error fetching user info: {e}")
        return "Error fetching user information. Please try again.", 500


    user = User(id=user_info.get('id'), name=user_info.get('name'), email=user_info.get('email'))

    # Store user data in session (in a real app, you'd save to DB)
    session['user_data'] = {'id': user.id, 'name': user.name, 'email': user.email}

    login_user(user)
    return redirect(url_for('home'))

@app.route('/')
def index(): # Renamed to index, home will be protected
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return redirect(url_for('show_login_page'))


@app.route('/home') # Protected home page
@login_required # Add this decorator
def home():
    return f'Hello, {current_user.name}! You are logged in. <a href="/logout">Logout</a>'

@app.route('/logout')
@login_required # Should be logged in to logout
def logout():
    logout_user()
    session.clear() # Clear the session to remove user_data and oauth_state
    return redirect(url_for('index'))

if __name__ == '__main__':
    # This is important for OAuth2Session to work with HTTP.
    # In production, you'd use HTTPS.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(debug=True)
