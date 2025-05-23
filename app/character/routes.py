from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.character import bp
from app.character.forms import CharacterCreationForm # Updated import location
from app.models import Character
import requests
from bs4 import BeautifulSoup
import re # For cleaning up names for URLs

# D&D 5e Class Data (Simplified)
CLASS_DATA = {
    "Artificer": {"hit_dice": 8, "saves": ["constitution", "intelligence"], "skills_options": [], "skills_count": 2},
    "Barbarian": {"hit_dice": 12, "saves": ["strength", "constitution"], "skills_options": ["animal_handling", "athletics", "intimidation", "nature", "perception", "survival"], "skills_count": 2},
    "Bard": {"hit_dice": 8, "saves": ["dexterity", "charisma"], "skills_options": "any", "skills_count": 3}, # Can choose any 3 skills
    "Cleric": {"hit_dice": 8, "saves": ["wisdom", "charisma"], "skills_options": ["history", "insight", "medicine", "persuasion", "religion"], "skills_count": 2},
    "Druid": {"hit_dice": 8, "saves": ["intelligence", "wisdom"], "skills_options": ["arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"], "skills_count": 2},
    "Fighter": {"hit_dice": 10, "saves": ["strength", "constitution"], "skills_options": ["acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception", "survival"], "skills_count": 2},
    "Monk": {"hit_dice": 8, "saves": ["strength", "dexterity"], "skills_options": ["acrobatics", "athletics", "history", "insight", "religion", "stealth"], "skills_count": 2},
    "Paladin": {"hit_dice": 10, "saves": ["wisdom", "charisma"], "skills_options": ["athletics", "insight", "intimidation", "medicine", "persuasion", "religion"], "skills_count": 2},
    "Ranger": {"hit_dice": 10, "saves": ["strength", "dexterity"], "skills_options": ["animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"], "skills_count": 3},
    "Rogue": {"hit_dice": 8, "saves": ["dexterity", "intelligence"], "skills_options": ["acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance", "persuasion", "sleight_of_hand", "stealth"], "skills_count": 4},
    "Sorcerer": {"hit_dice": 6, "saves": ["constitution", "charisma"], "skills_options": ["arcana", "deception", "insight", "intimidation", "persuasion", "religion"], "skills_count": 2},
    "Warlock": {"hit_dice": 8, "saves": ["wisdom", "charisma"], "skills_options": ["arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"], "skills_count": 2},
    "Wizard": {"hit_dice": 6, "saves": ["intelligence", "wisdom"], "skills_options": ["arcana", "history", "insight", "investigation", "medicine", "religion"], "skills_count": 2},
    # Default fallback if class is not in the list or is mis-typed
    "Default": {"hit_dice": 8, "saves": [], "skills_options": [], "skills_count": 0}
}

@bp.route('/create_character', methods=['GET', 'POST'])
@login_required
def create_character():
    form = CharacterCreationForm()
    if form.validate_on_submit():
        # Get class chosen by user
        char_class_name = form.character_class.data.capitalize() # Ensure consistent capitalization
        class_info = CLASS_DATA.get(char_class_name, CLASS_DATA["Default"])

        # Create character with basic info first to allow ability score calculations
        # For now, ability scores default to 10 in the model, so modifier is 0
        # In the future, these would be set by the form.
        character = Character(
            name=form.name.data,
            race=form.race.data, # Race might influence speed or other stats in the future
            character_class=char_class_name,
            level=1, # Start at level 1
            owner=current_user,
            # Default ability scores are set in model, will be used by get_modifier_for_ability
            # strength=form.strength.data, # Future: get from form
            # dexterity=form.dexterity.data, # Future: get from form
            # constitution=form.constitution.data, # Future: get from form
            # intelligence=form.intelligence.data, # Future: get from form
            # wisdom=form.wisdom.data, # Future: get from form
            # charisma=form.charisma.data, # Future: get from form
        )

        # Set Hit Dice Type
        character.hit_dice_type = class_info["hit_dice"]
        
        # Calculate Max HP: Hit Die size + Constitution modifier
        # Model's get_modifier_for_ability('constitution') will use the default 10 (mod 0) for now
        con_modifier = character.get_modifier_for_ability('constitution')
        character.max_hp = class_info["hit_dice"] + con_modifier
        character.current_hp = character.max_hp # Initialize current_hp

        # Set Hit Dice counts
        character.hit_dice_max = character.level # Level 1, so 1
        character.hit_dice_current = character.level # Level 1, so 1

        # Set Saving Throw Proficiencies
        for ability_save in class_info["saves"]:
            setattr(character, f"prof_{ability_save}_save", True)
            
        # Set default speed (Race might modify this later)
        character.speed = 30 # Default speed

        # Skill proficiencies will be handled later (e.g., based on class & background choices)
        # For now, they default to False as per the model.

        # 1. Extract race and class from form
        race_name = form.race.data
        class_name = form.character_class.data.capitalize() # Ensure consistent capitalization for fetching and display

        # 2. Fetch info from Roll20 for this race/class
        current_app.logger.info(f"Fetching summary for Race: {race_name}")
        race_summary = fetch_roll20_summary(race_name, "Race")
        current_app.logger.info(f"Fetching summary for Class: {class_name}")
        class_summary = fetch_roll20_summary(class_name, "Class")
        
        # 3. Then create the Character object, add to DB, commit.
        # Note: Character object creation was already here, just moving fetch before it.
        # The actual character object doesn't store these summaries, so this order is for logical flow.
        # If summaries were part of the model, this order would be critical.
        
        # Re-fetch class_info for character creation based on capitalized class_name
        class_info = CLASS_DATA.get(class_name, CLASS_DATA["Default"])

        character = Character(
            name=form.name.data,
            race=race_name, 
            character_class=class_name,
            level=1, 
            owner=current_user,
            # Default ability scores are set in model
        )
        character.hit_dice_type = class_info["hit_dice"]
        con_modifier = character.get_modifier_for_ability('constitution')
        character.max_hp = class_info["hit_dice"] + con_modifier
        character.current_hp = character.max_hp
        character.hit_dice_max = character.level
        character.hit_dice_current = character.level
        for ability_save in class_info["saves"]:
            setattr(character, f"prof_{ability_save}_save", True)
        character.speed = 30

        db.session.add(character)
        db.session.commit()

        # 4. Flash a message containing the fetched summary for race/class.
        flash(f'Character {character.name} ({character.race} {character.character_class}) created successfully!', 'success')
        if race_summary:
            flash(f"About {race_name}: {race_summary}", 'info')
        else:
            flash(f"Could not fetch summary for {race_name}.", 'warning')
        if class_summary:
            flash(f"About {class_name}: {class_summary}", 'info')
        else:
            flash(f"Could not fetch summary for {class_name}.", 'warning')
            
        return redirect(url_for('character.select_character')) # Redirect to character selection
    return render_template('character/create_character.html', title='Create Character', form=form)

def format_name_for_roll20_url(name: str) -> str:
    """Formats a name for Roll20 URL fragment IDs.
    e.g., 'Half-Elf' -> 'Half-Elf', 'High Elf' -> 'High_Elf'
    """
    # General approach: replace spaces with underscores.
    # Roll20 seems to handle capitalization fairly well in URLs, but fragment IDs might be case-sensitive.
    # The CLASS_DATA keys and RACE_CHOICES values are generally well-capitalized.
    return name.replace(' ', '_')

def fetch_roll20_summary(item_name: str, item_type: str) -> str | None:
    """
    Fetches a brief summary for a race or class from Roll20 Compendium.
    item_type should be "Race" or "Class".
    """
    formatted_name = format_name_for_roll20_url(item_name)
    
    # Determine the base URL and the list page name
    if item_type == "Race":
        # Races are listed under "Races List", but individual pages are often just the race name
        # e.g. https://roll20.net/compendium/dnd5e/Elf#h-Elf
        # For races with subraces like "Elf", the main page is just "Elf".
        # For "Half-Elf", it's "Half-Elf".
        # Let's try direct compendium page first, then the list page if that fails.
        # Direct page: https://roll20.net/compendium/dnd5e/{FormattedName}#h-{FormattedName}
        url = f"https://roll20.net/compendium/dnd5e/{formatted_name}#h-{formatted_name}"
    elif item_type == "Class":
        # e.g. https://roll20.net/compendium/dnd5e/Fighter#h-Fighter
        url = f"https://roll20.net/compendium/dnd5e/{formatted_name}#h-{formatted_name}"
    else:
        current_app.logger.error(f"Invalid item_type for Roll20 fetch: {item_type}")
        return None

    current_app.logger.info(f"Attempting to fetch Roll20 summary from URL: {url}")
    
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status() # Raise an exception for HTTP errors
    except requests.RequestException as e:
        current_app.logger.error(f"Error fetching URL {url}: {e}")
        # Fallback for races: try the "Races List" page if direct page fails or gives 404.
        # This is because some races (like subraces) might only be on the main list page.
        if item_type == "Race":
            url = f"https://roll20.net/compendium/dnd5e/Races%20List#h-{formatted_name}"
            current_app.logger.info(f"Retrying with race list URL: {url}")
            try:
                response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()
            except requests.RequestException as e_fallback:
                current_app.logger.error(f"Error fetching fallback URL {url}: {e_fallback}")
                return None
        else: # For classes, if direct page fails, we stop.
             return None


    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Try to find the specific header for the item, e.g., <h1 id="h-Elf">Elf</h1>
    # Roll20 uses h1, h2, h3 etc. for these anchors.
    # The ID is typically 'h-' + formatted_name.
    header_id = f"h-{formatted_name}"
    header = soup.find(lambda tag: tag.name in ['h1','h2','h3','h4'] and tag.has_attr('id') and tag['id'] == header_id)

    if not header:
        current_app.logger.warning(f"Could not find header with id '{header_id}' on {url}")
        # As a broader fallback, look for the first <p> in the main content area if header is missing
        # The main content area is usually within a div with class 'pagecontent' or similar.
        main_content = soup.find('div', id='pagecontent')
        if main_content:
            first_p = main_content.find('p')
            if first_p and first_p.get_text(strip=True):
                current_app.logger.info(f"Found fallback paragraph in #pagecontent for {item_name}")
                return first_p.get_text(strip=True)[:500] + "..." # Limit length
        return None

    # Find the first <p> tag that is a sibling to the header or a child of a common parent.
    # This logic can be complex. A common pattern is header followed by paragraphs.
    # We'll look for the first <p> immediately following the header's parent or the header itself.
    
    # Iterate through next siblings of the header to find the first <p>
    current_element = header
    while current_element:
        if current_element.name == 'p' and current_element.get_text(strip=True):
            summary = current_element.get_text(strip=True)
            current_app.logger.info(f"Found summary for {item_name}: {summary[:50]}...")
            return summary[:500] + "..." # Limit length
        current_element = current_element.find_next_sibling()
        
    # If no <p> sibling, try looking within the header's parent, after the header.
    # This can be less reliable. For now, the sibling search is preferred.
    # If that fails, check the parent's children paragraphs after the header's index.

    current_app.logger.warning(f"Could not find a suitable <p> tag after header for {item_name} on {url}")
    return None


@bp.route('/select_character')
@login_required
def select_character():
    characters = Character.query.filter_by(user_id=current_user.id).all() # type: ignore
    return render_template('character/select_character.html', title='Select Character', characters=characters)

@bp.route('/adventure/<int:character_id>')
@login_required
def adventure(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        # Not the owner, return 403 Forbidden
        # Alternatively, could return 404 to not reveal character existence
        return render_template('errors/403.html'), 403 # You'll need to create this template
    
    # Load adventure log entries
    log_entries = AdventureLogEntry.query.filter_by(character_id=character.id).order_by(AdventureLogEntry.timestamp.asc()).all()
    
    # For Level Up display
    from app.models import XP_THRESHOLDS # Import XP_THRESHOLDS
    can_level_up_status = character.can_level_up()
    xp_for_next_level = XP_THRESHOLDS[character.level] if character.level < 20 else "Max Level"


    return render_template('character/adventure.html', title='Adventure', 
                           character=character, log_entries=log_entries,
                           xp_thresholds=XP_THRESHOLDS, # Pass thresholds to template
                           can_level_up=can_level_up_status,
                           xp_for_next_level=xp_for_next_level)

@bp.route('/character/<int:character_id>/level-up', methods=['POST'])
@login_required
def level_up_character(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        flash("You are not authorized to level up this character.", "danger")
        return redirect(url_for('character.select_character'))

    if character.level_up():
        db.session.commit()
        flash(f"{character.name} has reached level {character.level}!", "success")
    else:
        if character.level >= 20:
            flash(f"{character.name} is already at the maximum level (20).", "info")
        else:
            # XP_THRESHOLDS is 0-indexed for levels 1-20. XP_THRESHOLDS[character.level] is for next level.
            xp_needed = XP_THRESHOLDS[character.level] if character.level < 20 else 0
            flash(f"{character.name} does not have enough experience ({character.experience_points}/{xp_needed}) to level up.", "warning")
            
    return redirect(url_for('character.adventure', character_id=character.id))


from app.models import AdventureLogEntry # Add this import
from app.extensions import db # Add this import
import json # Add this import

@bp.route('/adventure/<int:character_id>/chat', methods=['POST'])
@login_required
def adventure_chat(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Missing message in request'}), 400

    user_input = data['message']

    # Save user's message
    user_log_entry = AdventureLogEntry(
        character_id=character.id,
        entry_type="user_message",
        message=user_input,
        actor_name=character.name
    )
    db.session.add(user_log_entry)
    
    # Retrieve chat history for Gemini context (simplified for now)
    # In a more advanced setup, you might pass structured history
    chat_history_for_gemini = AdventureLogEntry.query.filter_by(character_id=character.id).order_by(AdventureLogEntry.timestamp.asc()).all()

    from app.services.gemini_service import get_story_response
    try:
        gemini_response = get_story_response(character, user_input, chat_history_for_gemini)
    except ValueError as e: # Catch API key error specifically
        db.session.rollback() # Rollback user message if Gemini fails
        return jsonify({'reply': str(e)}), 503 # Service Unavailable
    except Exception as e: # Catch other errors from the service
        db.session.rollback()
        current_app.logger.error(f"Error in get_story_response: {e}")
        return jsonify({'reply': "An unexpected error occurred with the storyteller."}), 500

    # Save Gemini's response
    gemini_log_entry = AdventureLogEntry(
        character_id=character.id,
        entry_type="gemini_response",
        message=gemini_response,
        actor_name="DM"
    )
    db.session.add(gemini_log_entry)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database commit error in chat: {e}")
        return jsonify({'reply': "Error saving adventure progress."}), 500

    return jsonify({'reply': gemini_response})

# @bp.route('/adventure/<int:character_id>/roll_action', methods=['POST'])
# @login_required
# def roll_action(character_id):
#     character = Character.query.get_or_404(character_id)
#     if character.owner != current_user:
#         return jsonify({'error': 'Forbidden'}), 403

#     data = request.get_json()
#     if not data or 'action_type' not in data:
#         return jsonify({'error': 'Missing action_type in request'}), 400

#     action_type = data.get('action_type')
#     stat_name = data.get('stat_name', '').lower() # e.g., 'strength', 'dexterity'
#     # skill_name = data.get('skill_name', '') # e.g., 'Acrobatics' - for future use
    
#     from app.utils.dice_roller import roll_dice # Moved to top-level imports
#     roll_result = {}
#     message = ""

#     try:
#         if action_type == "attack":
#             # Simple attack roll: 1d20 + (Dex or Str modifier, let's assume Str for now or make it simple)
#             # For now, let's make it a simple d20 roll without complex modifier logic from character stats
#             # to keep the initial implementation straightforward.
#             # A more complex implementation would check character.proficient_in_weapon, character.weapon_used etc.
#             attack_modifier_from_char = character.get_modifier_for_ability('strength') # Example
#             # Add proficiency bonus if it were a weapon attack the character is proficient with
#             # attack_modifier_from_char += character.proficiency_bonus 
#             roll_result = roll_dice(sides=20, num_dice=1, modifier=data.get('modifier_override', attack_modifier_from_char))
#             message = f"{character.name} attacks! Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"

#         elif action_type == "skill_check":
#             if not stat_name:
#                 return jsonify({'error': 'Missing stat_name for skill_check'}), 400
            
#             ability_modifier = character.get_modifier_for_ability(stat_name)
#             # In a full system, skill proficiency might add character.proficiency_bonus
#             # For a specific skill like 'Acrobatics (Dex)', you'd check if proficient in Acrobatics.
#             roll_result = roll_dice(sides=20, num_dice=1, modifier=ability_modifier)
#             skill_display_name = data.get('skill_name', stat_name.capitalize())
#             message = f"{character.name} attempts a {skill_display_name} check. Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"

#         elif action_type == "saving_throw":
#             if not stat_name:
#                 return jsonify({'error': 'Missing stat_name for saving_throw'}), 400
            
#             ability_modifier = character.get_modifier_for_ability(stat_name)
#             # Proficiency in saving throws for certain classes could be added here
#             # e.g. if character.class_has_strength_save_proficiency: modifier += character.proficiency_bonus
#             roll_result = roll_dice(sides=20, num_dice=1, modifier=ability_modifier)
#             message = f"{character.name} makes a {stat_name.capitalize()} saving throw! Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"
        
#         elif action_type == "damage":
#             dice_type = data.get('dice_type')
#             num_dice = data.get('num_dice', 1)
#             modifier = data.get('modifier', 0) # This could come from character.get_modifier_for_ability(stat_name)
#             if not dice_type:
#                 return jsonify({'error': 'Missing dice_type for damage roll'}),400
#             roll_result = roll_dice(sides=dice_type, num_dice=num_dice, modifier=modifier)
#             message = f"{character.name} deals damage! Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"

#         else:
#             return jsonify({'error': 'Invalid action_type'}), 400
        
#         # Save the action roll to the log
#         action_log_entry = AdventureLogEntry(
#             character_id=character.id,
#             entry_type="action_roll",
#             message=message,
#             actor_name=character.name,
#             roll_details=json.dumps(roll_result)
#         )
#         db.session.add(action_log_entry)
#         try:
#             db.session.commit()
#         except Exception as e:
#             db.session.rollback()
#             current_app.logger.error(f"Database commit error in roll_action: {e}")
#             # Still return the roll result to the user, but log the DB error
#             return jsonify({'message': message, 'roll_details': roll_result, 'db_error': 'Error saving action to log.'}), 500


#         return jsonify({'message': message, 'roll_details': roll_result})

#     except ValueError as e: # Catch errors from roll_dice or bad stat_names
#         current_app.logger.error(f"Error during roll_action: {e}")
#         return jsonify({'error': str(e)}), 400
#     except Exception as e:
#         current_app.logger.error(f"Unexpected error in roll_action: {e}")
#         return jsonify({'error': 'An unexpected error occurred.'}), 500

# --- New Specific Roll Routes ---
from app.utils.dice_roller import roll_dice # Ensure it's at the top if not already

def _log_and_respond(character, roll_result, message_template, action_name="action"):
    """Helper function to log action and return JSON response."""
    # Use action_name to fill in the message if a specific skill/ability name is not available
    display_name = action_name # Default if not more specific
    if hasattr(roll_result, 'get') and roll_result.get('skill_name'): # if skill_name was passed in payload and preserved
        display_name = roll_result['skill_name']
    
    message = message_template.format(
        name=character.name,
        action=display_name, # Use the more specific name if available
        total=roll_result['total_with_modifier'],
        desc=roll_result['description']
    )
    
    log_entry = AdventureLogEntry(
        character_id=character.id,
        entry_type="action_roll",
        message=message,
        actor_name=character.name,
        roll_details=json.dumps(roll_result)
    )
    db.session.add(log_entry)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database commit error in _log_and_respond: {e}")
        return jsonify({'message': message, 'roll_details': roll_result, 'db_error': 'Error saving action to log.'}), 500
    
    return jsonify({'message': message, 'roll_details': roll_result})

@bp.route('/adventure/<int:character_id>/roll_initiative', methods=['POST'])
@login_required
def roll_initiative(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        modifier = character.get_modifier_for_ability('dexterity')
        roll_result = roll_dice(sides=20, num_dice=1, modifier=modifier)
        roll_result['skill_name'] = "Initiative" # For display in log
        return _log_and_respond(character, roll_result, "{name} rolls Initiative: {total} ({desc})", "Initiative")
    except Exception as e:
        current_app.logger.error(f"Error in roll_initiative: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@bp.route('/adventure/<int:character_id>/roll_ability_check/<string:ability_name>', methods=['POST'])
@login_required
def roll_ability_check(character_id, ability_name):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    if ability_name not in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
        return jsonify({'error': 'Invalid ability name'}), 400
    try:
        modifier = character.get_modifier_for_ability(ability_name)
        roll_result = roll_dice(sides=20, num_dice=1, modifier=modifier)
        roll_result['skill_name'] = f"{ability_name.capitalize()} Check"
        return _log_and_respond(character, roll_result, "{name} makes a {action}: {total} ({desc})", f"{ability_name.capitalize()} Check")
    except Exception as e:
        current_app.logger.error(f"Error in roll_ability_check for {ability_name}: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@bp.route('/adventure/<int:character_id>/roll_saving_throw/<string:ability_name>', methods=['POST'])
@login_required
def roll_saving_throw(character_id, ability_name):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    if ability_name not in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
        return jsonify({'error': 'Invalid ability name for saving throw'}), 400
    try:
        modifier = character.get_saving_throw_bonus(ability_name)
        roll_result = roll_dice(sides=20, num_dice=1, modifier=modifier)
        roll_result['skill_name'] = f"{ability_name.capitalize()} Save"
        return _log_and_respond(character, roll_result, "{name} makes a {action}: {total} ({desc})", f"{ability_name.capitalize()} Save")
    except Exception as e:
        current_app.logger.error(f"Error in roll_saving_throw for {ability_name}: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@bp.route('/adventure/<int:character_id>/roll_skill_check/<string:skill_name_api>/<string:ability_name_api>', methods=['POST'])
@login_required
def roll_skill_check_specific(character_id, skill_name_api, ability_name_api): # Renamed to avoid conflict
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    # skill_name_api is the attribute name, e.g., 'athletics', 'stealth'
    # ability_name_api is for reference, actual modifier comes from get_skill_bonus
    skill_display_name = skill_name_api.replace('_', ' ').capitalize()
    try:
        # The get_skill_bonus method in the model uses the skill_name_api (e.g. 'athletics')
        modifier = character.get_skill_bonus(skill_name_api)
        roll_result = roll_dice(sides=20, num_dice=1, modifier=modifier)
        roll_result['skill_name'] = skill_display_name
        return _log_and_respond(character, roll_result, "{name} attempts a {action} check: {total} ({desc})", skill_display_name)
    except ValueError: # Handles unknown skill_name_api if get_skill_bonus raises it
        return jsonify({'error': f"Invalid skill: {skill_display_name}"}), 400
    except Exception as e:
        current_app.logger.error(f"Error in roll_skill_check for {skill_display_name}: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@bp.route('/adventure/<int:character_id>/roll_attack', methods=['POST'])
@login_required
def roll_attack_generic(character_id): # Renamed to avoid conflict if any
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        # Defaulting to Strength + Proficiency. Future: allow weapon choice / finesse.
        modifier = character.get_modifier_for_ability('strength') + character.get_proficiency_bonus()
        roll_result = roll_dice(sides=20, num_dice=1, modifier=modifier)
        roll_result['skill_name'] = "Attack"
        return _log_and_respond(character, roll_result, "{name} attacks! Roll: {total} ({desc})", "Attack")
    except Exception as e:
        current_app.logger.error(f"Error in roll_attack: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@bp.route('/adventure/<int:character_id>/roll_damage', methods=['POST'])
@login_required
def roll_damage_generic(character_id): # Renamed to avoid conflict
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON payload for damage roll'}), 400

    num_dice = data.get('num_dice')
    dice_type = data.get('dice_type')
    modifier_stat = data.get('modifier_stat') # e.g., "strength", "dexterity", or "none"/"null"

    if not isinstance(num_dice, int) or not isinstance(dice_type, int) or num_dice <= 0 or dice_type <= 0:
        return jsonify({'error': 'num_dice and dice_type must be positive integers.'}), 400

    try:
        damage_modifier = 0
        if modifier_stat and modifier_stat.lower() != 'none' and modifier_stat.lower() != 'null':
            if modifier_stat not in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
                 return jsonify({'error': f"Invalid modifier_stat: {modifier_stat}"}), 400
            damage_modifier = character.get_modifier_for_ability(modifier_stat)
        
        roll_result = roll_dice(sides=dice_type, num_dice=num_dice, modifier=damage_modifier)
        roll_result['skill_name'] = "Damage"
        return _log_and_respond(character, roll_result, "{name} deals damage! Roll: {total} ({desc})", "Damage")
    except ValueError as e: # Catch errors from roll_dice
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error in roll_damage: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500
