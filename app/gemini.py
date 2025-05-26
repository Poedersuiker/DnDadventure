import json
import google.generativeai as genai
from flask import current_app # jsonify will be handled by the route
from flask_babel import _
from app import db
from app.models import Character, Setting # Setting is used by geminiai

# current_user is not directly available here.
# The calling route will pass current_user.id as current_user_id.

def geminiai(character_id, user_message, current_user_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user_id:
        # Return dict and status code, to be jsonified by the caller
        return {"error": _("Unauthorized. This character does not belong to you.")}, 403

    if not user_message:
        return {"error": _("No message provided.")}, 400

    try:
        log_entries = json.loads(character.adventure_log or '[]')
        if not isinstance(log_entries, list):
            log_entries = []
    except json.JSONDecodeError:
        log_entries = []
        current_app.logger.warning(f"Adventure log for character {character_id} was malformed and has been reset.")

    # API Key Configuration
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        current_app.logger.error("Gemini API key (GEMINI_API_KEY) not configured.")
        return {"error": _("The Dungeon Master's connection to the ethereal plane is disrupted. (API key missing). Please try again later.")}, 500
    
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        current_app.logger.error(f"Error configuring Gemini API: {str(e)}")
        return {"error": _("There was an issue configuring the connection to the ethereal plane. Please try again later.")}, 500

    # Initialize Model
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    
    db_setting = Setting.query.filter_by(key='DEFAULT_GEMINI_MODEL').first()
    model_to_use = ""
    if db_setting and db_setting.value:
        model_to_use = db_setting.value
    else:
        model_to_use = current_app.config.get('DEFAULT_GEMINI_MODEL')
        if not model_to_use:
            current_app.logger.error("DEFAULT_GEMINI_MODEL not found in database or config.py.")
            model_to_use = "gemini-1.5-flash" 
            current_app.logger.warning(f"Critical: Using hardcoded fallback Gemini model: {model_to_use}.")
        else:
            current_app.logger.warning(f"Using DEFAULT_GEMINI_MODEL '{model_to_use}' from config.py (not found in DB or DB value empty).")
    
    model = genai.GenerativeModel(model_name=model_to_use, safety_settings=safety_settings)

    gemini_history = []
    for entry in log_entries:
        role = 'user' if entry['sender'] == 'user' else 'model'
        gemini_history.append({'role': role, 'parts': [{'text': entry['text']}]})

    chat = model.start_chat(history=gemini_history)
    
    prompt_text_to_send = "" 
    is_initial_adventure_prompt = False

    if not gemini_history and user_message == "__START_ADVENTURE__":
        is_initial_adventure_prompt = True
        
        skills_list = []
        if character.current_proficiencies:
            try:
                prof_data = json.loads(character.current_proficiencies)
                if isinstance(prof_data, dict) and isinstance(prof_data.get('skills'), list):
                    skills_list = prof_data.get('skills', [])
            except json.JSONDecodeError:
                current_app.logger.warning(f"Malformed current_proficiencies JSON for character {character_id}: {character.current_proficiencies}")
        
        skills_string = ", ".join(skills_list) if skills_list else "Not specified"

        prompt_text_to_send = (
            f"You are a Dungeon Master for a D&D 5e style game. I am your player. "
            f"My character is named {character.name}, a level {character.level} {character.race.name} {character.char_class.name}. "
            f"Character Description: {character.description or 'Not specified'}. "
            f"Character Alignment: {character.alignment or 'Not specified'}. "
            f"Character Background: {character.background_name or 'Not specified'}. "
            f"Key Skills: {skills_string}. "
            f"If the character description or background is 'Not specified' or very brief, please ask me some questions to help flesh out my character's history and motivations. Ask only one question at a time regarding this. "
            
            # Dice Roll and Player Guidance Instructions:
            "Your role is to guide me through the adventure. When a situation requires a dice roll, please ask me to make a specific roll (e.g., 'Make a Dexterity (Stealth) check'). "
            "When I (the player) send a message that clearly states a dice roll result (e.g., 'Rolling Strength Check (1d20+2): Rolled [15] + 2 = 17'), you should acknowledge this roll and incorporate its outcome into your narrative response. For example, if I roll high on a persuasion check, describe how the NPC is convinced. If I roll low on an attack, describe how my attack misses or is parried. "
            "Pay close attention to the context of the roll. If I state I am making a roll that seems inappropriate for the current situation (e.g., rolling for damage before an attack roll has been made and confirmed to hit, or rolling a skill check that doesn't fit the narrative or your last request), gently point this out. Explain what kind of roll you were expecting or why my stated roll might not be suitable right now, and then ask me to make the correct roll or to clarify my action. Your goal is to help me learn and ensure the game flows logically, but do so in a helpful and immersive way. Don't be overly strict if I'm just learning or if the roll could be creatively interpreted. "
            
            # Interaction Style:
            "When you need information from me, please ask only one question at a time. If you need more information, ask for it in a subsequent interaction. This will help keep our interactions clear and focused. "
            
            # Game Mechanics:
            "You will also need to keep track of my character's experience points (XP). Inform me when I have gained enough XP to level up and guide me through that process if necessary (though actual level-up mechanics are handled outside this chat). For now, just letting me know I can level up is sufficient. "
            
            # Starting the Adventure:
            "Please start our adventure now. Ask me some engaging questions about what kind of story or challenges I'm looking for. " # This is the line to modify
            "Also, let me know if you prefer a game where I, as the DM, provide more guidance and steer the story, or if you'd prefer more freedom to explore and make decisions independently. " # New question added
            "Make your response immersive and welcoming. Keep your initial questions concise (perhaps 2-3 short questions to get started, remembering the one-question-at-a-time rule for follow-ups)."
        )
    else:
        prompt_text_to_send = user_message

    ai_response_text = ""
    try:
        response = chat.send_message(prompt_text_to_send) 
        ai_response_text = response.text
    except Exception as e:
        current_app.logger.error(f"Error sending message to Gemini: {str(e)}")
        ai_response_text = _("The Dungeon Master seems to be lost in thought and couldn't quite catch that. Could you try again?")
        if is_initial_adventure_prompt:
            log_entries.append({"sender": "dm", "text": ai_response_text})
            character.adventure_log = json.dumps(log_entries)
            db.session.commit()
        return {"reply": ai_response_text} # Return as dict

    if user_message == "__START_ADVENTURE__":
        log_entries.append({"sender": "dm", "text": ai_response_text})
    else:
        log_entries.append({"sender": "user", "text": user_message})
        log_entries.append({"sender": "dm", "text": ai_response_text})

    character.adventure_log = json.dumps(log_entries)
    db.session.commit()

    return {"reply": ai_response_text} # Return as dict, status code 200 implied
