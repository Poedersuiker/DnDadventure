import os
import json # Added for loading races_database.json
from flask import Flask, redirect, url_for, session, render_template, jsonify, request as flask_request # Added render_template, jsonify, flask_request
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required # Added login_required
from requests_oauthlib import OAuth2Session
import requests # Moved import requests to top level
import threading # For background tasks
import time # For managing background task status

# Import the main function from your script
from process_races import main as process_races_main


from werkzeug.middleware.proxy_fix import ProxyFix

# Determine the absolute path to the instance folder
# This ensures that it works correctly whether run directly or as part of a larger project/test suite
INSTANCE_FOLDER_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

app = Flask(__name__, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)

# If the app is behind a proxy (common in production), ProxyFix helps it understand
# the correct scheme (http/https), host, etc., from X-Forwarded-* headers.
# x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1 specifies trusting one hop for these headers.
# Adjust the number of hops if you have multiple proxies.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


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
# Make redirect_uri configurable, defaulting for local development with the new path
redirect_uri = app.config.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/authorized')
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

@app.route('/auth/google/authorized') # Changed route
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
    character_creation_steps = [
        "1. Choose a Race",
        "2. Choose a Class",
        "3. Determine Ability Scores",
        "4. Describe Your Character",
        "5. Choose Equipment",
        "6. Come Together"
    ]
    # Placeholder for actual character data
    user_characters = [
        # {"name": "Gandalf", "race": "Human", "class": "Wizard"},
        # {"name": "Legolas", "race": "Elf", "class": "Ranger"}
    ]
    return render_template('home.html', character_creation_steps=character_creation_steps, characters=user_characters)

@app.route('/logout')
@login_required # Should be logged in to logout
def logout():
    logout_user()
    session.clear() # Clear the session to remove user_data and oauth_state
    return redirect(url_for('index'))

@app.route('/admin/get_structure')
@login_required
def get_structure():
    # from flask import request, jsonify # Import jsonify -> request is now flask_request
    # import requests # Import requests module -> Moved to top

    url = flask_request.args.get('url')
    if not url:
        return jsonify({"error": "URL parameter is missing"}), 400

    all_results = []
    current_url = url
    first_page_data = None

    try:
        while current_url:
            response = requests.get(current_url)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            data = response.json()

            if not first_page_data:
                first_page_data = data.copy() # Keep a copy of the first page structure
                # Remove 'results' from first_page_data if it will be replaced by combined list
                # Or, ensure it's correctly updated later. For now, we'll build it up.

            if 'results' in data and isinstance(data['results'], list):
                all_results.extend(data['results'])

            current_url = data.get('next') # Get the next page URL

        # Combine results: start with the structure of the first page,
        # then update 'results' and potentially 'count'.
        if first_page_data:
            final_data = first_page_data
            final_data['results'] = all_results
            final_data['count'] = len(all_results) # Update count to reflect all fetched results
            if not all_results and 'results' not in final_data: # Ensure 'results' key exists
                 final_data['results'] = []
            # Remove 'next' and 'previous' if they relate to the last fetched page
            final_data.pop('next', None)
            final_data.pop('previous', None) # Or set to None if appropriate for the combined view
        else: # Should not happen if initial URL is valid and returns data
            return jsonify({"error": "No data received from the initial URL"}), 500

        return jsonify(final_data)

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching URL {url}: {e}")
        return jsonify({"error": str(e)}), 500
    except ValueError as e:  # Catches JSON decoding errors
        app.logger.error(f"Error decoding JSON from {url}: {e}")
        return jsonify({"error": "Invalid JSON response"}), 500

# --- Race Processing ---
# Global state for race processing
processing_status = {
    'status': 'idle', # idle, running, complete, error
    'message': 'Not started.',
    'current': 0,
    'total': 0,
    'output_file': None,
    'error_details': None
}
processing_lock = threading.Lock() # To prevent multiple concurrent processing runs

def update_processing_status(update_dict):
    """Callback function for process_races.py to update Flask app's status."""
    with processing_lock:
        for key, value in update_dict.items():
            processing_status[key] = value
        # Ensure essential keys always exist
        if 'status' not in processing_status: processing_status['status'] = 'unknown'
        if 'message' not in processing_status: processing_status['message'] = ''
        if 'current' not in processing_status: processing_status['current'] = 0
        if 'total' not in processing_status: processing_status['total'] = 0
    app.logger.info(f"Race processing status updated: {processing_status}")


def run_race_processing_task():
    """The actual task that runs process_races_main."""
    app.logger.info("Background race processing task started.")
    try:
        # Initialize status before starting
        update_processing_status({
            'status': 'running',
            'message': 'Initializing race data processing...',
            'current': 0,
            'total': 0,
            'output_file': None,
            'error_details': None
        })
        process_races_main(status_updater=update_processing_status)
        # The script itself should call update_processing_status with 'complete' or 'error'
    except Exception as e:
        app.logger.error(f"Exception in race processing thread: {e}", exc_info=True)
        update_processing_status({
            'status': 'error',
            'message': 'An unexpected error occurred in the processing thread.',
            'error_details': str(e),
            'output_file': None
        })
    app.logger.info("Background race processing task finished.")


@app.route('/admin/run-race-processing', methods=['POST'])
@login_required
def start_race_processing():
    with processing_lock:
        if processing_status['status'] == 'running':
            return jsonify({"error": "Race processing is already in progress."}), 409 # Conflict

        # Reset status for a new run
        processing_status.update({
            'status': 'running',
            'message': 'Starting race data processing...',
            'current': 0,
            'total': 0,
            'output_file': None,
            'error_details': None
        })

        app.logger.info("Attempting to start race processing thread.")
        thread = threading.Thread(target=run_race_processing_task)
        thread.daemon = True # Allows main program to exit even if threads are running
        thread.start()
        app.logger.info("Race processing thread started.")
        return jsonify({"message": "Race processing initiated."})

@app.route('/admin/get-race-processing-status', methods=['GET'])
@login_required
def get_race_processing_status():
    with processing_lock:
        # Make a copy to avoid issues if the dict is modified while creating the response
        current_status_copy = processing_status.copy()
    return jsonify(current_status_copy)

# --- End Race Processing ---

# --- Character Creation ---
RACES_FILE = 'races_database.json'

def load_races():
    try:
        with open(RACES_FILE, 'r') as f:
            races_data = json.load(f)

        # Process races to identify subraces
        # This is a simplified approach. A more robust solution might involve
        # checking for common base race names in descriptions or specific subrace fields if they existed.
        # For now, we assume a subrace might mention its parent in its name or description.
        # Example: "High Elf" is a subrace of "Elf". "Hill Dwarf" is a subrace of "Dwarf".

        races_with_subraces = []
        processed_races = {} # To keep track of base races and their subraces

        # First pass: identify potential base races (those without obvious parent race names in their own names)
        base_race_names = ["Dwarf", "Elf", "Gnome", "Halfling", "Minotaur", "Mushroomfolk", "Drow", "Derro", "Catfolk", "Gearforged", "Darakhul"]

        all_races_map = {race['name']: race for race in races_data}

        for race in races_data:
            processed_races[race['name']] = {
                'name': race['name'],
                'description': race.get('description', ''),
                'ability_score_increase': race.get('ability_score_increase', ''),
                'languages': race.get('languages', ''),
                'damage_resistance': race.get('damage_resistance', ''),
                'other_traits_html': race.get('other_traits_html', ''),
                'subraces': []
            }

        # Second pass: assign subraces to their parents
        # This logic is quite heuristic and depends on naming conventions.
        # E.g. "High Elf" contains "Elf", "Hill Dwarf" contains "Dwarf".
        # "Darakhul" and "Derro" also have "Heritage" subraces.
        # "Gearforged" have "Chassis" subraces.
        # "Mushroomfolk" has named subraces like "Acid Cap".
        # "Catfolk" has "Malkin", "Pantheran".
        # "Minotaur" has "Bhain Kwai", "Boghaid".
        # "Drow" has "Delver", "Fever-Bit", "Purified".
        # "Derro" has "Far-Touched", "Mutated", "Uncorrupted".

        # More explicit parent-subrace mapping might be needed if names are not indicative
        parent_map = {
            "High Elf": "Elf", "Wood Elf": "Elf", # Assuming Wood Elf might exist or be added
            "Hill Dwarf": "Dwarf", "Mountain Dwarf": "Dwarf", # Assuming Mountain Dwarf
            "Rock Gnome": "Gnome", "Forest Gnome": "Gnome", # Assuming Forest Gnome
            "Lightfoot": "Halfling", "Stout Halfling": "Halfling", # Assuming Stout Halfling
            "Acid Cap": "Mushroomfolk", "Favored": "Mushroomfolk", "Morel": "Mushroomfolk",
            "Malkin": "Catfolk", "Pantheran": "Catfolk",
            "Bhain Kwai": "Minotaur", "Boghaid": "Minotaur",
            "Delver": "Drow", "Fever-Bit": "Drow", "Purified": "Drow",
            "Far-Touched": "Derro", "Mutated": "Derro", "Uncorrupted": "Derro",
            # Heritage races for Darakhul
            "Derro Heritage": "Darakhul", "Dragonborn Heritage": "Darakhul", "Drow Heritage": "Darakhul",
            "Dwarf Heritage": "Darakhul", "Elf/Shadow Fey Heritage": "Darakhul", "Gnome Heritage": "Darakhul",
            "Halfling Heritage": "Darakhul", "Human/Half-Elf Heritage": "Darakhul", "Kobold Heritage": "Darakhul",
            "Ravenfolk Heritage": "Darakhul", "Tiefling Heritage": "Darakhul", "Trollkin Heritage": "Darakhul",
            # Chassis for Gearforged
            "Dwarf Chassis": "Gearforged", "Gnome Chassis": "Gearforged",
            "Human Chassis": "Gearforged", "Kobold Chassis": "Gearforged"
        }

        temp_races_list = []
        subrace_names = set(parent_map.keys())

        for race_name, race_details in processed_races.items():
            if race_name not in subrace_names:
                temp_races_list.append(race_details)

        for sub_name, parent_name in parent_map.items():
            if sub_name in processed_races and parent_name in processed_races:
                # Ensure the parent race exists in temp_races_list or add it if it's missing (e.g. base "Elf" is also selectable)
                parent_entry = next((r for r in temp_races_list if r['name'] == parent_name), None)
                if not parent_entry: # If parent itself wasn't added (e.g. "Elf" might be a subrace of something else in a complex hierarchy or just a base)
                    # This case needs careful handling. For now, assume base races are added if not subraces themselves.
                    # If "Elf" is a base race, it should already be in temp_races_list.
                    pass # Parent should already be in the list

                # Add subrace to parent
                if parent_name in processed_races: # Check if parent is a known race
                     # Find the parent in temp_races_list and add the subrace
                    for r_detail in temp_races_list:
                        if r_detail['name'] == parent_name:
                            r_detail['subraces'].append(processed_races[sub_name])
                            break
            elif sub_name in processed_races and parent_name not in processed_races:
                # This is a subrace whose defined parent is not in the main list (e.g. "Wood Elf" but no "Elf")
                # Add it as a top-level race for now.
                temp_races_list.append(processed_races[sub_name])


        # Sort alphabetically by name for consistent order
        temp_races_list.sort(key=lambda r: r['name'])
        for race_detail in temp_races_list:
            race_detail['subraces'].sort(key=lambda sr: sr['name'])

        return temp_races_list, all_races_map

    except FileNotFoundError:
        app.logger.error(f"{RACES_FILE} not found.")
        return [], {}
    except json.JSONDecodeError:
        app.logger.error(f"Error decoding {RACES_FILE}.")
        return [], {}

@app.route('/character_creation/select_race')
@login_required
def select_race():
    races_list, _ = load_races()
    if not races_list:
        # Handle case where races couldn't be loaded
        return "Error: Could not load race data. Please check server logs.", 500
    return render_template('select_race.html', races=races_list)

@app.route('/api/race_details/<race_name>')
@login_required
def api_race_details(race_name):
    _, all_races_map = load_races()
    race_detail = all_races_map.get(race_name)
    if race_detail:
        # Ensure all expected fields are present, provide defaults if not
        return jsonify({
            'name': race_detail.get('name', 'N/A'),
            'description': race_detail.get('description', 'No description available.'),
            'ability_score_increase': race_detail.get('ability_score_increase', 'N/A'),
            'languages': race_detail.get('languages', 'N/A'),
            'damage_resistance': race_detail.get('damage_resistance', 'None'),
            'other_traits_html': race_detail.get('other_traits_html', '<p>No other traits listed.</p>')
        })
    return jsonify({"error": "Race not found"}), 404

# --- End Character Creation ---


if __name__ == '__main__':
    # Set OAUTHLIB_INSECURE_TRANSPORT only if FLASK_ENV is development or app.debug is True.
    # This allows HTTP for local development but expects HTTPS in production.
    # How you set app.debug or FLASK_ENV for production (e.g. via Gunicorn/uWSGI config) is crucial.
    # For direct `python app.py` runs, `debug=True` below will enable it.
    if app.debug or os.environ.get('FLASK_ENV') == 'development':
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        app.logger.info("OAUTHLIB_INSECURE_TRANSPORT enabled for development (HTTP).")
    else:
        app.logger.info("OAUTHLIB_INSECURE_TRANSPORT is not set, HTTPS is expected for OAuth.")

    # The debug=True argument to app.run() also sets app.debug = True
    app.run(debug=True, threaded=True) # Added threaded=True for background tasks
