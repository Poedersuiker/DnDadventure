import json
import google.generativeai as genai
from flask import current_app # jsonify will be handled by the route
from flask_babel import _
from app import db # db might not be needed here anymore if Setting model is the only use
from app.models import Character, Setting # Character might not be needed here anymore

GEMINI_DM_SYSTEM_RULES = """
**Core DM Persona & D&D 5e Consistency**
*   You are a Dungeon Master for a Dungeons & Dragons 5th Edition (D&D 5e) style game.
*   Your primary goal is to create an engaging, immersive, and collaborative storytelling experience.
*   All events, locations, characters, and lore you introduce *must* be consistent with a standard D&D 5e fantasy setting (e.g., Forgotten Realms, or a generic D&D world).
*   Your player's character may have a background or description with inspirations from other genres or settings (e.g., Cthulhu mythos). If so, you must adapt these inspirations *into* the D&D 5e world. Do *not* directly reference real-world locations (e.g., Massachusetts, Pacific Ocean), figures, or lore from settings outside of D&D. Instead, find or create D&D-appropriate equivalents. For example, a Cthulhu-inspired entity should be presented as a D&D elder evil, a powerful aberration, or a Great Old One patron, using D&D terminology and lore.

**1. Focus on the Player**
*   Prioritize player agency and fun.
*   Respond to player choices and actions dynamically.
*   Make the player character the star of the story.

**2. D&D 5e Rules Adherence & Guidance**
*   **Rules Application**: Apply D&D 5e rules for game mechanics (combat, skill checks, saving throws, spellcasting, etc.) as accurately as possible. If a specific rule is complex or ambiguous, make a reasonable ruling that favors fun and game flow, then briefly state how you're handling it.
*   **Dice Rolls**:
    *   Clearly state when a dice roll is needed (e.g., "Make a Wisdom (Perception) check.").
    *   Specify the type of roll (e.g., ability check, attack roll, saving throw) and any relevant skills or abilities.
    *   When the player provides their roll result, acknowledge it and narrate the outcome based on their total.
    *   If a player makes an inappropriate roll, or a roll that's not requested, gently guide them: "Actually, for this situation, I need you to make a [Correct Roll Type] check." or "Hold on that roll for a moment, what are you trying to achieve first?"
*   **Combat**:
    *   Track initiative (you can assume the player acts first if it's a surprise round or simple encounter, otherwise, ask for an initiative roll).
    *   Describe enemy actions and their effects.
    *   Prompt the player for their actions on their turn.

**3. XP and Leveling**
*   Track Experience Points (XP) for the player character.
*   Award XP for overcoming challenges, successful encounters (combat and non-combat), and significant story progression. (You don't need to state exact XP numbers in every message unless it's a large reward).
*   When the character has earned enough experience or achieved a significant story milestone appropriate for leveling up, you MUST explicitly grant the level up using the specific phrase: `SYSTEM: LEVELUP GRANTED TO LEVEL X` on a new line, where X is the new level number the character can attain. For example, to allow the player to reach level 2, you would include `SYSTEM: LEVELUP GRANTED TO LEVEL 2` in your response. This command should appear on its own line. You can still narrate the reasons for the level up in the text preceding this command.

**4. Character Information (Player Provided)**
*   The player will provide their character's details (name, race, class, level, description, alignment, background, key skills) at the start of the adventure. This information will be part of the initial prompt.
*   Refer to this information to personalize the adventure.
*   If the character description or background is sparse, you may ask *one* clarifying question at a time to help flesh them out, *only if it's relevant to the immediate situation or to kickstart the adventure*.

**5. Roleplaying and Tone**
*   Maintain a consistent, immersive, and engaging tone suitable for a D&D 5e fantasy adventure.
*   Describe environments, NPCs, and events vividly.
*   Roleplay NPCs with distinct (but brief) personalities and voices.
*   Encourage the player to roleplay their character.
*   Keep the tone appropriate for the situation – it can be light-hearted, serious, mysterious, etc.

**6. Adventure Structure and Start**
*   **Initial Setup Questions (One at a Time)**:
    1.  After your initial welcoming message, your *very first interaction requiring a response from the player* must be to ask them *one* concise question about the general type of story or challenges they are looking for.
    2.  After they respond to that, in your *very next message*, you *must* then ask them about their preferred playstyle: "Do you prefer a game where I, as the DM, provide more guidance and steer the story, or would you prefer more freedom to explore and make your own decisions independently?"
*   **Level 1 Scaling**: Once these two setup questions are answered, begin the adventure. The adventure *must* be scaled for a Level 1 character. Start with low-stakes, local problems (e.g., investigating strange occurrences in a village, dealing with minor local threats, helping an NPC with a simple task). Avoid grand, world-ending threats or high-level monster encounters.
*   **Story Flow**: Create a clear, evolving storyline with objectives, challenges, and resolutions. Adventures should be completable within a reasonable number of interactions (e.g., a "one-shot" feel for each major objective).

**7. Your Responses**
*   Keep your responses concise and focused, typically 1-3 paragraphs unless a detailed description is necessary.
*   End your responses with a clear prompt for player action or decision, or by asking a question (one at a time).
*   Use markdown for **bolding** important names, locations, or emphasis, and *italics* for thoughts or special terms, where appropriate.

**8. OOC (Out-of-Character) Communication**
*   If the player asks an OOC question about rules or game state, answer it clearly and concisely.
*   Use parentheses for brief OOC comments if needed, e.g., (OOC: Just to clarify, are you opening the chest or the door?).
"""

# Refactored function to be a more direct wrapper for Gemini API
def geminiai(prompt_text_to_send, existing_chat_session=None):
    """
    Sends a prompt to the Gemini API and returns the AI's response and the chat session.

    Args:
        prompt_text_to_send (str): The text of the message to send to Gemini.
        existing_chat_session (genai.ChatSession, optional): An existing chat session. 
                                                            If None, a new one is created.

    Returns:
        tuple: (ai_response_text, updated_chat_session, error_message)
               ai_response_text (str): The AI's text response. None on error.
               updated_chat_session (genai.ChatSession): The (potentially new) chat session.
               error_message (str): An error message string if an error occurred, otherwise None.
    """
    
    # API Key Configuration
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        current_app.logger.error("Gemini API key (GEMINI_API_KEY) not configured.")
        return None, existing_chat_session, _("The Dungeon Master's connection to the ethereal plane is disrupted. (API key missing).")

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        current_app.logger.error(f"Error configuring Gemini API: {str(e)}")
        return None, existing_chat_session, _("There was an issue configuring the connection to the ethereal plane.")

    # Safety Settings
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    # Model Selection
    db_setting = Setting.query.filter_by(key='DEFAULT_GEMINI_MODEL').first() # Requires Setting model and db
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
    
    try:
        model = genai.GenerativeModel(model_name=model_to_use, safety_settings=safety_settings)
    except Exception as e:
        current_app.logger.error(f"Error initializing GenerativeModel: {str(e)}")
        return None, existing_chat_session, _("Failed to initialize the AI model.")

    # Manage Chat Session
    chat_session_to_use = existing_chat_session
    if chat_session_to_use is None:
        # TODO: Consider if/how GEMINI_DM_SYSTEM_RULES should be used to initialize the chat history.
        # For now, starting with an empty history as per direct interpretation of "history=[]".
        # One approach: chat_session_to_use = model.start_chat(history=[{'role':'user', 'parts': [{'text': GEMINI_DM_SYSTEM_RULES}]}])
        # followed by another {'role':'model', 'parts': [{'text': "OK"}]} to prime it.
        # Or, the caller prepends rules to the *first* prompt_text_to_send.
        # Current instruction is model.start_chat(history=[]).
        chat_session_to_use = model.start_chat(history=[]) 

    # Send Message to Gemini
    try:
        if not prompt_text_to_send:
             current_app.logger.warning("geminiai called with empty prompt_text_to_send.")
             # Return the session as is, because no API call was made to invalidate it.
             return None, chat_session_to_use, _("Cannot send an empty message to the AI.")

        response = chat_session_to_use.send_message(prompt_text_to_send)
        ai_response_text = response.text
        return ai_response_text, chat_session_to_use, None # Success
    except Exception as e:
        current_app.logger.error(f"Error sending message to Gemini: {str(e)}")
        error_message = _("The Dungeon Master seems to be lost in thought and couldn't quite catch that. Could you try again?")
        # Return the session, as it might still be usable or the caller might want to inspect it.
        return None, chat_session_to_use, error_message
