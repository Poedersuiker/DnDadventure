from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, session # Added session
from flask_login import login_required, current_user
from app.extensions import db
from app.character import bp
from app.character.forms import (
    RaceSelectionForm, ClassSelectionForm, # Removed CharacterCreationForm
    AbilityScoreAssignmentForm, BackgroundAlignmentForm, SkillsProficienciesForm,
    EquipmentForm, SpellSelectionForm, ALL_SKILLS, CharacterNameForm
)
from app.models import Character, CLASS_DATA_MODEL # Added CLASS_DATA_MODEL
from app.utils.dice_roller import roll_ability_scores
from app.character.spell_data import SPELL_DATA, CLASS_SPELLCASTING_INFO # Added spell_data imports
# CLASS_DATA is already imported from .routes (or should be available in the same file)
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

@bp.route('/create_character', methods=['GET', 'POST']) # Keeping methods for now
@login_required
def create_character(): # This is the old function
    # All old logic removed
    # redirect and url_for are already imported from flask at the top of the file.
    return redirect(url_for('character.create_character_wizard')) # Redirect to step 1 of the new wizard

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
                           xp_for_next_level=xp_for_next_level,
                           getattr=getattr) # Add getattr to context

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

# --- Character Creation Wizard Routes ---
WIZARD_TOTAL_STEPS = 9 # Step 9 is Review & Save.


STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
ABILITY_SCORE_KEYS = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']

@bp.route('/create_wizard/', defaults={'step': 1}, methods=['GET', 'POST'])
@bp.route('/create_wizard/<int:step>', methods=['GET', 'POST'])
@login_required
def create_character_wizard(step):
    character_data = session.get('character_creation_data', {})
    current_form = None

    if step == 1: # Name
        current_form = CharacterNameForm(request.form if request.method == 'POST' else None)
        if request.method == 'GET' and character_data.get('name'):
            current_form.character_name.data = character_data['name']
    elif step == 2: # Race
        current_form = RaceSelectionForm(request.form if request.method == 'POST' else None)
        if request.method == 'GET' and character_data.get('race'):
            current_form.race.data = character_data['race']
    elif step == 3: # Class
        current_form = ClassSelectionForm(request.form if request.method == 'POST' else None)
        if request.method == 'GET' and character_data.get('character_class'):
            current_form.character_class.data = character_data['character_class']
    elif step == 4: # Abilities
        current_form = AbilityScoreAssignmentForm(request.form if request.method == 'POST' and request.form.get('action') == 'assign_scores' else None)
        if request.method == 'GET':
            # Pre-populate form if data exists from a previous attempt or a generation method was just used
            for ability_key in ABILITY_SCORE_KEYS:
                if character_data.get(ability_key) and hasattr(current_form, ability_key) and getattr(current_form, ability_key).data is None: # Check if form field is not already set by POST data
                    getattr(current_form, ability_key).data = character_data[ability_key]
    elif step == 5: # Background & Alignment
        current_form = BackgroundAlignmentForm(request.form if request.method == 'POST' else None)
        if request.method == 'GET':
            if character_data.get('alignment'):
                current_form.alignment.data = character_data['alignment']
            if character_data.get('background'):
                current_form.background.data = character_data['background']
    elif step == 6: # Skills & Proficiencies
        char_class_name = character_data.get('character_class', 'Default') # Default if not found
        class_info = CLASS_DATA.get(char_class_name, CLASS_DATA["Default"])
        current_form = SkillsProficienciesForm(request.form if request.method == 'POST' else None)
        
        if request.method == 'GET':
            for skill_key, _ in ALL_SKILLS: # ALL_SKILLS has 'prof_skillname' as key
                if hasattr(current_form, skill_key) and character_data.get(skill_key):
                    getattr(current_form, skill_key).data = character_data[skill_key]
        
        # Pass class_info and ALL_SKILLS to template context for GET and POST (if validation fails)
        template_context_extra = {'class_info': class_info, 'ALL_SKILLS_FOR_TEMPLATE': ALL_SKILLS}
    elif step == 7: # Equipment
        current_form = EquipmentForm(request.form if request.method == 'POST' else None)
        if request.method == 'GET' and character_data.get('inventory'):
            current_form.inventory.data = character_data['inventory']
    elif step == 8: # Spells
        char_class = character_data.get('character_class')
        selection_key = f"{char_class}_selection"

        if not char_class or char_class not in SPELL_DATA or selection_key not in CLASS_SPELLCASTING_INFO:
            # Skip this step if not a spellcaster defined in SPELL_DATA/CLASS_SPELLCASTING_INFO
            # Or, if they are a spellcaster but have no selections to make at L1 via this UI
            flash(f"{char_class} does not select spells at 1st level via this simplified step, or is not yet configured. Skipping to next step.", "info")
            session['character_creation_data'] = character_data # Save any prior step data
            return redirect(url_for('character.create_character_wizard', step=9))

        selection_rules = CLASS_SPELLCASTING_INFO[selection_key]
        
        available_cantrips = SPELL_DATA[char_class].get('cantrips', [])
        available_level1_spells = SPELL_DATA[char_class].get('level1', [])

        cantrip_choices = [(spell['name'], f"{spell['name']}") for spell in available_cantrips]
        level1_spell_choices = [(spell['name'], f"{spell['name']}") for spell in available_level1_spells]
        
        form_kwargs = {'cantrip_choices': cantrip_choices, 'level1_spell_choices': level1_spell_choices}
        if request.method == 'POST':
            current_form = SpellSelectionForm(request.form, **form_kwargs)
        else: # GET
            current_form = SpellSelectionForm(**form_kwargs)
            # Pre-populate from session
            # spells_known_list is a list of spell names.
            spells_known_list = character_data.get('spells_known_list', [])
            if spells_known_list:
                current_form.selected_cantrips.data = [spell for spell in spells_known_list if spell in dict(cantrip_choices)]
                current_form.selected_level1_spells.data = [spell for spell in spells_known_list if spell in dict(level1_spell_choices)]
        
        template_context_extra = {
            'selection_rules': selection_rules,
            'spell_data_for_class': SPELL_DATA[char_class] 
        }
    elif step == 9: # Review Step
        # Calculate ability modifiers for display
        ability_modifiers = {
            stat: (character_data.get(stat, 10) - 10) // 2
            for stat in ABILITY_SCORE_KEYS 
        }
        # Ensure skills are presented nicely if they are just prof_skillname: True
        skills_list_for_review = [
            skill_display for skill_key, skill_display in ALL_SKILLS 
            if character_data.get(skill_key)
        ]

        character_data_for_review = {
            **character_data, 
            'ability_modifiers': ability_modifiers,
            'skills_list_for_review': skills_list_for_review
        }
        template_context_extra = {'character_data_for_review': character_data_for_review}
        # No form specific to step 9 for GET
        current_form = None


    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'previous_step':
            if step > 1:
                prev_step = step - 1
                return redirect(url_for('character.create_character_wizard', step=prev_step))
        
        elif step == 4 and action == 'roll':
            character_data['available_scores'] = roll_ability_scores()
            character_data['generation_method'] = 'roll'
            for key in ABILITY_SCORE_KEYS: character_data.pop(key, None) # Clear previous assignments
            session['character_creation_data'] = character_data
            return redirect(url_for('character.create_character_wizard', step=4))

        elif step == 4 and action == 'use_standard_array':
            character_data['available_scores'] = STANDARD_ARRAY[:]
            character_data['generation_method'] = 'standard_array'
            for key in ABILITY_SCORE_KEYS: character_data.pop(key, None) # Clear previous assignments
            session['character_creation_data'] = character_data
            return redirect(url_for('character.create_character_wizard', step=4))

        # Default 'next_step' or specific 'assign_scores' for step 4
        elif action == 'next_step' or (step == 4 and action == 'assign_scores'):
            valid_step = True
            if step == 1: # Process Name
                # current_form is CharacterNameForm, already instantiated with request.form for POST at the top of create_character_wizard
                if current_form and current_form.validate(): # Changed validate_on_submit() to validate()
                    character_data['name'] = current_form.character_name.data
                else:
                    valid_step = False # Errors will be displayed by the form rendering
            elif step == 2: # Process Race
                if current_form and current_form.validate(): # current_form is RaceSelectionForm
                    character_data['race'] = current_form.race.data
                else:
                    valid_step = False
            elif step == 3: # Process Class
                if current_form and current_form.validate(): # current_form is ClassSelectionForm
                    character_data['character_class'] = current_form.character_class.data
                else:
                    valid_step = False
            elif step == 4: # Process Ability Score Assignment
                # current_form is AbilityScoreAssignmentForm, already instantiated with request.form at the top for step 4 POST
                if current_form and current_form.validate(): # Validates individual field rules (e.g. NumberRange)
                    available_scores = character_data.get('available_scores')
                    if not available_scores:
                        flash("Please generate scores (roll or standard array) first before assigning.", "error")
                        valid_step = False
                    else:
                        assigned_scores_values = sorted([
                            current_form.strength.data, current_form.dexterity.data,
                            current_form.constitution.data, current_form.intelligence.data,
                            current_form.wisdom.data, current_form.charisma.data
                        ])

                        if sorted(available_scores) != assigned_scores_values:
                            flash("The scores you assigned do not match the available scores. Please use the scores from the 'Available Scores' list without modification, assigning each one exactly once.", "error")
                            valid_step = False
                            # current_form already contains user's invalid input
                        else:
                            # Scores are valid and match the permutation
                            for ability_key in ABILITY_SCORE_KEYS:
                                character_data[ability_key] = getattr(current_form, ability_key).data
                else:
                    # Form field validation (e.g., NumberRange) failed for step 4
                    valid_step = False
            elif step == 5: # Process Background & Alignment
                if current_form and current_form.validate(): # current_form is BackgroundAlignmentForm
                    character_data['alignment'] = current_form.alignment.data
                    character_data['background'] = current_form.background.data
                else:
                    valid_step = False
            elif step == 6: # Process Skills & Proficiencies
                if current_form and current_form.validate(): # Basic WTForms validation
                    char_class_name_post = character_data.get('character_class', 'Default')
                    class_info_post = CLASS_DATA.get(char_class_name_post, CLASS_DATA["Default"])
                    
                    selected_skill_keys = []
                    for skill_key_form, _ in ALL_SKILLS: # e.g. skill_key_form is 'prof_athletics'
                        if hasattr(current_form, skill_key_form) and getattr(current_form, skill_key_form).data:
                            selected_skill_keys.append(skill_key_form)
                    
                    num_selected_skills = len(selected_skill_keys)
                    required_skill_count = class_info_post['skills_count']
                    allowed_skill_options_raw = class_info_post['skills_options'] # This is list of 'skill_name' not 'prof_skill_name'

                    # Convert allowed_skill_options to 'prof_skill_name' format for comparison
                    allowed_skill_options = [f"prof_{opt}" for opt in allowed_skill_options_raw]


                    custom_validation_passed = True
                    if num_selected_skills != required_skill_count:
                        flash(f"Please select exactly {required_skill_count} skills for the {char_class_name_post} class. You selected {num_selected_skills}.", "error")
                        custom_validation_passed = False
                    
                    if class_info_post['skills_options'] != "any": # If not "any", check if selected are allowed
                        for selected_key in selected_skill_keys:
                            if selected_key not in allowed_skill_options:
                                skill_display_name = dict(ALL_SKILLS).get(selected_key, selected_key.replace("prof_", "").replace("_", " ").title())
                                flash(f"Skill '{skill_display_name}' is not an allowed option for the {char_class_name_post} class.", "error")
                                custom_validation_passed = False
                                break # No need to check further if one invalid skill is found
                    
                    if custom_validation_passed:
                        for skill_key_session, _ in ALL_SKILLS:
                            character_data[skill_key_session] = getattr(current_form, skill_key_session).data
                    else:
                        valid_step = False # Custom validation failed
                else:
                    # WTForms validation failed (e.g. CSRF, or if other validators were added to BooleanFields)
                    valid_step = False
            elif step == 7: # Process Equipment
                if current_form and current_form.validate(): # current_form is EquipmentForm
                    character_data['inventory'] = current_form.inventory.data
                else:
                    valid_step = False # WTForms validation failed (e.g. Length)
            elif step == 8: # Process Spells
                # current_form is SpellSelectionForm, already instantiated with choices
                if current_form and current_form.validate_on_submit(): # validate_on_submit for POST specific validation
                    # Re-fetch selection_rules for POST context
                    char_class_post = character_data.get('character_class')
                    selection_key_post = f"{char_class_post}_selection"
                    # selection_rules_post = CLASS_SPELLCASTING_INFO.get(selection_key_post)
                    # The selection_rules should be the same as in GET, already fetched.
                    # selection_rules variable from GET part of step 8 should be accessible if structured well,
                    # but better to re-fetch or ensure it's passed if route logic is complex.
                    # For now, assume 'selection_rules' from GET scope is available or re-fetch:
                    selection_rules_post = CLASS_SPELLCASTING_INFO.get(selection_key_post)


                    if not selection_rules_post: # Should not happen if GET guard worked
                        flash("Error processing spells: class spell selection rules not found.", "error")
                        valid_step = False
                    else:
                        num_selected_cantrips = len(current_form.selected_cantrips.data)
                        num_selected_level1 = len(current_form.selected_level1_spells.data)

                        required_cantrips = selection_rules_post.get('cantrips_to_select', 0)
                        required_level1 = selection_rules_post.get('level1_to_select', 0)
                        
                        custom_spell_validation_passed = True
                        if num_selected_cantrips != required_cantrips:
                            flash(f"Please select exactly {required_cantrips} cantrips. You selected {num_selected_cantrips}.", "error")
                            custom_spell_validation_passed = False
                        
                        if num_selected_level1 != required_level1:
                            flash(f"Please select exactly {required_level1} 1st-level spells. You selected {num_selected_level1}.", "error")
                            custom_spell_validation_passed = False
                        
                        if custom_spell_validation_passed:
                            combined_spells = current_form.selected_cantrips.data + current_form.selected_level1_spells.data
                            character_data['spells_known_list'] = combined_spells
                            character_data['spells_known'] = ", ".join(combined_spells)
                        else:
                            valid_step = False
                else:
                    # WTForms validation failed (e.g. CSRF) or it's not a POST for this form type.
                    # If current_form is None here for step 8, it means it wasn't a POST for spell selection.
                    # This path might be taken if action was 'previous_step' and current_form was not set for step 8.
                    # The general 'valid_step = True' at start of 'next_step' action handles this.
                    if not current_form: # Should not happen if action is 'next_step' for a form-based step
                         flash("An unexpected error occurred with the form for this step.","error")
                    valid_step = False 
            elif step == 9: # Finalize and Save Character (triggered by 'Next Step' on step 9)
                # Data validation
                required_fields = ['name', 'race', 'character_class', 'strength', 'dexterity', 
                                   'constitution', 'intelligence', 'wisdom', 'charisma',
                                   'alignment', 'background'] # Add more if they become mandatory
                missing_fields = [field for field in required_fields if not character_data.get(field)]
                if missing_fields:
                    flash(f"Missing essential character information: {', '.join(missing_fields)}. Please go back and complete all steps.", "error")
                    # Redirect to first step or the step where the first missing field is
                    return redirect(url_for('character.create_character_wizard', step=1))

                # Create Character instance
                new_character = Character(
                    name=character_data['name'],
                    race=character_data['race'],
                    character_class=character_data['character_class'],
                    level=1, # Start at level 1
                    strength=character_data['strength'],
                    dexterity=character_data['dexterity'],
                    constitution=character_data['constitution'],
                    intelligence=character_data['intelligence'],
                    wisdom=character_data['wisdom'],
                    charisma=character_data['charisma'],
                    alignment=character_data.get('alignment'),
                    background=character_data.get('background'),
                    inventory=character_data.get('inventory'),
                    spells_known=character_data.get('spells_known'), # This is the comma-separated string
                    owner=current_user
                )

                # Skill Proficiencies
                for skill_key, _ in ALL_SKILLS:
                    if character_data.get(skill_key, False):
                        setattr(new_character, skill_key, True)
                
                # HP and Hit Dice (using CLASS_DATA_MODEL from app.models)
                char_class_model_key = new_character.character_class
                class_model_info = CLASS_DATA_MODEL.get(char_class_model_key, CLASS_DATA_MODEL["Default"])
                
                con_modifier = new_character.get_modifier_for_ability('constitution')
                new_character.max_hp = class_model_info["hit_dice_type"] + con_modifier
                new_character.current_hp = new_character.max_hp
                new_character.hit_dice_type = class_model_info["hit_dice_type"]
                new_character.hit_dice_max = 1 # Level 1
                new_character.hit_dice_current = 1 # Level 1

                # Saving Throws (using CLASS_DATA from this file for save proficiency keys)
                class_info_for_saves = CLASS_DATA.get(new_character.character_class, CLASS_DATA["Default"])
                for ability_save_key in class_info_for_saves.get("saves", []): # e.g. "strength"
                    setattr(new_character, f"prof_{ability_save_key}_save", True)

                try:
                    db.session.add(new_character)
                    db.session.commit()
                    session.pop('character_creation_data', None) # Clear session data
                    flash(f"Character '{new_character.name}' created successfully!", "success")
                    return redirect(url_for('character.select_character'))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error saving new character: {e}")
                    flash("An error occurred while saving your character. Please try again.", "error")
                    valid_step = False # Stay on step 9 to show the error

            if valid_step:
                session['character_creation_data'] = character_data
                if step < WIZARD_TOTAL_STEPS: # Check against WIZARD_TOTAL_STEPS for general next step
                    next_step = step + 1
                    return redirect(url_for('character.create_character_wizard', step=next_step))
                # If step == WIZARD_TOTAL_STEPS, it means the last step's POST was handled above (like step 9)
                # or it's an undefined step, so it will fall through to render.
        
    # GET request or POST that failed validation (valid_step = False or last step was not a saving POST)
    template_context = {
        'current_step': step,
        'total_steps': WIZARD_TOTAL_STEPS, # WIZARD_TOTAL_STEPS should be 9 if step 9 is the final review and save.
        'character_data': character_data,
        'title': f"Create Character - Step {step}"
    }
    if current_form: # This will be AbilityScoreAssignmentForm if step 4 fails validation on assign_scores
        template_context['form'] = current_form

    return render_template('character/create_character_wizard.html', **template_context)


@bp.route('/create_wizard/clear_session')
@login_required
def clear_character_creation_session():
    if 'character_creation_data' in session:
        session.pop('character_creation_data')
        flash('Character creation progress has been cleared.', 'info')
    return redirect(url_for('character.create_character_wizard', step=1))
