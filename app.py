from gevent import monkey
monkey.patch_all()

import logging
import time
import re
import json
import datetime
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_socketio import SocketIO, emit
from threading import Thread
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import auth
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, init_db, User, Character, TTRPGType, GeminiPrepMessage, Message, CharacterSheetHistory
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MalformedAppDataError(Exception):
    pass

def update_character_sheet(character_id, sheet_data):
    character = Character.query.get(character_id)
    if character:
        character.charactersheet = json.dumps(sheet_data)
        history_record = CharacterSheetHistory(
            character_id=character_id,
            sheet_data=json.dumps(sheet_data)
        )
        db.session.add(history_record)
        db.session.commit()
        logger.info(f"Character sheet updated for character {character_id}")
    else:
        logger.error(f"Character not found when trying to update sheet: {character_id}")

def process_bot_response(bot_response, character_id=None):
    charactersheet_pattern = re.compile(r'\[CHARACTERSHEET\](.*?)\[/CHARACTERSHEET\]', re.DOTALL)
    match_cs = charactersheet_pattern.search(bot_response)
    if match_cs and character_id:
        cs_json_str = match_cs.group(1)
        try:
            cs_data = json.loads(cs_json_str)
            update_character_sheet(character_id, cs_data)
            bot_response = charactersheet_pattern.sub('', bot_response).strip()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse CHARACTERSHEET json: {e}")

    if bot_response.count('[APPDATA]') != bot_response.count('[/APPDATA]'):
        raise MalformedAppDataError("Mismatched number of [APPDATA] and [/APPDATA] tags.")

    appdata_pattern = re.compile(r'\[APPDATA\](.*?)\[/APPDATA\]', re.DOTALL)
    match = appdata_pattern.search(bot_response)

    if not match:
        return bot_response.replace('\n', '<br>')

    appdata_json_str = match.group(1)
    processed_text = appdata_pattern.sub('', bot_response).strip().replace('\n', '<br>')

    try:
        appdata = json.loads(appdata_json_str)
        if 'SingleChoice' in appdata:
            choice_data = appdata['SingleChoice']
            title = choice_data.get('Title', 'Choose an option')
            options = choice_data.get('Options', {})

            html_choices = f'<div class="singlechoice-container"><h3>{title}</h3>'
            for key, details in options.items():
                html_choices += f"""
                    <div class="singlechoice-option">
                        <div class="singlechoice-option-inner">
                            <button onclick="sendChoice('{details['Name']}')">{details['Name']}</button>
                        </div>
                        <span class="description">{details['Description']}</span>
                    </div>
                """
            html_choices += '</div>'

            return processed_text + html_choices

        if 'OrderedList' in appdata:
            list_data = appdata['OrderedList']
            title = list_data.get('Title', 'Ordered List')
            items = list_data.get('Items', [])
            values = list_data.get('Values', [])

            html_list = f'<div class="ordered-list-container"><h3>{title}</h3><ul id="sortable-list">'
            for i, item in enumerate(items):
                value = values[i] if i < len(values) else ''
                # Add classes to first and last items to control arrow visibility
                li_class = "sortable-item"
                if i == 0:
                    li_class += " first-item"
                if i == len(items) - 1:
                    li_class += " last-item"

                html_list += f'<li class="{li_class}" data-name="{item["Name"]}">{item["Name"]}<div class="value-card" draggable="true" ondragstart="drag(event)" id="val-{i}"><span class="value">{value}</span><span class="arrows"><span class="up-arrow" onclick="moveValueUp(this)">&#8593;</span><span class="down-arrow" onclick="moveValueDown(this)">&#8595;</span></span><span class="drag-handle">&#9776;</span></div></li>'
            html_list += '</ul><button onclick="confirmOrderedList()">Confirm</button></div>'

            return processed_text + html_list

        if 'MultiSelect' in appdata:
            multiselect_data = appdata['MultiSelect']
            title = multiselect_data.get('Title', 'Choose an option')
            max_choices = multiselect_data.get('MaxChoices', 1)
            options = multiselect_data.get('Options', {})

            html_choices = f'<div class="multiselect-container" data-max-choices="{max_choices}"><h3>{title}</h3>'
            for key, details in options.items():
                html_choices += f"""
                    <div class="multiselect-option">
                        <div class="multiselect-option-inner">
                            <input type="checkbox" id="{key}" name="{details['Name']}" value="{details['Name']}">
                            <label for="{key}">{details['Name']}</label>
                        </div>
                        <span class="description">{details['Description']}</span>
                    </div>
                """
            html_choices += '<button onclick="confirmMultiSelect(this)">Confirm</button></div>'

            return processed_text + html_choices

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse APPDATA json: {e}")
        raise MalformedAppDataError(f"Failed to parse APPDATA json: {e}")

    return processed_text

app = Flask(__name__, instance_relative_config=True)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config.from_mapping(
    SECRET_KEY='your-very-secret-key! barbarandomkeybarchar',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    GEMINI_MODEL='gemini-1.5-pro-latest',
    GEMINI_DEBUG=False
)
app.config.from_pyfile('config.py', silent=True)

# Gemini API Key
gemini_api_key = app.config.get('GEMINI_API_KEY')
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

# Database setup
db_type = app.config.get("DB_TYPE", "sqlite")
if db_type == "sqlite":
    db_path = app.config.get("DB_PATH", "database.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, db_path)
elif db_type in ["mysql", "postgresql"]:
    db_user = app.config.get("DB_USER")
    db_password = app.config.get("DB_PASSWORD")
    db_host = app.config.get("DB_HOST")
    db_port = app.config.get("DB_PORT")
    db_name = app.config.get("DB_NAME")
    if db_type == "mysql":
        app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else: # postgresql
        app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

init_db(app)

socketio = SocketIO(app, async_mode='gevent')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

auth.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    admin_email = app.config.get('ADMIN_EMAIL')
    characters = Character.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', admin_email=admin_email, characters=characters)

@app.route('/login')
def login():
    return auth.login()

@app.route('/authorize')
def authorize():
    user_info = auth.authorize()
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(google_id=google_id, email=email, name=name)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/new_character', methods=['GET', 'POST'])
@login_required
def new_character():
    if request.method == 'POST':
        character_name = request.form.get('character_name')
        ttrpg_type_id = request.form.get('ttrpg_type')
        ttrpg_type = TTRPGType.query.get(ttrpg_type_id)
        new_char = Character(
            user_id=current_user.id,
            ttrpg_type_id=ttrpg_type_id,
            character_name=character_name,
            charactersheet=ttrpg_type.json_template
        )
        db.session.add(new_char)
        db.session.commit()
        return redirect(url_for('index', new_char_id=new_char.id))
    ttrpg_types = TTRPGType.query.all()
    return render_template('new_character.html', ttrpg_types=ttrpg_types)

@app.route('/delete_character/<int:character_id>', methods=['DELETE'])
@login_required
def delete_character(character_id):
    character = Character.query.get(character_id)
    if character and character.user_id == current_user.id:
        db.session.delete(character)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Character not found or unauthorized'}), 404

@app.route('/recap/<int:character_id>')
@login_required
def get_recap(character_id):
    character = Character.query.get(character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    messages = Message.query.filter_by(character_id=character.id).order_by(Message.timestamp.asc()).all()
    if not messages:
        return jsonify({'recap': ''})

    last_message_id = messages[-1].id
    if character.recap and character.last_recap_message_id == last_message_id:
        return jsonify({'recap': character.recap})

    history_for_prompt = []
    for msg in messages:
        # Exclude the initial system prompt from the recap context
        if msg.role == 'user' and "You are the DM" in msg.content:
            continue
        history_for_prompt.append(f"{msg.role.capitalize()}: {msg.content}")

    history_str = "\n".join(history_for_prompt)

    # Define sessions
    sessions = []
    if messages:
        current_session = [messages[0]]
        for i in range(1, len(messages)):
            time_diff = messages[i].timestamp - messages[i-1].timestamp
            if time_diff > datetime.timedelta(hours=1):
                sessions.append(current_session)
                current_session = [messages[i]]
            else:
                current_session.append(messages[i])
        sessions.append(current_session)

    # Create the prompt for Gemini
    prompt = f"""
Please provide a recap of the following adventure based on the message history. The user wants a two-part summary:
1. A general overview of the entire adventure so far (one paragraph).
2. A more detailed summary of the last two sessions. A 'session' is a period of continuous play.

Here is the full message history:
---
{history_str}
---

Based on this, please generate the recap.
"""

    model = genai.GenerativeModel(app.config.get('GEMINI_MODEL'))
    try:
        response = model.generate_content(prompt)
        recap_text = response.text.replace('\n', '<br>')
    except Exception as e:
        logger.error(f"Error generating recap for character {character_id}: {e}")
        return jsonify({'error': 'Failed to generate recap'}), 500


    # Store the recap
    character.recap = recap_text
    character.last_recap_message_id = last_message_id
    db.session.commit()

    return jsonify({'recap': recap_text})

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    """Admin page to select the Gemini model."""
    if current_user.email != app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    if request.method == 'POST':
        if request.form.get('form_type') == 'add_ttrpg':
            ttrpg_name = request.form.get('ttrpg_name')
            json_template = request.form.get('json_template')
            html_template = request.form.get('html_template')
            wiki_link = request.form.get('wiki_link')
            new_ttrpg_type = TTRPGType(
                name=ttrpg_name,
                json_template=json_template,
                html_template=html_template,
                wiki_link=wiki_link
            )
            db.session.add(new_ttrpg_type)
            db.session.commit()
        else:
            config_path = os.path.join(app.instance_path, 'config.py')

            new_model = request.form.get('model')
            new_debug_status = 'gemini_debug' in request.form

            config_lines = []
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_lines = f.readlines()

            updated_keys = {'GEMINI_MODEL', 'GEMINI_DEBUG'}
            new_config_lines = []
            keys_found = set()

            for line in config_lines:
                stripped_line = line.strip()
                key_found_on_line = False
                if not stripped_line or stripped_line.startswith('#'):
                    new_config_lines.append(line)
                    continue

                for key in updated_keys:
                    if stripped_line.startswith(key + ' '):
                        if key == 'GEMINI_MODEL':
                            new_config_lines.append(f"GEMINI_MODEL = '{new_model}'\n")
                        elif key == 'GEMINI_DEBUG':
                            new_config_lines.append(f"GEMINI_DEBUG = {new_debug_status}\n")
                        keys_found.add(key)
                        key_found_on_line = True
                        break
                if not key_found_on_line:
                    new_config_lines.append(line)

            if 'GEMINI_MODEL' not in keys_found:
                new_config_lines.append(f"GEMINI_MODEL = '{new_model}'\n")
            if 'GEMINI_DEBUG' not in keys_found:
                new_config_lines.append(f"GEMINI_DEBUG = {new_debug_status}\n")

            with open(config_path, 'w') as f:
                f.writelines(new_config_lines)

            app.config.from_pyfile('config.py', silent=True)

        return redirect(url_for('admin'))

    models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    ttrpg_types = TTRPGType.query.all()
    gemini_model = app.config.get('GEMINI_MODEL')
    gemini_debug = app.config.get('GEMINI_DEBUG', False)
    return render_template('admin.html', models=models, selected_model=gemini_model, gemini_debug=gemini_debug, ttrpg_types=ttrpg_types)

@app.route('/admin/ttrpg_data', methods=['GET', 'POST', 'DELETE', 'PUT'])
@login_required
def ttrpg_data():
    if current_user.email != app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    if request.method == 'GET':
        ttrpg_types = TTRPGType.query.all()
        return jsonify([
            {
                'id': t.id,
                'name': t.name,
                'json_template': t.json_template,
                'html_template': t.html_template,
                'wiki_link': t.wiki_link
            } for t in ttrpg_types
        ])

    if request.method == 'POST':
        data = request.get_json()
        ttrpg_type = TTRPGType.query.get(data['id'])
        if ttrpg_type:
            ttrpg_type.name = data['name']
            ttrpg_type.json_template = data['json_template']
            ttrpg_type.html_template = data['html_template']
            ttrpg_type.wiki_link = data['wiki_link']
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'TTRPG type not found'})

    if request.method == 'PUT':
        data = request.get_json()
        new_ttrpg_type = TTRPGType(
            name=data['name'],
            json_template=data['json_template'],
            html_template=data['html_template'],
            wiki_link=data['wiki_link']
        )
        db.session.add(new_ttrpg_type)
        db.session.commit()
        return jsonify({'success': True})

    if request.method == 'DELETE':
        data = request.get_json()
        ttrpg_type = TTRPGType.query.get(data['id'])
        if ttrpg_type:
            db.session.delete(ttrpg_type)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'TTRPG type not found'})

@app.route('/admin/gemini_prep_data', methods=['GET', 'POST', 'DELETE', 'PUT'])
@login_required
def gemini_prep_data():
    if current_user.email != app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    if request.method == 'GET':
        messages = GeminiPrepMessage.query.order_by(GeminiPrepMessage.priority).all()
        return jsonify([
            {
                'id': m.id,
                'message': m.message,
                'priority': m.priority
            } for m in messages
        ])

    if request.method == 'POST':
        data = request.get_json()
        message = GeminiPrepMessage.query.get(data['id'])
        if message:
            message.message = data['message']
            message.priority = data['priority']
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Message not found'})

    if request.method == 'PUT':
        data = request.get_json()
        new_message = GeminiPrepMessage(
            message=data['message'],
            priority=data['priority']
        )
        db.session.add(new_message)
        db.session.commit()
        return jsonify({'success': True})

    if request.method == 'DELETE':
        data = request.get_json()
        message = GeminiPrepMessage.query.get(data['id'])
        if message:
            db.session.delete(message)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Message not found'})

def send_to_gemini_with_retry(model, history, character_id, max_retries=3):
    if app.config.get('GEMINI_DEBUG'):
        socketio.emit('debug_message', {'type': 'request', 'data': json.dumps(history, indent=2), 'character_id': character_id})

    bot_response_text = None
    for attempt in range(max_retries):
        try:
            response = model.generate_content(history)

            if not response or not (hasattr(response, 'parts') and response.parts or hasattr(response, 'text')):
                logger.warning(f"Empty response from Gemini on attempt {attempt + 1}")
                if attempt + 1 == max_retries:
                    return "Sorry, I received an empty or invalid response from the AI.", None
                continue

            if hasattr(response, 'parts') and response.parts:
                bot_response_text = "".join(part.text for part in response.parts)
            else:
                bot_response_text = response.text

            if app.config.get('GEMINI_DEBUG'):
                socketio.emit('debug_message', {'type': 'response', 'data': bot_response_text, 'character_id': character_id})

            logger.info(f"Gemini response (attempt {attempt+1}): {bot_response_text}")
            processed_response = process_bot_response(bot_response_text, character_id)
            return processed_response, bot_response_text

        except MalformedAppDataError as e:
            logger.warning(f"Malformed APPDATA from Gemini (attempt {attempt+1}): {e}. Retrying...")
            if bot_response_text:
                history.append({'role': 'model', 'parts': [bot_response_text]})
            history.append({'role': 'user', 'parts': ["The response you just sent contained a malformed [APPDATA] block. Please correct the formatting of the JSON data and resend your message."]})

            if attempt + 1 == max_retries:
                logger.error(f"Failed to get valid response from Gemini after {max_retries} attempts.")
                return "Sorry, I'm having trouble generating a valid response right now. Please try again later.", None

        except Exception as e:
            logger.error(f"Error calling Gemini API on attempt {attempt + 1}: {e}")
            if attempt + 1 == max_retries:
                return "Error: Could not connect to the bot.", None
            time.sleep(1)

    return "An unexpected error occurred.", None

@socketio.on('connect')
def handle_connect():
    """Handles a new client connection."""
    if not current_user.is_authenticated:
        return False
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """Handles a client disconnection."""
    logger.info('Client disconnected')

@socketio.on('edit_ttrpg')
def handle_edit_ttrpg(data):
    """Handles a request to edit a TTRPG type."""
    ttrpg_id = data['id']
    ttrpg_type = TTRPGType.query.get(ttrpg_id)
    if ttrpg_type:
        emit('ttrpg_data', {'html': ttrpg_type.html_template})

@socketio.on('initiate_chat')
def handle_initiate_chat(data):
    character_id = str(data['character_id'])
    character = Character.query.get(character_id)
    if not character or character.user_id != current_user.id:
        return

    messages = Message.query.filter_by(character_id=character.id).order_by(Message.timestamp).all()

    if messages:
        # Existing character with history.
        # Do nothing here. The client will fetch the recap.
        pass
    else:
        # New character
        prep_messages = GeminiPrepMessage.query.order_by(GeminiPrepMessage.priority).all()
        ttrpg_name = character.ttrpg_type.name
        char_name = character.character_name

        system_instructions = []
        initial_user_prompt = ""

        ttrpg_json = character.ttrpg_type.json_template
        for prep_msg in prep_messages:
            msg = prep_msg.message.replace('[DB.TTRPG.Name]', ttrpg_name).replace('[DB.CHARACTER.NAME]', char_name).replace('[DB.TTRPG.JSON]', ttrpg_json)
            # Priority 2 is the initial user-facing prompt
            if prep_msg.priority == 2:
                initial_user_prompt = msg
            else:
                system_instructions.append(msg)

        # Save the combined system instructions and initial prompt as the first user message
        # This preserves the full context for the model in a single, initial user turn
        full_initial_prompt = "\n".join(system_instructions) + "\n" + initial_user_prompt

        user_message = Message(character_id=character.id, role='user', content=full_initial_prompt)
        db.session.add(user_message)
        db.session.commit()

        history = [{'role': 'user', 'parts': [full_initial_prompt]}]
        model = genai.GenerativeModel(app.config.get('GEMINI_MODEL'))

        processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

        if bot_response_text:
            model_message = Message(character_id=character.id, role='model', content=bot_response_text)
            db.session.add(model_message)
            db.session.commit()

            # We only want to display the bot's response, not the entire initial prompt
            emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})


@socketio.on('get_character_sheet')
def handle_get_character_sheet(data):
    character_id = data.get('character_id')
    character = Character.query.get(character_id)

    if character and character.user_id == current_user.id:
        try:
            sheet_data = json.loads(character.charactersheet)
            html_template = character.ttrpg_type.html_template

            emit('character_sheet_data', {
                'sheet_data': sheet_data,
                'html_template': html_template,
                'character_id': character_id
            })
        except json.JSONDecodeError:
            logger.error(f"Could not decode character sheet JSON for character {character_id}")
            # Optionally, emit an error to the client
            emit('character_sheet_error', {'character_id': character_id, 'message': 'Could not load character sheet data.'})


@socketio.on('get_character_sheet_history')
def handle_get_character_sheet_history(data):
    character_id = data.get('character_id')
    character = Character.query.get(character_id)

    if character and character.user_id == current_user.id:
        history_records = CharacterSheetHistory.query.filter_by(character_id=character_id).order_by(CharacterSheetHistory.timestamp.desc()).all()

        history_data = []
        for record in history_records:
            try:
                history_data.append({
                    'sheet_data': json.loads(record.sheet_data),
                    'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M:%S') + ' UTC'
                })
            except json.JSONDecodeError:
                logger.error(f"Could not decode character sheet history JSON for character {character_id}, record {record.id}")

        emit('character_sheet_history_data', {
            'history': history_data,
            'character_id': character_id
        })


@socketio.on('get_message_history')
@login_required
def get_message_history(data):
    character_id = data.get('character_id')
    character = Character.query.get(character_id)
    if character and character.user_id == current_user.id:
        messages = Message.query.filter_by(character_id=character.id).order_by(Message.timestamp.asc()).all()
        history_data = []
        for msg in messages:
            if msg.role == 'user' and "You are the DM" in msg.content:
                continue

            try:
                content = process_bot_response(msg.content)
            except MalformedAppDataError:
                logger.warning(f"Malformed APPDATA in history for message {msg.id}. Displaying raw content.")
                content = msg.content.replace('\n', '<br>')

            history_data.append({
                'role': msg.role,
                'content': content
            })
        emit('message_history_data', {'history': history_data, 'character_id': character_id})


@socketio.on('user_ordered_list')
def handle_user_ordered_list(data):
    """Handles a user's ordered list submission from a structured data interaction."""
    ordered_list = data['ordered_list']
    character_id = str(data['character_id'])
    logger.info(f"Received ordered list: {ordered_list} for character: {character_id}")

    if not app.config.get('GEMINI_API_KEY'):
        logger.error("Gemini API key is not configured.")
        emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
        return

    user_message_text = "I have assigned the scores as follows:\n"
    for item in ordered_list:
        user_message_text += f"{item['name']}: {item['value']}\n"

    # Save user message
    user_message = Message(character_id=character_id, role='user', content=user_message_text)
    db.session.add(user_message)
    db.session.commit()

    # Load history
    messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
    history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

    model = genai.GenerativeModel(app.config.get('GEMINI_MODEL'))
    processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

    if bot_response_text:
        # Save model response
        model_message = Message(character_id=character_id, role='model', content=bot_response_text)
        db.session.add(model_message)
        db.session.commit()

    emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

@socketio.on('message')
def handle_message(data):
    """Handles a message from a client."""
    message_text = data['message']
    character_id = str(data['character_id'])
    logger.info(f"Received message: {message_text} for character: {character_id}")

    if not app.config.get('GEMINI_API_KEY'):
        logger.error("Gemini API key is not configured.")
        emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
        return

    # Save user message
    user_message = Message(character_id=character_id, role='user', content=message_text)
    db.session.add(user_message)
    db.session.commit()

    # Load history
    messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
    history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

    model = genai.GenerativeModel(app.config.get('GEMINI_MODEL'))
    processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

    if bot_response_text:
        # Save model response
        model_message = Message(character_id=character_id, role='model', content=bot_response_text)
        db.session.add(model_message)
        db.session.commit()

    emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

@socketio.on('user_choice')
def handle_user_choice(data):
    """Handles a user's choice from a structured data interaction."""
    choice = data['choice']
    character_id = str(data['character_id'])
    logger.info(f"Received choice: {choice} for character: {character_id}")

    if not app.config.get('GEMINI_API_KEY'):
        logger.error("Gemini API key is not configured.")
        emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
        return

    user_message_text = f"I choose: {choice}"

    # Save user message
    user_message = Message(character_id=character_id, role='user', content=user_message_text)
    db.session.add(user_message)
    db.session.commit()

    # Load history
    messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
    history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

    model = genai.GenerativeModel(app.config.get('GEMINI_MODEL'))
    processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

    if bot_response_text:
        # Save model response
        model_message = Message(character_id=character_id, role='model', content=bot_response_text)
        db.session.add(model_message)
        db.session.commit()

    emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

if __name__ == '__main__':
    socketio.run(app, debug=True)

@socketio.on('user_multi_choice')
def handle_user_multi_choice(data):
    """Handles a user's multi-choice submission from a structured data interaction."""
    choices = data['choices']
    character_id = str(data['character_id'])
    logger.info(f"Received choices: {choices} for character: {character_id}")

    if not app.config.get('GEMINI_API_KEY'):
        logger.error("Gemini API key is not configured.")
        emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
        return

    user_message_text = f"I choose the following: {', '.join(choices)}"

    # Save user message
    user_message = Message(character_id=character_id, role='user', content=user_message_text)
    db.session.add(user_message)
    db.session.commit()

    # Load history
    messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
    history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

    model = genai.GenerativeModel(app.config.get('GEMINI_MODEL'))
    processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

    if bot_response_text:
        # Save model response
        model_message = Message(character_id=character_id, role='model', content=bot_response_text)
        db.session.add(model_message)
        db.session.commit()

    emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})