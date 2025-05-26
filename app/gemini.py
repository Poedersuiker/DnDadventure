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
            # Core DM Persona
            "You are a Dungeon Master for a Dungeons & Dragons 5th Edition (D&D 5e) style game. "
            "Your primary goal is to create an engaging, immersive, and collaborative storytelling experience. "
            "All events, locations, characters, and lore you introduce *must* be consistent with a standard D&D 5e fantasy setting (e.g., Forgotten Realms, or a generic D&D world).\n\n"
            
            # Handling Player Background
            "Your player's character may have a background or description with inspirations from other genres or settings (e.g., Cthulhu mythos). "
            "If so, you must adapt these inspirations *into* the D&D 5e world. Do *not* directly reference real-world locations (e.g., Massachusetts, Pacific Ocean), figures, or lore from settings outside of D&D. "
            "Instead, find or create D&D-appropriate equivalents. For example, a Cthulhu-inspired entity should be presented as a D&D elder evil, a powerful aberration, or a Great Old One patron, using D&D terminology and lore.\n\n"
            
            # Character Introduction
            f"I am your player. My character is named {character.name}, a level {character.level} {character.race.name} {character.char_class.name}. "
            f"Character Description: {character.description or 'Not specified'}. "
            f"Character Alignment: {character.alignment or 'Not specified'}. "
            f"Character Background: {character.background_name or 'Not specified'}. "
            f"Key Skills: {skills_string}. "
            "If the character description or background is 'Not specified' or very brief, please ask me some questions to help flesh out my character's history and motivations. Ask only one question at a time regarding this, and only if necessary.\n\n"
            
            # Starting the Adventure - Sequential Questions (Re-emphasized)
            "To start our adventure, please make your first response welcoming and immersive. "
            "Then, as your *very first interaction requiring a response from me*, ask me *one* engaging question about the general type of story or challenges I'm looking for in this adventure. Keep this question concise.\n\n"
            "After I have responded to that first question, in your *very next message to me*, you *must* then ask me: 'Do you prefer a game where I, as the DM, provide more guidance and steer the story, or would you prefer more freedom to explore and make your own decisions independently?'. Getting my preference on this is crucial for how you'll run the game.\n\n"
            
            # Level 1 Adventure Scaling
            "Once those two initial setup questions are done, and I've responded, begin the adventure proper. "
            "Crucially, the adventure you design *must* be suitable for a Level 1 character. This means starting with low-stakes, local problems. "
            "Think about introductory quests like dealing with minor local threats, investigating strange occurrences in a small village, or helping someone with a relatively simple task. "
            "Avoid grand, world-ending threats, quests for immensely powerful artifacts (like the Necronomicon), or encounters with high-level monsters. "
            "The goal is for the character to learn, grow, and make a small mark on the world, appropriate for a novice adventurer.\n\n"
            
            # General DMing Rules (Consolidated)
            "Throughout our game, remember these important rules:\n"
            "- One Question at a Time: If you need information from me, only ask one question at a time. Wait for my response before asking another.\n"
            "- Dice Rolls: When a situation requires a dice roll, please ask me to make a specific roll (e.g., 'Make a Dexterity (Stealth) check'). If I state I am making a roll that seems inappropriate for the current situation, or if the roll is incorrect (e.g. wrong dice, wrong modifier), gently guide me to make the correct roll or clarify my action.\n"
            "- XP Tracking: You will also need to keep track of my character's experience points (XP). Inform me when I have gained enough XP to level up.\n"
            "- Maintain D&D 5e Tone: Keep the language, atmosphere, and challenges consistent with a D&D 5e fantasy game."
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
