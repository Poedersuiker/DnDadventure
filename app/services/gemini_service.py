import google.generativeai as genai
from flask import current_app
import markdown2

def get_gemini_model():
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        # In a real scenario, you might want to log this or handle it more gracefully
        # For this task, we'll let it raise an error if the key is missing,
        # or return a mock/dummy model if that's preferred for testing without a key.
        current_app.logger.warning("GEMINI_API_KEY not set. Gemini functionality will be disabled.")
        raise ValueError("GEMINI_API_KEY not set.")
    
    genai.configure(api_key=api_key)
    # For this task, we'll use 'gemini-pro' as specified.
    # Ensure this model is available and suitable for your use case.
    model = genai.GenerativeModel('gemini-pro')
    return model

def generate_story_prompt(character_name, character_details, user_input, chat_history_str=None):
    # Basic prompt engineering. This will likely need refinement.
    prompt = f"""You are a Dungeon Master for a solo Dungeons & Dragons adventure.
The player character is {character_name}.
Character details: {character_details}

Continue the adventure based on the player's last action. Be descriptive and engaging.
If this is the start of the adventure, and the user says "start adventure" or similar, begin with an introductory scenario.

Previous conversation:
{chat_history_str if chat_history_str else "No previous conversation yet."}

Player's action: {user_input}

What happens next? Make sure your response is engaging and moves the story forward. If combat is initiated, describe the scene and prompt for player action.
"""
    return prompt

def get_story_response(character, user_input, chat_history_objects=None):
    # Let exceptions like ValueError from get_gemini_model propagate to the route
    # The route will then handle returning the appropriate HTTP error (e.g., 503)
    model = get_gemini_model()


    # Simplified character details string for now
    char_details_str = f"Race: {character.race}, Class: {character.character_class}, Level: {character.level}, Alignment: {character.alignment}, Background: {character.background}"
    
    # Construct a simple text-based history for the prompt if available
    simple_history_str = ""
    if chat_history_objects: # chat_history_objects would be a list of database ChatMessage objects
        # This part is a placeholder for when ChatMessage model is introduced
        # For now, this will likely remain empty as chat_history_objects isn't being passed
        simple_history_str = "\n".join([
            f"{'Player' if turn.entry_type == 'user_message' else 'DM'}: {turn.message}"
            for turn in chat_history_objects
        ])

    prompt = generate_story_prompt(character.name, char_details_str, user_input, simple_history_str)
    
    current_app.logger.info(f"Generated Gemini Prompt for {character.name}: {prompt[:200]}...") # Log a snippet

    # For gemini-pro, use generate_content
    response = model.generate_content(prompt) # Allow exceptions to propagate
    # Check if response.text is None or empty
    if response.text:
        # Convert Markdown to HTML
        html_output = markdown2.markdown(response.text)
        return html_output
    else:
        # This case might occur if the response was blocked or had no content.
        current_app.logger.warning(f"Gemini API returned empty response for prompt: {prompt[:200]}...")
        # Check for parts and candidates for more detailed logging if needed
        if response.parts:
                current_app.logger.warning(f"Gemini response parts: {response.parts}")
        if response.candidates and response.candidates[0].finish_reason != 'STOP':
                current_app.logger.warning(f"Gemini finish reason: {response.candidates[0].finish_reason}")
                # Raise an exception that can be caught by the route to return a 500 or similar
                raise Exception("Gemini content filtered or empty") 
        # If no text and not filtered, it's an unusual empty response.
        raise Exception("Gemini returned no response text.")
