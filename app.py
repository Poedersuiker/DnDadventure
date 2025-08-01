from gevent import monkey
monkey.patch_all()

import logging
import time
import re
import json
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_socketio import SocketIO, emit
from threading import Thread
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import auth
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, init_db, User, Character, TTRPGType, GeminiPrepMessage
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_bot_response(bot_response):
    appdata_pattern = re.compile(r'\[APPDATA\](.*?)\[/APPDATA\]', re.DOTALL)
    match = appdata_pattern.search(bot_response)

    if not match:
        return bot_response

    appdata_json_str = match.group(1)
    processed_text = appdata_pattern.sub('', bot_response).strip()

    try:
        appdata = json.loads(appdata_json_str)
        if 'SingleChoice' in appdata:
            choice_data = appdata['SingleChoice']
            title = next(iter(choice_data))
            options = choice_data[title]

            html_choices = f'<div class="choice-container"><h3>{title}</h3>'
            for key, details in options.items():
                html_choices += f"""
                    <div class="choice-option">
                        <button onclick="sendChoice('{details['Name']}')">{details['Name']}</button>
                        <p>{details['Description']}</p>
                    </div>
                """
            html_choices += '</div>'

            return processed_text + html_choices

    except (json.JSONDecodeError, StopIteration) as e:
        logger.error(f"Failed to parse APPDATA json: {e}")
        return processed_text

    return processed_text

app = Flask(__name__, instance_relative_config=True)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config.from_mapping(
    SECRET_KEY='your-very-secret-key! barbarandomkeybarchar',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
app.config.from_pyfile('config.py', silent=True)

# Global variable to store the selected model
selected_model = 'gemini-1.5-pro-latest'

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

conversations = {}

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
        return redirect(url_for('index'))
    ttrpg_types = TTRPGType.query.all()
    return render_template('new_character.html', ttrpg_types=ttrpg_types)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    """Admin page to select the Gemini model."""
    if current_user.email != app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    global selected_model
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
            selected_model = request.form.get('model')
        return redirect(url_for('admin'))

    models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    ttrpg_types = TTRPGType.query.all()
    return render_template('admin.html', models=models, selected_model=selected_model, ttrpg_types=ttrpg_types)

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
    character_id = data['character_id']
    character = Character.query.get(character_id)
    if not character or character.user_id != current_user.id:
        return

    global conversations

    prep_messages = GeminiPrepMessage.query.order_by(GeminiPrepMessage.priority).all()
    ttrpg_name = character.ttrpg_type.name
    char_name = character.character_name

    initial_prompt_parts = []
    for prep_msg in prep_messages:
        msg = prep_msg.message
        msg = msg.replace('<fill selected TTRPG name>', ttrpg_name)
        msg = msg.replace('<fill selected character name>', char_name)
        initial_prompt_parts.append(msg)

    initial_prompt = "\n".join(initial_prompt_parts)

    history = [{'role': 'user', 'parts': [initial_prompt]}]

    try:
        model = genai.GenerativeModel(selected_model)
        response = model.generate_content(history)

        if response and response.parts:
            bot_response = "".join(part.text for part in response.parts)
            logger.info('Gemini initial response: ' + bot_response)
            processed_response = process_bot_response(bot_response)
            history.append({'role': 'model', 'parts': [bot_response]})
            conversations[character_id] = history
            emit('message', {'text': processed_response, 'sender': 'other', 'character_id': character_id})
        else:
            logger.warning("Unexpected response format from Gemini: " + str(response))
            emit('message', {'text': "Sorry, I couldn't process that.", 'sender': 'other', 'character_id': character_id})

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        emit('message', {'text': f"Error: Could not connect to the bot.", 'sender': 'other', 'character_id': character_id})

@socketio.on('message')
def handle_message(data):
    """Handles a message from a client."""
    message = data['message']
    character_id = data['character_id']
    logger.info(f"Received message: {message} for character: {character_id}")

    if not gemini_api_key:
        logger.error("Gemini API key is not configured.")
        emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'other'})
        return

    global conversations
    if character_id not in conversations:
        emit('message', {'text': "Chat not initiated.", 'sender': 'other', 'character_id': character_id})
        return

    history = conversations[character_id]
    history.append({'role': 'user', 'parts': [message]})

    try:
        model = genai.GenerativeModel(selected_model)
        response = model.generate_content(history)

        if response and response.parts:
            bot_response = "".join(part.text for part in response.parts)
            logger.info('Gemini response: ' + bot_response)
            processed_response = process_bot_response(bot_response)
            history.append({'role': 'model', 'parts': [bot_response]})
            conversations[character_id] = history
            emit('message', {'text': processed_response, 'sender': 'other', 'character_id': character_id})
        else:
            # Fallback for unexpected response format
            logger.warning("Unexpected response format from Gemini: " + str(response))
            emit('message', {'text': "Sorry, I couldn't process that.", 'sender': 'other', 'character_id': character_id})

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        emit('message', {'text': f"Error: Could not connect to the bot.", 'sender': 'other', 'character_id': character_id})

@socketio.on('user_choice')
def handle_user_choice(data):
    """Handles a user's choice from a structured data interaction."""
    choice = data['choice']
    character_id = data['character_id']
    logger.info(f"Received choice: {choice} for character: {character_id}")

    if not gemini_api_key:
        logger.error("Gemini API key is not configured.")
        emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'other', 'character_id': character_id})
        return

    global conversations
    if character_id not in conversations:
        emit('message', {'text': "Chat not initiated.", 'sender': 'other', 'character_id': character_id})
        return

    history = conversations[character_id]
    user_message = f"I choose: {choice}"
    history.append({'role': 'user', 'parts': [user_message]})

    try:
        model = genai.GenerativeModel(selected_model)
        response = model.generate_content(history)

        if response and response.parts:
            bot_response = "".join(part.text for part in response.parts)
            logger.info('Gemini response after choice: ' + bot_response)
            processed_response = process_bot_response(bot_response)
            history.append({'role': 'model', 'parts': [bot_response]})
            conversations[character_id] = history
            emit('message', {'text': processed_response, 'sender': 'other', 'character_id': character_id})
        else:
            logger.warning("Unexpected response format from Gemini: " + str(response))
            emit('message', {'text': "Sorry, I couldn't process that.", 'sender': 'other', 'character_id': character_id})

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        emit('message', {'text': f"Error: Could not connect to the bot.", 'sender': 'other', 'character_id': character_id})

if __name__ == '__main__':
    socketio.run(app, debug=True)