import logging
import json
from flask import request
from flask_login import current_user
from flask_socketio import emit
from app import socketio
from database import db, User, Character, TTRPGType, GeminiPrepMessage, Message, CharacterSheetHistory
import google.generativeai as genai
import dice_roller
from bot.gemini_utils import process_bot_response, send_to_gemini_with_retry, MalformedAppDataError

logger = logging.getLogger(__name__)

def register_socketio_handlers(socketio):
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
            pass
        else:
            prep_messages = GeminiPrepMessage.query.order_by(GeminiPrepMessage.priority).all()
            ttrpg_name = character.ttrpg_type.name
            char_name = character.character_name

            system_instructions = []
            initial_user_prompt = ""

            ttrpg_json = character.ttrpg_type.json_template
            for prep_msg in prep_messages:
                msg = prep_msg.message.replace('[DB.TTRPG.Name]', ttrpg_name).replace('[DB.CHARACTER.NAME]', char_name).replace('[DB.TTRPG.JSON]', ttrpg_json)
                if prep_msg.priority == 2:
                    initial_user_prompt = msg
                else:
                    system_instructions.append(msg)

            full_initial_prompt = "\\n".join(system_instructions) + "\\n" + initial_user_prompt

            user_message = Message(character_id=character.id, role='user', content=full_initial_prompt)
            db.session.add(user_message)
            db.session.commit()

            history = [{'role': 'user', 'parts': [full_initial_prompt]}]
            model = genai.GenerativeModel(socketio.app.config.get('GEMINI_MODEL'))

            processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

            if bot_response_text:
                model_message = Message(character_id=character.id, role='model', content=bot_response_text)
                db.session.add(model_message)
                db.session.commit()

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
                    content = msg.content.replace('\\n', '<br>')

                history_data.append({
                    'role': msg.role,
                    'content': content
                })
            emit('message_history_data', {'history': history_data, 'character_id': character_id})

    @socketio.on('user_ordered_list')
    def handle_user_ordered_list(data):
        ordered_list = data['ordered_list']
        character_id = str(data['character_id'])
        logger.info(f"Received ordered list: {ordered_list} for character: {character_id}")

        if not socketio.app.config.get('GEMINI_API_KEY'):
            logger.error("Gemini API key is not configured.")
            emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
            return

        user_message_text = "I have assigned the scores as follows:\\n"
        for item in ordered_list:
            user_message_text += f"{item['name']}: {item['value']}\\n"

        user_message = Message(character_id=character_id, role='user', content=user_message_text)
        db.session.add(user_message)
        db.session.commit()

        messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
        history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

        model = genai.GenerativeModel(socketio.app.config.get('GEMINI_MODEL'))
        processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

        if bot_response_text:
            model_message = Message(character_id=character_id, role='model', content=bot_response_text)
            db.session.add(model_message)
            db.session.commit()

        emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

    @socketio.on('dice_roll')
    def handle_dice_roll(data):
        character_id = str(data['character_id'])
        roll_params = data['roll_params']
        logger.info(f"Received dice roll request: {roll_params} for character: {character_id}")

        if not socketio.app.config.get('GEMINI_API_KEY'):
            logger.error("Gemini API key is not configured.")
            emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
            return

        try:
            results = dice_roller.roll(
                mechanic=roll_params.get('Mechanic'),
                dice=roll_params.get('Dice'),
                num_rolls=roll_params.get('NumRolls', 1),
                advantage=roll_params.get('Advantage', False),
                disadvantage=roll_params.get('Disadvantage', False)
            )

            emit('dice_roll_result', {'results': results, 'character_id': character_id})

            summary_parts = []
            for result in results:
                total = result['total']
                rolls = result['rolls']
                dropped = result.get('dropped')
                part = f"Total: {total}, Rolls: {rolls}"
                if dropped:
                    part += f", Dropped: {dropped}"
                summary_parts.append(f"({part})")
            user_message_text = f"I rolled for {roll_params.get('Title', 'dice')}: {', '.join(summary_parts)}"

            user_message = Message(character_id=character_id, role='user', content=user_message_text)
            db.session.add(user_message)
            db.session.commit()

            messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
            history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

            model = genai.GenerativeModel(socketio.app.config.get('GEMINI_MODEL'))
            processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

            if bot_response_text:
                model_message = Message(character_id=character_id, role='model', content=bot_response_text)
                db.session.add(model_message)
                db.session.commit()

            emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

        except (ValueError, TypeError) as e:
            logger.error(f"Error processing dice roll: {e}")
            emit('message', {'text': f"Error: {e}", 'sender': 'received', 'character_id': character_id})

    @socketio.on('message')
    def handle_message(data):
        message_text = data['message']
        character_id = str(data['character_id'])
        logger.info(f"Received message: {message_text} for character: {character_id}")

        if not socketio.app.config.get('GEMINI_API_KEY'):
            logger.error("Gemini API key is not configured.")
            emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
            return

        user_message = Message(character_id=character_id, role='user', content=message_text)
        db.session.add(user_message)
        db.session.commit()

        messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
        history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

        model = genai.GenerativeModel(socketio.app.config.get('GEMINI_MODEL'))
        processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

        if bot_response_text:
            model_message = Message(character_id=character_id, role='model', content=bot_response_text)
            db.session.add(model_message)
            db.session.commit()

        emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

    @socketio.on('user_choice')
    def handle_user_choice(data):
        choice = data['choice']
        character_id = str(data['character_id'])
        logger.info(f"Received choice: {choice} for character: {character_id}")

        if not socketio.app.config.get('GEMINI_API_KEY'):
            logger.error("Gemini API key is not configured.")
            emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
            return

        user_message_text = f"I choose: {choice}"

        user_message = Message(character_id=character_id, role='user', content=user_message_text)
        db.session.add(user_message)
        db.session.commit()

        messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
        history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

        model = genai.GenerativeModel(socketio.app.config.get('GEMINI_MODEL'))
        processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

        if bot_response_text:
            model_message = Message(character_id=character_id, role='model', content=bot_response_text)
            db.session.add(model_message)
            db.session.commit()

        emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})

    @socketio.on('user_multi_choice')
    def handle_user_multi_choice(data):
        """Handles a user's multi-choice submission from a structured data interaction."""
        choices = data['choices']
        character_id = str(data['character_id'])
        logger.info(f"Received choices: {choices} for character: {character_id}")

        if not socketio.app.config.get('GEMINI_API_KEY'):
            logger.error("Gemini API key is not configured.")
            emit('message', {'text': "Error: Gemini API key not configured", 'sender': 'received', 'character_id': character_id})
            return

        user_message_text = f"I choose the following: {', '.join(choices)}"

        user_message = Message(character_id=character_id, role='user', content=user_message_text)
        db.session.add(user_message)
        db.session.commit()

        messages = Message.query.filter_by(character_id=character_id).order_by(Message.timestamp).all()
        history = [{'role': msg.role, 'parts': [msg.content]} for msg in messages]

        model = genai.GenerativeModel(socketio.app.config.get('GEMINI_MODEL'))
        processed_response, bot_response_text = send_to_gemini_with_retry(model, history, character_id)

        if bot_response_text:
            model_message = Message(character_id=character_id, role='model', content=bot_response_text)
            db.session.add(model_message)
            db.session.commit()

        emit('message', {'text': processed_response, 'sender': 'received', 'character_id': character_id})
