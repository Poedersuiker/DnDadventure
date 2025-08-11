import logging
import json
import datetime
from database import db, Character, Message, CharacterSheetHistory
import google.generativeai as genai
from flask import current_app

logger = logging.getLogger(__name__)

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

def get_recap(character_id):
    character = Character.query.get(character_id)
    if not character:
        return {'error': 'Character not found'}, 404

    messages = Message.query.filter_by(character_id=character.id).order_by(Message.timestamp.asc()).all()
    if not messages:
        return {'recap': ''}

    last_message_id = messages[-1].id
    if character.recap and character.last_recap_message_id == last_message_id:
        return {'recap': character.recap}

    history_for_prompt = []
    for msg in messages:
        if msg.role == 'user' and "You are the DM" in msg.content:
            continue
        history_for_prompt.append(f"{msg.role.capitalize()}: {msg.content}")

    history_str = "\n".join(history_for_prompt)

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

    model = genai.GenerativeModel(current_app.config.get('GEMINI_MODEL'))
    try:
        response = model.generate_content(prompt)
        recap_text = response.text.replace('\\n', '<br>')
    except Exception as e:
        logger.error(f"Error generating recap for character {character_id}: {e}")
        return {'error': 'Failed to generate recap'}, 500

    character.recap = recap_text
    character.last_recap_message_id = last_message_id
    db.session.commit()

    return {'recap': recap_text}
