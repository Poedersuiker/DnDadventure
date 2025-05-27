import json
import os
# import google.generativeai as genai # Removed
import google.generativeai as genai # Re-add import
import re # Added for gold parsing
from flask import render_template, redirect, url_for, flash, request, session, get_flashed_messages, jsonify, current_app
from flask_babel import _
from flask_login import login_required, current_user
from app import db
from app.models import User, Character, Race, Class, Spell, Setting, Item, Coinage
from app.utils import roll_dice, parse_coinage # Changed import to parse_coinage
from app.gemini import geminiai, GEMINI_DM_SYSTEM_RULES
from app.main import bp

# Placeholder for Gemini API Key Configuration
# GEMINI_API_KEY = "YOUR_API_KEY" # Load this from environment variables in a real app
# genai.configure(api_key=GEMINI_API_KEY)

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    characters = Character.query.filter_by(user_id=current_user.id).all()
    return render_template('main.html', characters=characters)

@bp.route('/login_page')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('login.html')

@bp.route('/create_character', methods=['GET']) # Only GET needed now for redirect
@login_required
def create_character():
    # Redirect to the first step of the new character creation flow
    return redirect(url_for('main.creation_race'))

@bp.route('/delete_character/<int:character_id>', methods=['POST'])
@login_required
def delete_character(character_id):
    character = Character.query.get_or_404(character_id) # Use get_or_404 for convenience
    
    if character.user_id != current_user.id:
        flash('You do not have permission to delete this character.', 'error')
        # Or abort(403)
        return redirect(url_for('main.index'))
        
    db.session.delete(character)
    db.session.commit()
    flash('Character deleted successfully.', 'success')
    return redirect(url_for('main.index'))

@bp.route('/clear_character_progress/<int:character_id>', methods=['POST'])
@login_required
def clear_character_progress(character_id):
    character = Character.query.get_or_404(character_id)

    if character.user_id != current_user.id:
        flash('You do not have permission to modify this character.', 'error')
        return redirect(url_for('main.index'))

    # Reset adventure log and level
    character.adventure_log = json.dumps([])
    character.level = 1

    # Recalculate HP for Level 1
    if character.constitution and character.char_class and character.char_class.hit_die:
        con_score = character.constitution
        con_modifier = (con_score - 10) // 2
        try:
            hit_die_value = int(character.char_class.hit_die[1:]) # Assumes format like "d8"
        except (ValueError, TypeError, IndexError):
            current_app.logger.error(f"Could not parse hit_die '{character.char_class.hit_die}' for class {character.char_class.name}. Defaulting to 8 for HP calculation.")
            hit_die_value = 8 # Default to a d8 if parsing fails
        
        character.max_hp = hit_die_value + con_modifier
        character.hp = character.max_hp
    else:
        # Fallback or error if essential data is missing
        current_app.logger.warning(f"Could not recalculate HP for character {character.id} due to missing CON or class/hit_die info. HP set to a default or remains unchanged if that's safer.")
        # Consider setting a default HP, e.g., based on average if CON/hit_die is missing
        # For now, if this data is missing, HP calculation is skipped. User might need to edit character.

    # Reset Armor Class to base (10 + DEX modifier)
    if character.dexterity is not None: # Ensure dexterity is not None
        dex_score = character.dexterity
        dex_modifier = (dex_score - 10) // 2
        character.armor_class = 10 + dex_modifier
    else:
        current_app.logger.warning(f"Could not recalculate AC for character {character.id} due to missing Dexterity. AC remains unchanged or could be set to a default.")
        # character.armor_class = 10 # Default if DEX is missing

    # Clear spells (Chosen Simplification)
    character.known_spells = []
    character.prepared_spells = []
    
    # current_equipment and current_proficiencies are assumed to be the L1 state as per creation_review logic.

    # Clear items and coinage
    Item.query.filter_by(character_id=character.id).delete()
    Coinage.query.filter_by(character_id=character.id).delete()
    # Note: Re-adding L1 equipment/coinage is deferred for simplicity in this step.

    db.session.commit()
    flash('Adventure progress cleared. Your character has been reset to level 1. Inventory and coinage have been cleared.', 'success')
    return redirect(url_for('main.index'))

# Character Creation Step 1: Race Selection
@bp.route('/creation/race', methods=['GET', 'POST'])
@login_required
def creation_race():
    if request.method == 'GET':
        # Initialize or reset character data in session
        session['new_character_data'] = {}
        races = Race.query.all()
        if not races:
            flash('No races found in the database. Please run the population script.', 'error')
            # Potentially redirect to index or an admin page if desired
            return render_template('create_character_race.html', races=[])
        return render_template('create_character_race.html', races=races)

    # POST request
    race_id = request.form.get('race_id')
    selected_race = None
    if race_id:
        try:
            selected_race = Race.query.get(int(race_id))
        except ValueError:
            flash('Invalid Race ID format.', 'error')
            races = Race.query.all()
            return render_template('create_character_race.html', races=races)

    if selected_race:
        session['new_character_data']['race_id'] = selected_race.id
        session['new_character_data']['race_name'] = selected_race.name
        session.modified = True # Ensure session is saved if nested dicts are modified directly
        flash(f'{selected_race.name} selected!', 'success')
        return redirect(url_for('main.creation_class')) # Next step
    else:
        flash('Please select a valid race.', 'error')
        races = Race.query.all()
        return render_template('create_character_race.html', races=races)

# Character Creation Step 2: Class Selection
@bp.route('/creation/class', methods=['GET', 'POST'])
@login_required
def creation_class():
    char_data = session.get('new_character_data', {})
    if not char_data.get('race_id'):
        flash('Please select a race first.', 'error')
        return redirect(url_for('main.creation_race'))

    if request.method == 'GET':
        classes = Class.query.all()
        if not classes:
            flash('No classes found in the database. Please run the population script.', 'error')
            return render_template('create_character_class.html', classes=[], race_name=char_data.get('race_name'))
        return render_template('create_character_class.html', classes=classes, race_name=char_data.get('race_name'))

    # POST request
    class_id = request.form.get('class_id')
    selected_class = None
    if class_id:
        try:
            selected_class = Class.query.get(int(class_id))
        except ValueError:
            flash('Invalid Class ID format.', 'error')
            classes = Class.query.all()
            return render_template('create_character_class.html', classes=classes, race_name=char_data.get('race_name'))

    if selected_class:
        session['new_character_data']['class_id'] = selected_class.id
        session['new_character_data']['class_name'] = selected_class.name
        session.modified = True # Ensure session is saved
        flash(f'{selected_class.name} selected!', 'success')
        return redirect(url_for('main.creation_stats')) # Next step: stats
    else:
        flash('Please select a valid class.', 'error')
        classes = Class.query.all()
        return render_template('create_character_class.html', classes=classes, race_name=char_data.get('race_name'))

# Character Creation Step 3: Ability Scores
@bp.route('/creation/stats', methods=['GET', 'POST'])
@login_required
def creation_stats():
    char_data = session.get('new_character_data', {})
    if not char_data.get('race_id'):
        flash('Please select a race first.', 'error')
        return redirect(url_for('main.creation_race'))
    if not char_data.get('class_id'):
        flash('Please select a class first.', 'error')
        return redirect(url_for('main.creation_class'))

    selected_race = Race.query.get(char_data['race_id'])
    selected_class = Class.query.get(char_data['class_id'])

    if not selected_race or not selected_class:
        flash('Selected race or class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None) # Clear corrupted data
        return redirect(url_for('main.creation_race'))

    racial_bonuses_list = json.loads(selected_race.ability_score_increases or '[]')
    primary_ability = selected_class.spellcasting_ability or "Refer to class features"
    standard_array = [15, 14, 13, 12, 10, 8]
    
    # Convert list of dicts to a simple dict for easier lookup in template/logic
    racial_bonuses_dict = {bonus['name']: bonus['bonus'] for bonus in racial_bonuses_list}
    rolled_stats_from_session = session.get('rolled_stats')


    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'roll_stats':
            rolled_scores = [roll_dice(4, 6, 1)[0] for _ in range(6)]
            session['rolled_stats'] = rolled_scores
            session.modified = True
            # Re-render the template with the rolled scores
            return render_template('create_character_stats.html',
                                   race_name=selected_race.name,
                                   class_name=selected_class.name,
                                   racial_bonuses_dict=racial_bonuses_dict,
                                   primary_ability=primary_ability,
                                   standard_array=standard_array,
                                   rolled_stats=rolled_scores,
                                   submitted_scores=request.form) # Keep any already submitted scores

        # Logic for submitting final stats (action is not 'roll_stats')
        base_scores = {}
        errors = False
        # Map form field names to 3-letter score keys
        ability_map = {
            'strength': 'STR', 'dexterity': 'DEX', 'constitution': 'CON',
            'intelligence': 'INT', 'wisdom': 'WIS', 'charisma': 'CHA'
        }
        
        form_scores_to_repopulate = {} # For re-rendering in case of error

        for form_name, score_key in ability_map.items():
            score_val_str = request.form.get(form_name)
            form_scores_to_repopulate[form_name] = score_val_str # Store original string for repopulation

            if not score_val_str:
                flash(f'{form_name.capitalize()} score is required.', 'error')
                errors = True
                continue
            try:
                score = int(score_val_str)
                if not (3 <= score <= 18): # Basic validation for manually entered base scores
                    flash(f'{form_name.capitalize()} score must be between 3 and 18 before racial modifiers.', 'error')
                    errors = True
                base_scores[score_key] = score # Use 'STR', 'DEX', 'CON', etc.
            except ValueError:
                flash(f'Invalid score for {form_name.capitalize()}. Must be a number.', 'error')
                errors = True
        
        if errors:
            # Pass back the original string values for repopulation
            # Also need all other context for rendering the template
            return render_template('create_character_stats.html',
                                   race_name=selected_race.name, 
                                   class_name=selected_class.name, 
                                   racial_bonuses_dict=racial_bonuses_dict, 
                                   primary_ability=primary_ability, 
                                   standard_array=standard_array, 
                                   rolled_stats=session.get('rolled_stats'), 
                                   submitted_scores=form_scores_to_repopulate)


        final_scores = base_scores.copy()
        # racial_bonuses_list is already defined from the GET part of the route
        # selected_race is also defined
        
        # Re-fetch racial_bonuses_list just to be absolutely sure, though it should be available
        # from the top of the function. This is defensive.
        # racial_bonuses_list = json.loads(selected_race.ability_score_increases or '[]')

        for bonus_item in racial_bonuses_list: # racial_bonuses_list was defined near the start of the function
            ability_key = bonus_item.get('name') # This is 'STR', 'DEX', etc.
            bonus_value = bonus_item.get('bonus', 0)
            if ability_key in final_scores: # Now keys 'STR', 'DEX' will match
                final_scores[ability_key] += bonus_value
            # No else needed, as all 6 keys ('STR'...'CHA') should be in final_scores.
        
        session['new_character_data']['ability_scores'] = final_scores
        session['new_character_data']['base_ability_scores'] = base_scores # Now also uses 'STR', 'DEX' keys
        session.modified = True
        session.pop('rolled_stats', None) # Clear rolled_stats after successful submission
        flash('Ability scores saved!', 'success')
        return redirect(url_for('main.creation_background')) # Next step

    # GET request
    return render_template('create_character_stats.html',
                           race_name=selected_race.name,
                           class_name=selected_class.name,
                           racial_bonuses_dict=racial_bonuses_dict, # Pass the dict
                           primary_ability=primary_ability,
                           standard_array=standard_array,
                           rolled_stats=rolled_stats_from_session, # Pass rolled_stats from session
                           submitted_scores=None) # No scores submitted yet for GET


# Sample backgrounds data (can be moved to a different file or DB later)
sample_backgrounds_data = {
    "Acolyte": {
        "name": "Acolyte",
        "skill_proficiencies": ["Insight", "Religion"],
        "tool_proficiencies": [], 
        "languages": ["Two of your choice"], 
        "equipment": "A holy symbol (a gift to you when you entered the priesthood), a prayer book or prayer wheel, 5 sticks of incense, vestments, a set of common clothes, and a pouch containing 15 gp."
    },
    "Criminal": {
        "name": "Criminal (Spy)",
        "skill_proficiencies": ["Deception", "Stealth"],
        "tool_proficiencies": ["One type of gaming set", "Thieves' tools"],
        "languages": [],
        "equipment": "A crowbar, a set of dark common clothes including a hood, and a pouch containing 15 gp."
    },
    "Sage": {
        "name": "Sage",
        "skill_proficiencies": ["Arcana", "History"],
        "tool_proficiencies": [], 
        "languages": ["Two of your choice"],
        "equipment": "A bottle of black ink, a quill, a small knife, a letter from a dead colleague posing a question you have not yet been able to answer, a set of common clothes, and a pouch containing 10 gp."
    },
    "Soldier": {
        "name": "Soldier",
        "skill_proficiencies": ["Athletics", "Intimidation"],
        "tool_proficiencies": ["One type of gaming set", "Vehicles (land)"],
        "languages": [],
        "equipment": "An insignia of rank, a trophy taken from a fallen enemy, a set of bone dice or deck of cards, a set of common clothes, and a pouch containing 10 gp."
    },
    "Entertainer": {
        "name": "Entertainer",
        "skill_proficiencies": ["Acrobatics", "Performance"],
        "tool_proficiencies": ["Disguise kit", "One type of musical instrument"],
        "languages": [],
        "equipment": "A musical instrument (one of your choice), the favor of an admirer (love letter, lock of hair, or trinket), a costume, and a pouch containing 15 gp."
    }
}

# Character Creation Step 4: Background
@bp.route('/creation/background', methods=['GET', 'POST'])
@login_required
def creation_background():
    char_data = session.get('new_character_data', {})
    if not char_data.get('ability_scores'):
        flash('Please determine ability scores first.', 'error')
        return redirect(url_for('main.creation_stats'))

    if request.method == 'POST':
        selected_bg_name = request.form.get('background_name')
        if selected_bg_name and selected_bg_name in sample_backgrounds_data:
            chosen_bg_data = sample_backgrounds_data[selected_bg_name]
            
            session['new_character_data']['background_name'] = chosen_bg_data['name']
            session['new_character_data']['background_skill_proficiencies'] = chosen_bg_data['skill_proficiencies']
            session['new_character_data']['background_tool_proficiencies'] = chosen_bg_data['tool_proficiencies']
            session['new_character_data']['background_languages'] = chosen_bg_data['languages']
            session['new_character_data']['background_equipment'] = chosen_bg_data['equipment']
            session.modified = True # Ensure session is saved if nested dicts are modified directly

            flash(f"Background '{chosen_bg_data['name']}' selected.", 'success')
            return redirect(url_for('main.creation_skills')) # Next step: class skills
        else:
            flash('Please select a valid background.', 'error')
            # Re-render with existing data
            return render_template('create_character_background.html',
                                   race_name=char_data.get('race_name'),
                                   class_name=char_data.get('class_name'),
                                   backgrounds=sample_backgrounds_data)
    
    # GET request
    return render_template('create_character_background.html',
                           race_name=char_data.get('race_name'),
                           class_name=char_data.get('class_name'),
                           backgrounds=sample_backgrounds_data)


# Character Creation Step 5: Class Skills & Proficiencies
@bp.route('/creation/skills', methods=['GET', 'POST'])
@login_required
def creation_skills():
    char_data = session.get('new_character_data', {})
    if not char_data.get('background_name'): # Check if previous step (background) was completed
        flash('Please choose your background first.', 'error')
        return redirect(url_for('main.creation_background'))

    selected_class = Class.query.get(char_data.get('class_id'))
    if not selected_class:
        flash('Selected class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    skill_options_from_class = json.loads(selected_class.skill_proficiencies_options or '[]')
    num_skills_to_choose = selected_class.skill_proficiencies_option_count
    saving_throw_proficiencies = json.loads(selected_class.proficiency_saving_throws or '[]')

    if request.method == 'POST':
        chosen_skills = request.form.getlist('chosen_skill')

        if len(chosen_skills) != num_skills_to_choose:
            flash(f'Please choose exactly {num_skills_to_choose} skill(s). You chose {len(chosen_skills)}.', 'error')
            # Re-render the page with user's previous selections
            return render_template('create_character_skills.html',
                                   race_name=char_data.get('race_name'),
                                   class_name=selected_class.name,
                                   background_name=char_data.get('background_name'),
                                   skill_options=skill_options_from_class,
                                   num_to_choose=num_skills_to_choose,
                                   saving_throws=saving_throw_proficiencies,
                                   submitted_skills=chosen_skills) # Pass back submitted skills

        session['new_character_data']['class_skill_proficiencies'] = chosen_skills
        session['new_character_data']['armor_proficiencies'] = json.loads(selected_class.proficiencies_armor or '[]')
        session['new_character_data']['weapon_proficiencies'] = json.loads(selected_class.proficiencies_weapons or '[]')
        session['new_character_data']['tool_proficiencies_class_fixed'] = json.loads(selected_class.proficiencies_tools or '[]')
        session['new_character_data']['saving_throw_proficiencies'] = saving_throw_proficiencies # Already a list from GET
        session.modified = True

        flash('Class skills and proficiencies saved!', 'success')
        return redirect(url_for('main.creation_hp')) # Next step: HP

    # GET request
    return render_template('create_character_skills.html',
                           race_name=char_data.get('race_name'),
                           class_name=selected_class.name,
                           background_name=char_data.get('background_name'),
                           skill_options=skill_options_from_class,
                           num_to_choose=num_skills_to_choose,
                           saving_throws=saving_throw_proficiencies,
                           submitted_skills=[]) # No skills submitted yet for GET


# Character Creation Step 6: HP & Combat Stats
@bp.route('/creation/hp', methods=['GET']) # GET only for now
@login_required
def creation_hp():
    char_data = session.get('new_character_data', {})
    # Check for a key from the previous step (skills/proficiencies)
    if not char_data.get('armor_proficiencies') and not char_data.get('class_skill_proficiencies'):
        flash('Please complete the skills and proficiencies step first.', 'error')
        return redirect(url_for('main.creation_skills'))

    # Ensure necessary data is in session
    required_keys = ['race_id', 'class_id', 'ability_scores']
    if not all(key in char_data for key in required_keys):
        flash('Missing critical data (race, class, or scores). Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    selected_race = Race.query.get(char_data['race_id'])
    selected_class = Class.query.get(char_data['class_id'])
    ability_scores = char_data.get('ability_scores', {}) # e.g., {'STR': 10, 'DEX': 12, ...}

    if not selected_race or not selected_class:
        flash('Selected race or class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))
    
    if not ability_scores.get('CON') or not ability_scores.get('DEX'):
        flash('Constitution or Dexterity scores not found. Please complete the stats step.', 'error')
        return redirect(url_for('main.creation_stats'))

    # Calculate CON modifier
    con_score = ability_scores.get('CON', 10) # Default to 10 if somehow missing, though previous check should catch
    con_modifier = (con_score - 10) // 2

    # Extract Hit Die value
    try:
        # Assumes hit_die is like "d8", "d10", "d12"
        hit_die_value = int(selected_class.hit_die[1:]) if selected_class.hit_die else 8 # Default to 8 if malformed
    except (ValueError, TypeError, IndexError):
        flash('Error parsing hit die for the class. Defaulting HP calculation.', 'warning')
        hit_die_value = 8 # Fallback

    # Calculate Max HP (Level 1)
    max_hp = hit_die_value + con_modifier

    # Calculate DEX modifier for AC
    dex_score = ability_scores.get('DEX', 10)
    dex_modifier = (dex_score - 10) // 2
    
    # Base Armor Class (before armor/shield)
    ac_base = 10 + dex_modifier
    
    # Speed
    speed = selected_race.speed

    # Store in session
    session['new_character_data']['max_hp'] = max_hp
    session['new_character_data']['current_hp'] = max_hp # Start with full HP
    session['new_character_data']['armor_class_base'] = ac_base
    session['new_character_data']['speed'] = speed
    session.modified = True

    return render_template('create_character_hp.html',
                           race_name=selected_race.name,
                           class_name=selected_class.name,
                           background_name=char_data.get('background_name', 'N/A'),
                           ability_scores_summary=ability_scores, # Pass the whole dict for summary
                           max_hp=max_hp,
                           ac_base=ac_base,
                           speed=speed)


def parse_starting_equipment(starting_equipment_data_json):
    """
    Parses the starting_equipment JSON string into fixed items and choice groups.
    The D&D API structure for starting_equipment is a list. Each item in the list
    can be either:
    1. A direct equipment grant: {"equipment": {"index": "shield", "name": "Shield", ...}, "quantity": 1}
    2. A choice object: {"choose": 1, "desc": "Choose one from...", "from": {"option_set_type": "options_array", "options": [
           {"option_type": "counted_reference", "count":1, "of": {"index": "dagger", ...}}, 
           {"option_type": "choice", "choice": {"desc": "Choose a simple weapon", "from": { "option_set_type": "equipment_category", "equipment_category": { "index": "simple-weapons"}} }}
           // and other complex structures
       ]}}
    This parser will simplify: it will look for direct grants and top-level choices where options are direct equipment.
    More complex nested choices (like choice of equipment category) are not fully expanded by this simple parser.
    """
    fixed_items = []
    choice_groups = []
    if not starting_equipment_data_json:
        return fixed_items, choice_groups
        
    starting_equipment_data = json.loads(starting_equipment_data_json)

    for i, item_or_choice in enumerate(starting_equipment_data):
        if 'equipment' in item_or_choice and 'quantity' in item_or_choice:
            # Direct equipment grant
            fixed_items.append(item_or_choice)
        elif 'choose' in item_or_choice and 'from' in item_or_choice:
            # This is a choice group
            options_list = []
            # The 'from' key can have different structures. We're looking for 'options' array.
            actual_options_source = item_or_choice['from'].get('options', [])
            
            for opt in actual_options_source:
                # Try to find the actual equipment item within the option
                # Option types can be "reference", "counted_reference", "choice" etc.
                if opt.get('option_type') == 'counted_reference' and 'of' in opt:
                    options_list.append({
                        "name": opt['of'].get('name', opt['of'].get('index', 'Unknown Item')),
                        "index": opt['of'].get('index', 'unknown-item-' + str(i)),
                        "quantity": opt.get('count', 1)
                    })
                elif opt.get('option_type') == 'reference' and 'item' in opt: # Common for single item references
                     options_list.append({
                        "name": opt['item'].get('name', opt['item'].get('index', 'Unknown Item')),
                        "index": opt['item'].get('index', 'unknown-item-' + str(i)),
                        "quantity": 1 # Default quantity for single reference
                    })
                # Add more conditions here if other option_type structures yield direct equipment
                # For this simplified version, we'll only grab options that directly point to an item's name/index.

            if options_list: # Only add choice group if we successfully parsed some options
                choice_groups.append({
                    "id": f"choice_{i}", # Unique ID for the form
                    "desc": item_or_choice.get('desc', f"Choose {item_or_choice['choose']}"),
                    "choose": item_or_choice['choose'],
                    "options": options_list
                })
        # Other structures in starting_equipment are ignored by this simple parser.
    return fixed_items, choice_groups


# Character Creation Step 7: Starting Equipment
@bp.route('/creation/equipment', methods=['GET', 'POST'])
@login_required
def creation_equipment():
    char_data = session.get('new_character_data', {})
    if not char_data.get('max_hp'): # Check for a key from the HP step
        flash('Please complete the HP & combat stats step first.', 'error')
        return redirect(url_for('main.creation_hp'))

    selected_class = Class.query.get(char_data.get('class_id'))
    if not selected_class:
        flash('Selected class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    class_starting_equipment_json = selected_class.starting_equipment or '[]'
    fixed_items, choice_groups = parse_starting_equipment(class_starting_equipment_json)
    
    background_equipment_string = char_data.get('background_equipment', '')

    if request.method == 'POST':
        chosen_equipment_list = []
        
        # Add fixed items
        for item_data in fixed_items:
            if item_data.get('equipment'):
                item_name = item_data['equipment'].get('name', item_data['equipment'].get('index', 'Unknown Fixed Item'))
                chosen_equipment_list.append(f"{item_name} (x{item_data.get('quantity', 1)})")

        # Process choices
        for group in choice_groups:
            group_id = group['id'] # e.g., "choice_0"
            # For 'choose: 1', expect a single value (radio button)
            if group['choose'] == 1:
                selected_option_index = request.form.get(group_id) # This is the equipment's index
                if selected_option_index:
                    # Find the selected option in the group to get its name and quantity
                    found_option = next((opt for opt in group['options'] if opt['index'] == selected_option_index), None)
                    if found_option:
                        chosen_equipment_list.append(f"{found_option['name']} (x{found_option.get('quantity',1)})")
            # For 'choose > 1', expect a list of values (checkboxes) - NOT fully implemented as per subtask focus on radio for now
            # else: 
            #     selected_options_indices = request.form.getlist(group_id) # This would be for checkboxes
            #     for selected_idx in selected_options_indices:
            #         found_option = next((opt for opt in group['options'] if opt['index'] == selected_idx), None)
            #         if found_option:
            #             chosen_equipment_list.append(f"{found_option['name']} (x{found_option.get('quantity',1)})")


        # Combine with background equipment (already a string)
        # A more robust approach would be to parse the background string into items too.
        # For now, just appending the string.
        if background_equipment_string:
            chosen_equipment_list.append(f"Background: {background_equipment_string}")

        session['new_character_data']['final_equipment'] = chosen_equipment_list
        session.modified = True

        flash('Starting equipment chosen!', 'success')

        if selected_class.spellcasting_ability:
            return redirect(url_for('main.creation_spells'))
        else:
            return redirect(url_for('main.creation_review'))

    # GET request
    return render_template('create_character_equipment.html',
                           race_name=char_data.get('race_name'),
                           class_name=selected_class.name,
                           background_name=char_data.get('background_name'),
                           fixed_items=fixed_items,
                           choice_groups=choice_groups,
                           background_equipment_string=background_equipment_string)


# Character Creation Step 8: Spell Selection (Conditional)
@bp.route('/creation/spells', methods=['GET', 'POST'])
@login_required
def creation_spells():
    char_data = session.get('new_character_data', {})
    if not char_data.get('final_equipment'): # Check for a key from the equipment step
        flash('Please complete the equipment step first.', 'error')
        return redirect(url_for('main.creation_equipment'))

    selected_class = Class.query.get(char_data.get('class_id'))
    if not selected_class:
        flash('Selected class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    if not selected_class.spellcasting_ability:
        # This class is not a spellcaster, skip to review
        return redirect(url_for('main.creation_review'))

    # Determine spell counts (Level 1 logic, simplified)
    num_cantrips_to_select = 0
    num_level_1_spells_to_select = 0
    class_name = selected_class.name

    # Simplified logic for spell counts based on class name
    if class_name == "Wizard":
        num_cantrips_to_select = 3
        num_level_1_spells_to_select = 6 # For spellbook
    elif class_name == "Sorcerer":
        num_cantrips_to_select = 4
        num_level_1_spells_to_select = 2 # Known spells
    elif class_name == "Bard":
        num_cantrips_to_select = 2
        num_level_1_spells_to_select = 4 # Known spells
    elif class_name == "Cleric":
        num_cantrips_to_select = 3
        # Clerics "know" all their spells, but prepare a subset.
        # For simplicity, we'll let them pick a few to "have ready" or "focus on".
        # Or, we can say they select none here and handle preparation later.
        # For this step, let's say they select 0 to "learn", as they "know" all.
        # This part might need refinement based on how "known" vs "prepared" is handled.
        # For now, let's treat this as selecting "known" or "spellbook" spells.
        # Let's assume Clerics/Druids pick their prepared spells later, so 0 L1 spells selected here.
        num_level_1_spells_to_select = 0 # They prepare from full list later
    elif class_name == "Druid":
        num_cantrips_to_select = 2
        num_level_1_spells_to_select = 0 # They prepare from full list later
    elif class_name == "Warlock":
        num_cantrips_to_select = 2
        num_level_1_spells_to_select = 2 # Pact magic known spells
    # Add other casters like Artificer if data is available. Paladin/Ranger get spells at L2.

    # Fetch available spells for the class
    # Using .like() for JSON array string search. Ensure class_name is properly quoted.
    # Example: classes_that_can_use = '["Wizard", "Sorcerer"]'
    # Search pattern should be like '%"Wizard"%'
    search_pattern = f'%"{selected_class.name}"%'
    available_cantrips = Spell.query.filter(Spell.level == 0, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all()
    available_level_1_spells = Spell.query.filter(Spell.level == 1, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all()
    
    # If no spells need to be selected (e.g. Cleric/Druid in this simplified model, or a non-caster somehow got here)
    if num_cantrips_to_select == 0 and num_level_1_spells_to_select == 0 and request.method == 'GET':
        # Store empty lists and proceed
        session['new_character_data']['chosen_cantrip_ids'] = []
        session['new_character_data']['chosen_level_1_spell_ids'] = []
        flash('No spells to select at Level 1 for your class in this step (e.g. Clerics/Druids prepare spells daily).', 'info')
        return redirect(url_for('main.creation_review'))


    if request.method == 'POST':
        chosen_cantrip_ids_str = request.form.getlist('chosen_cantrip')
        chosen_level_1_spell_ids_str = request.form.getlist('chosen_level_1_spell')

        errors = False
        if len(chosen_cantrip_ids_str) != num_cantrips_to_select:
            flash(f'Please select exactly {num_cantrips_to_select} cantrip(s). You chose {len(chosen_cantrip_ids_str)}.', 'error')
            errors = True
        
        if len(chosen_level_1_spell_ids_str) != num_level_1_spells_to_select:
            flash(f'Please select exactly {num_level_1_spells_to_select} 1st-level spell(s). You chose {len(chosen_level_1_spell_ids_str)}.', 'error')
            errors = True

        if errors:
            # Re-render with submitted choices to allow correction
            return render_template('create_character_spells.html',
                                   race_name=char_data.get('race_name'),
                                   class_name=selected_class.name,
                                   background_name=char_data.get('background_name'),
                                   available_cantrips=available_cantrips,
                                   num_cantrips_to_select=num_cantrips_to_select,
                                   available_level_1_spells=available_level_1_spells,
                                   num_level_1_spells_to_select=num_level_1_spells_to_select,
                                   submitted_cantrips=chosen_cantrip_ids_str, # Pass as strings
                                   submitted_level_1_spells=chosen_level_1_spell_ids_str) # Pass as strings
        
        try:
            session['new_character_data']['chosen_cantrip_ids'] = [int(id_str) for id_str in chosen_cantrip_ids_str]
            session['new_character_data']['chosen_level_1_spell_ids'] = [int(id_str) for id_str in chosen_level_1_spell_ids_str]
        except ValueError:
            flash('Invalid spell ID submitted. Please try again.', 'error')
            # This case is less likely if form values are directly from Spell.id
            return render_template('create_character_spells.html',
                                   # ... (re-pass all context)
                                   submitted_cantrips=chosen_cantrip_ids_str, 
                                   submitted_level_1_spells=chosen_level_1_spell_ids_str)
        
        session.modified = True
        flash('Spells selected!', 'success')
        return redirect(url_for('main.creation_review'))

    # GET request
    return render_template('create_character_spells.html',
                           race_name=char_data.get('race_name'),
                           class_name=selected_class.name,
                           background_name=char_data.get('background_name'),
                           available_cantrips=available_cantrips,
                           num_cantrips_to_select=num_cantrips_to_select,
                           available_level_1_spells=available_level_1_spells,
                           num_level_1_spells_to_select=num_level_1_spells_to_select,
                           submitted_cantrips=[], # No selections yet on GET
                           submitted_level_1_spells=[])


# Character Creation Step 9: Final Details & Review
@bp.route('/creation/review', methods=['GET', 'POST'])
@login_required
def creation_review():
    char_data = session.get('new_character_data', {})
    # Check for ability_scores as a proxy for core steps completion
    if not char_data.get('ability_scores'):
        flash('Please complete the core character creation steps first, starting with ability scores.', 'error')
        return redirect(url_for('main.creation_stats')) # Redirect to stats or an earlier appropriate step

    # Fetch related objects for display
    race = Race.query.get(char_data.get('race_id'))
    char_class_obj = Class.query.get(char_data.get('class_id')) # Renamed to avoid clash
    
    if not race or not char_class_obj:
        flash('Race or Class data missing or invalid. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    cantrips = Spell.query.filter(Spell.id.in_(char_data.get('chosen_cantrip_ids', []))).all()
    level_1_spells = Spell.query.filter(Spell.id.in_(char_data.get('chosen_level_1_spell_ids', []))).all()

    # Compile Proficiencies for display in GET
    all_skill_proficiencies = set(char_data.get('background_skill_proficiencies', []))
    all_skill_proficiencies.update(char_data.get('class_skill_proficiencies', []))
    # (Future: add racial skill profs if they were stored separately)

    all_tool_proficiencies = set(char_data.get('background_tool_proficiencies', []))
    all_tool_proficiencies.update(char_data.get('tool_proficiencies_class_fixed', []))
    # (Future: add racial tool profs)
    
    all_language_proficiencies = set(char_data.get('background_languages', []))
    # (Future: add racial languages if they were stored separately and aren't just text descriptions)

    # parse_coinage is now imported from app.utils

    if request.method == 'POST':
        character_name = request.form.get('character_name')
        alignment = request.form.get('alignment')
        char_description = request.form.get('character_description') # Model field is 'description'

        if not character_name:
            flash('Character name is required.', 'error')
            # Re-render GET view with all the data
            return render_template('create_character_review.html',
                                   data=char_data, race=race, char_class=char_class_obj,
                                   cantrips=cantrips, level_1_spells=level_1_spells,
                                   all_skill_proficiencies=list(all_skill_proficiencies),
                                   all_tool_proficiencies=list(all_tool_proficiencies),
                                   all_language_proficiencies=list(all_language_proficiencies),
                                   submitted_name=character_name,
                                   submitted_alignment=alignment,
                                   submitted_description=char_description)
        
        # Re-calculate proficiencies for saving to ensure consistency
        # (or trust that char_data hasn't changed, but re-calc is safer if complex)
        current_skills_set = set(char_data.get('background_skill_proficiencies', []))
        current_skills_set.update(char_data.get('class_skill_proficiencies', []))
        
        current_tools_set = set(char_data.get('background_tool_proficiencies', []))
        current_tools_set.update(char_data.get('tool_proficiencies_class_fixed', []))

        current_languages_set = set(char_data.get('background_languages', []))
        # Assuming racial languages are part of background_languages if "Two of your choice" etc.
        # Or need to fetch race.languages and parse if stored as JSON list of names.
        # For now, this relies on background_languages potentially containing the choices.

        new_char = Character(
            name=character_name,
            description=char_description,
            user_id=current_user.id,
            race_id=char_data.get('race_id'),
            class_id=char_data.get('class_id'),
            level=1,
            strength=char_data.get('ability_scores', {}).get('STR'),
            dexterity=char_data.get('ability_scores', {}).get('DEX'),
            constitution=char_data.get('ability_scores', {}).get('CON'),
            intelligence=char_data.get('ability_scores', {}).get('INT'),
            wisdom=char_data.get('ability_scores', {}).get('WIS'),
            charisma=char_data.get('ability_scores', {}).get('CHA'),
            hp=char_data.get('max_hp'), # current_hp from model
            max_hp=char_data.get('max_hp'),
            armor_class=char_data.get('armor_class_base'), # Base AC, actual AC needs armor calculation
            speed=char_data.get('speed'),
            alignment=alignment,
            background_name=char_data.get('background_name'),
            # Store background profs as a simple list, not separated by type in this field
            background_proficiencies=json.dumps(
                char_data.get('background_skill_proficiencies', []) +
                char_data.get('background_tool_proficiencies', []) +
                char_data.get('background_languages', [])
            ),
            # background_equipment field is removed from Character model
            current_proficiencies=json.dumps({
                'skills': list(current_skills_set),
                'tools': list(current_tools_set),
                'languages': list(current_languages_set),
                'armor': char_data.get('armor_proficiencies', []),
                'weapons': char_data.get('weapon_proficiencies', []),
                'saving_throws': char_data.get('saving_throw_proficiencies', [])
            })
            # current_equipment field is removed from Character model
        )

        db.session.add(new_char)
        db.session.flush() # Flush to get new_char.id for foreign key relationships

        # Process Equipment and Coinage
        # final_equipment from session is a list of strings like "Shield (x1)", "Dagger"
        # background_equipment from session is a single string like "Acolyte's pack (holy symbol, ... 15 gp)"
        
        final_equipment_from_session = char_data.get('final_equipment', [])
        background_equipment_str = char_data.get('background_equipment', '') # This is a string

        # Parse all coinage from background equipment string
        parsed_coins = parse_coinage(background_equipment_str)
        for coin_type, quantity in parsed_coins.items():
            if quantity > 0:
                # Construct a descriptive name like "Gold Pieces", "Silver Pieces"
                coin_name = f"{coin_type.title()} Pieces" 
                coin_entry = Coinage(name=coin_name, quantity=quantity, character_id=new_char.id)
                db.session.add(coin_entry)
        
        # Process items from final_equipment (class choices / fixed items from class)
        # and items from background_equipment_str (excluding gold)
        
        # Consolidate all item strings to parse
        all_item_strings_to_parse = []
        if background_equipment_str:
            # Add parts of the background equipment string, attempting to split by common delimiters
            # and excluding already processed gold parts.
            potential_bg_items = re.split(r',\s*|\s+and\s+', background_equipment_str)
            for p_item in potential_bg_items:
                p_item_clean = p_item.strip()
                if "gp" in p_item_clean.lower() or "gold pieces" in p_item_clean.lower() or "gold" in p_item_clean.lower():
                    continue # Gold already handled
                if p_item_clean and not p_item_clean.lower().startswith("a pouch containing"): # Avoid adding the pouch itself if it only contained gold
                    all_item_strings_to_parse.append(p_item_clean)
        
        # Add items from class equipment choices (which might include "Background: full string" if not careful in previous step)
        for item_string_from_session in final_equipment_from_session:
            if item_string_from_session.lower().startswith("background:"):
                # If the full background string was added to final_equipment, parse it similarly
                actual_bg_items_str = item_string_from_session.replace("Background: ", "", 1)
                potential_bg_items_from_final = re.split(r',\s*|\s+and\s+', actual_bg_items_str)
                for p_item in potential_bg_items_from_final:
                    p_item_clean = p_item.strip()
                    if "gp" in p_item_clean.lower() or "gold pieces" in p_item_clean.lower() or "gold" in p_item_clean.lower():
                        continue
                    if p_item_clean and not p_item_clean.lower().startswith("a pouch containing"):
                         all_item_strings_to_parse.append(p_item_clean)
            else:
                all_item_strings_to_parse.append(item_string_from_session)

        # Process all collected item strings with aggregation
        aggregated_items = {} # To store {normalized_name: {'quantity': Q, 'description': D}}

        for item_string in all_item_strings_to_parse:
            item_name_raw = item_string
            quantity = 1
            # Default description, can be updated if a more specific one is parsed
            description = "Starting equipment" 

            # Basic parsing for quantity like "Item Name (xN)" or "N Item Name"
            qty_match_suffix = re.match(r'^(.*?)\s*\(x(\d+)\)$', item_string) # "Shield (x1)"
            qty_match_prefix = re.match(r'(\d+)\s+(.*)', item_string)    # "5 sticks of incense"

            if qty_match_suffix:
                item_name_raw = qty_match_suffix.group(1).strip()
                quantity = int(qty_match_suffix.group(2))
            elif qty_match_prefix:
                quantity = int(qty_match_prefix.group(1))
                item_name_raw = qty_match_prefix.group(2).strip()
            
            # Normalize item name (e.g., title case and strip whitespace)
            # More advanced normalization (e.g., singularization) could be added here if needed.
            normalized_item_name = item_name_raw.strip().title() # Using title case for consistency

            if not normalized_item_name: # Avoid adding empty item names
                continue

            if normalized_item_name in aggregated_items:
                aggregated_items[normalized_item_name]['quantity'] += quantity
                # Description handling: keep the first one, or implement more complex logic
                # For now, if a more generic "Starting equipment" is already there,
                # and a more specific one comes along (e.g. "From background"), prefer the more specific.
                # This is a simple heuristic.
                if aggregated_items[normalized_item_name]['description'] == "Starting equipment" and description != "Starting equipment":
                    aggregated_items[normalized_item_name]['description'] = description
            else:
                aggregated_items[normalized_item_name] = {
                    'quantity': quantity,
                    'description': description 
                }
        
        # Create Item objects from the aggregated list
        for name, data in aggregated_items.items():
            item = Item(name=name, quantity=data['quantity'], character_id=new_char.id, description=data['description'])
            db.session.add(item)

        # Assign spells
        chosen_spell_ids = char_data.get('chosen_cantrip_ids', []) + char_data.get('chosen_level_1_spell_ids', [])
        if chosen_spell_ids:
            spells_to_add = Spell.query.filter(Spell.id.in_(chosen_spell_ids)).all()
            new_char.known_spells.extend(spells_to_add)
            # For classes that prepare spells (Cleric, Druid, Paladin, Wizard),
            # this step adds to "known_spells". "prepared_spells" would be a separate mechanic.
            # Wizard L1 spells are added to spellbook (known_spells), then prepared.
            # Sorcerers/Bards directly know their chosen spells.

        db.session.add(new_char)
        db.session.commit()

        session.pop('new_character_data', None) # Clear session data
        flash('Character created successfully!', 'success')
        return redirect(url_for('main.index'))

    # GET request
    return render_template('create_character_review.html',
                           data=char_data,
                           race=race,
                           char_class=char_class_obj, # Use the renamed variable
                           cantrips=cantrips,
                           level_1_spells=level_1_spells,
                           all_skill_proficiencies=list(all_skill_proficiencies),
                           all_tool_proficiencies=list(all_tool_proficiencies),
                           all_language_proficiencies=list(all_language_proficiencies),
                           submitted_name=char_data.get('character_name_draft',''), # For repopulating if user goes back
                           submitted_alignment=char_data.get('alignment_draft',''),
                           submitted_description=char_data.get('description_draft',''))



ALL_SKILLS_LIST = [
    ("Acrobatics", "DEX"), ("Animal Handling", "WIS"), ("Arcana", "INT"),
    ("Athletics", "STR"), ("Deception", "CHA"), ("History", "INT"),
    ("Insight", "WIS"), ("Intimidation", "CHA"), ("Investigation", "INT"),
    ("Medicine", "WIS"), ("Nature", "INT"), ("Perception", "WIS"),
    ("Performance", "CHA"), ("Persuasion", "CHA"), ("Religion", "INT"),
    ("Sleight of Hand", "DEX"), ("Stealth", "DEX"), ("Survival", "WIS")
]
ABILITY_NAMES_FULL = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']


@bp.route('/<int:character_id>/adventure', methods=['GET', 'POST'])
@login_required
def adventure(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash(_('This character does not belong to you.'))
        return redirect(url_for('main.index'))

    try:
        log_entries = json.loads(character.adventure_log or '[]')
        if not isinstance(log_entries, list):
            log_entries = []
    except json.JSONDecodeError:
        log_entries = []
        current_app.logger.warning(f"Adventure log for character {character_id} was malformed and has been reset.")

    # If adventure log is empty, trigger initial DM message
    if not log_entries:
        dm_chat_session = None  # Initialize session variable

        # Step A: Send System Rules to Gemini
        current_app.logger.info(f"Attempting to send system rules to Gemini for new adventure (char_id: {character_id}).")
        rules_response_text, dm_chat_session, rules_error = geminiai(
            prompt_text_to_send=GEMINI_DM_SYSTEM_RULES,
            existing_chat_session=None
        )

        if rules_error:
            current_app.logger.error(f"Error sending system rules to Gemini for char {character_id}: {rules_error}")
            flash(_("The Dungeon Master is currently unavailable due to a configuration error. Please try again later."), 'error')
            # Render with empty log or redirect. For now, page will render with empty log.
        elif rules_response_text is not None:
            # Log AI's ack of rules if any text is returned. Usually, this might be empty or a simple "OK".
            current_app.logger.info(f"System rules sent. Gemini ack/response: {rules_response_text[:200]}") # Log snippet
        else: # No error, but no text response (might be normal for system prompt)
            current_app.logger.info(f"System rules sent to Gemini, no explicit text response received (char_id: {character_id}). Session established.")

        # Proceed only if rules step was okay (no error and session established)
        if not rules_error and dm_chat_session is not None:
            # Step B: Prepare Character Sheet Information
            # Proficiencies and equipment are loaded later for the template, ensure they are available here.
            # The existing code populates these variables (proficient_skills, equipment_list etc.)
            # *after* this 'if not log_entries:' block. This needs reordering or recalculation here.
            
            # For safety, let's re-calculate/re-fetch necessary character sheet details here or ensure they are loaded before this block.
            # Assuming proficiencies_data, proficient_*, equipment_list are available from the later part of the route.
            # This is a structural dependency that needs care. For now, let's assume they are available.
            # If not, they would need to be calculated here.
            # For now, I will just use the variables that are already populated later in the function.
            # This part of the code will be run *before* the existing proficiency/equipment parsing.
            # So I must duplicate that logic here or move it up.
            # Let's duplicate minimally for now for clarity of this step.

            temp_proficiencies_data = {}
            try:
                temp_proficiencies_data = json.loads(character.current_proficiencies or '{}')
                if not isinstance(temp_proficiencies_data, dict): temp_proficiencies_data = {}
            except json.JSONDecodeError: 
                current_app.logger.error(f"Malformed current_proficiencies for char {character.id} in adventure init prompt.")
                pass # temp_proficiencies_data remains {}
            
            temp_skills_str = ", ".join(temp_proficiencies_data.get('skills', [])) or "None"
            temp_saving_throws_str = ", ".join(temp_proficiencies_data.get('saving_throws', [])) or "None"
            temp_armor_prof_str = ", ".join(temp_proficiencies_data.get('armor', [])) or "None"
            temp_weapon_prof_str = ", ".join(temp_proficiencies_data.get('weapons', [])) or "None"
            temp_tool_prof_str = ", ".join(temp_proficiencies_data.get('tools', [])) or "None"
            temp_languages_str = ", ".join(temp_proficiencies_data.get('languages', [])) or "None"

            # Build equipment string from Item and Coinage models for the prompt
            # character.items and character.coinage should be loaded due to relationship access
            items_list_for_prompt = [f"{item.name} (x{item.quantity})" + (f" - {item.description}" if item.description else "") for item in character.items]
            coinage_list_for_prompt = [f"{coin.quantity} {coin.name}" for coin in character.coinage]
            
            full_equipment_list_for_prompt = items_list_for_prompt + coinage_list_for_prompt
            temp_equipment_str = "\n".join([f"- {item_str}" for item_str in full_equipment_list_for_prompt]) if full_equipment_list_for_prompt else "None"
            
            xp_thresholds = {1: 300, 2: 900, 3: 2700, 4: 6500, 5: 14000, 6: 23000, 7: 34000, 8: 48000, 9: 64000, 10: 85000, 11: 100000, 12: 120000, 13: 140000, 14: 165000, 15: 195000, 16: 225000, 17: 265000, 18: 305000, 19: 355000}
            xp_for_next = xp_thresholds.get(character.level, "N/A for current level")

            character_sheet_prompt = (
                f"PLAYER CHARACTER SHEET:\n"
                f"Name: {character.name}\n"
                f"Race: {character.race.name if character.race else 'N/A'}\n"
                f"Class: {character.char_class.name if character.char_class else 'N/A'}\n"
                f"Level: {character.level}\n\n"
                f"Ability Scores:\n"
                f"  Strength: {character.strength}\n"
                f"  Dexterity: {character.dexterity}\n"
                f"  Constitution: {character.constitution}\n"
                f"  Intelligence: {character.intelligence}\n"
                f"  Wisdom: {character.wisdom}\n"
                f"  Charisma: {character.charisma}\n\n"
                f"Proficiencies:\n"
                f"  Skills: {temp_skills_str}\n"
                f"  Saving Throws: {temp_saving_throws_str}\n"
                f"  Armor: {temp_armor_prof_str}\n"
                f"  Weapons: {temp_weapon_prof_str}\n"
                f"  Tools: {temp_tool_prof_str}\n"
                f"  Languages: {temp_languages_str}\n\n"
                f"Equipment:\n{temp_equipment_str}\n\n"
                f"Background: {character.background_name or 'N/A'}\n"
                f"Description: {character.description or 'Not specified'}\n"
                f"Alignment: {character.alignment or 'Not specified'}\n\n"
                f"Experience Points:\n"
                f"  Current XP: {character.xp or 0}\n"
                f"  XP for Next Level: {xp_for_next}\n\n"
                f"The above is my character sheet. Please confirm you have received it, and then proceed with the initial setup questions as outlined in your system rules (ask about story/challenges first, then playstyle preference in a separate, subsequent message)."
            )
            current_app.logger.info(f"Sending character sheet to Gemini for char {character_id}.")
            # Step C: Send Character Sheet to Gemini
            first_dm_message, dm_chat_session, char_sheet_error = geminiai(
                prompt_text_to_send=character_sheet_prompt,
                existing_chat_session=dm_chat_session 
            )

            if char_sheet_error:
                current_app.logger.error(f"Error sending char sheet to Gemini for char {character_id}: {char_sheet_error}")
                flash(_("The Dungeon Master had trouble reading your character sheet. Please try again later."), 'error')
            elif first_dm_message:
                current_app.logger.info(f"Received first DM message for char {character_id}: {first_dm_message[:200]}")
                # Step D: Save and Display First Message
                # Log the character sheet prompt as a user message BEFORE the DM's first actual adventure message
                log_entries.append({"sender": "user", "text": character_sheet_prompt})
                log_entries.append({"sender": "dm", "text": first_dm_message})
                character.adventure_log = json.dumps(log_entries)
                # The chat session object (dm_chat_session) is not stored in the DB.
                # It will be reconstructed from log_entries in the send_chat_message route.
                try:
                    db.session.commit()
                except Exception as e:
                    current_app.logger.error(f"Failed to commit initial DM message (after char sheet) to DB for char {character_id}: {str(e)}")
                    db.session.rollback()
                    flash(_("An error occurred saving your adventure's start. Please try again."), 'error')
            else: # No error, but no message
                current_app.logger.error(f"Received no message from Gemini after sending character sheet for char {character_id}.")
                flash(_("The Dungeon Master seems to be at a loss for words after seeing your character sheet! Please try again."), 'error')
        elif dm_chat_session is None and not rules_error : # Rules step failed to establish a session but didn't set rules_error
             current_app.logger.error(f"Gemini session not established after system rules, cannot proceed for char {character_id}.")
             flash(_("The Dungeon Master is currently unavailable. Please try again later."), 'error')


    # --- Data Preparation for Character Sheet (for template rendering) ---
    # This part needs to run regardless of whether the log was empty or not.
    proficiency_bonus = (character.level - 1) // 4 + 2

    # Parse Proficiencies (proficient_skills and proficient_saving_throws are used below and also for AI prompt context)
    proficiencies_data = {}
    try:
        proficiencies_data = json.loads(character.current_proficiencies or '{}')
        if not isinstance(proficiencies_data, dict): # Ensure it's a dict
            proficiencies_data = {}
            current_app.logger.warning(f"current_proficiencies for char {character_id} was not a dict, reset to empty.")
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse current_proficiencies JSON for character {character_id}: {character.current_proficiencies}")
        proficiencies_data = {} # Default to empty if parsing fails

    proficient_skills = proficiencies_data.get('skills', [])
    proficient_tools = proficiencies_data.get('tools', [])
    proficient_languages = proficiencies_data.get('languages', [])
    proficient_armor = proficiencies_data.get('armor', [])
    proficient_weapons = proficiencies_data.get('weapons', [])
    proficient_saving_throws = proficiencies_data.get('saving_throws', []) # List of ability abbreviations e.g. ["STR", "DEX"]

    # Get Items and Coinage for template rendering
    # These are now direct relationships from the Character model
    character_items = character.items # List of Item objects
    character_coinage = character.coinage # List of Coinage objects

    # Filter Spells
    cantrips = [spell for spell in character.known_spells if spell.level == 0]
    level_1_spells = [spell for spell in character.known_spells if spell.level == 1]

    # Prepare Saving Throws Data
    saving_throws_data = []
    for ability_name_full in ABILITY_NAMES_FULL:
        ability_attr_lower = ability_name_full.lower() 
        ability_attr_short = ability_name_full[:3].upper() 
        
        base_score = getattr(character, ability_attr_lower, 10) 
        base_modifier = (base_score - 10) // 2
        is_proficient = ability_attr_short in proficient_saving_throws
        final_modifier = base_modifier + proficiency_bonus if is_proficient else base_modifier
        saving_throws_data.append({
            "name": ability_name_full,
            "attribute_short": ability_attr_short, 
            "modifier": final_modifier,
            "is_proficient": is_proficient
        })

    # Prepare Skills Data
    skills_data = []
    ability_abbr_to_attr_lower = {
        "STR": "strength", "DEX": "dexterity", "CON": "constitution",
        "INT": "intelligence", "WIS": "wisdom", "CHA": "charisma"
    }
    for skill_name, skill_ability_abbr in ALL_SKILLS_LIST:
        ability_attr_lower = ability_abbr_to_attr_lower.get(skill_ability_abbr)
        if not ability_attr_lower:
            current_app.logger.error(f"Unknown ability abbreviation '{skill_ability_abbr}' for skill '{skill_name}'. Defaulting score to 10.")
            base_score = 10
        else:
            base_score = getattr(character, ability_attr_lower, 10)
            
        base_modifier = (base_score - 10) // 2
        is_proficient = skill_name in proficient_skills
        final_modifier = base_modifier + proficiency_bonus if is_proficient else base_modifier
        skills_data.append({
            "name": skill_name,
            "ability_abbr": skill_ability_abbr,
            "modifier": final_modifier,
            "is_proficient": is_proficient
        })

    # Prepare Abilities Data
    abilities_data = []
    ability_full_to_short_map = {
        'Strength': 'STR', 'Dexterity': 'DEX', 'Constitution': 'CON',
        'Intelligence': 'INT', 'Wisdom': 'WIS', 'Charisma': 'CHA'
    }
    for ability_name_full in ABILITY_NAMES_FULL:
        attr_lower = ability_name_full.lower() 
        score = getattr(character, attr_lower, 10) 
        modifier = (score - 10) // 2
        abilities_data.append({
            "name_full": ability_name_full,
            "name_short": ability_full_to_short_map.get(ability_name_full, "UNK"), 
            "score": score,
            "modifier": modifier
        })
    
    return render_template('adventure.html', 
                           title=_('Adventure'),
                           character=character, 
                           log_entries=log_entries,
                           # Character Sheet Data:
                           all_skills_list=ALL_SKILLS_LIST, 
                           ability_names_full=ABILITY_NAMES_FULL, 
                           proficiency_bonus=proficiency_bonus,
                           proficient_skills=proficient_skills, 
                           proficient_saving_throws=proficient_saving_throws,
                           proficient_tools=proficient_tools,
                           proficient_languages=proficient_languages,
                           proficient_armor=proficient_armor,
                           proficient_weapons=proficient_weapons,
                           # equipment_list is replaced by character_items and character_coinage
                           character_items=character_items,
                           character_coinage=character_coinage,
                           cantrips=cantrips,
                           level_1_spells=level_1_spells,
                           # New pre-calculated data for template:
                           saving_throws_data=saving_throws_data,
                           skills_data=skills_data,
                           abilities_data=abilities_data
                           )

@bp.route('/roll_dice_from_sheet', methods=['POST'])
@login_required
def roll_dice_from_sheet():
    data = request.get_json()
    if not data:
        return jsonify(error="No data provided"), 400

    roll_type = data.get('roll_type')
    dice_formula = data.get('dice_formula', '1d20') # Default to 1d20
    modifier = data.get('modifier', 0)
    roll_name = data.get('roll_name', 'Roll') # Default roll name

    if not isinstance(modifier, int):
        try:
            modifier = int(modifier)
        except ValueError:
            return jsonify(error="Invalid modifier format. Must be an integer."), 400

    try:
        parts = dice_formula.lower().split('d')
        if len(parts) != 2:
            raise ValueError("Invalid dice formula format. Expected 'XdY', e.g., '1d20'.")
        
        num_dice = int(parts[0])
        num_sides = int(parts[1])

        if num_dice <= 0 or num_sides <= 0:
            raise ValueError("Number of dice and sides must be positive.")

    except Exception as e: # Catches ValueError from int conversion or splitting
        current_app.logger.error(f"Error parsing dice formula '{dice_formula}': {e}")
        return jsonify(error=f"Invalid dice formula: {dice_formula}. Expected format 'XdY' (e.g., '1d20')."), 400

    # Call the utility function. It returns (sum_of_rolls, list_of_all_rolls)
    # The prompt implies `actual_rolls, subtotal = roll_dice(...)`
    # My utils.roll_dice returns `sum_of_rolls, rolls`. So:
    # subtotal = sum_of_rolls, actual_rolls = rolls
    subtotal, actual_rolls = roll_dice(num_dice, num_sides) 
    total = subtotal + modifier

    return jsonify({
        "roll_name": roll_name,
        "dice_formula": dice_formula,
        "modifier": modifier,
        "rolls": actual_rolls,
        "subtotal": subtotal,
        "total": total
    })


@bp.route('/send_chat_message/<int:character_id>', methods=['POST'])
@login_required
def send_chat_message(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(error=_("Unauthorized. This character does not belong to you.")), 403

    data = request.get_json()
    if not data:
        return jsonify(error=_("No data provided in request.")), 400
        
    user_message = data.get('message')
    if not user_message:
        return jsonify(error=_("No message provided.")), 400

    try:
        log_entries = json.loads(character.adventure_log or '[]')
        if not isinstance(log_entries, list):
            log_entries = []
    except json.JSONDecodeError:
        log_entries = []
        current_app.logger.warning(f"Adventure log for char {character_id} was malformed, starting fresh for this turn.")

    gemini_history_list = []
    for entry in log_entries:
        role = 'user' if entry['sender'] == 'user' else 'model'
        gemini_history_list.append({'role': role, 'parts': [{'text': entry['text']}]})

    # --- Model Initialization and Configuration ---
    # API key configuration is handled by the geminiai wrapper function.
    # Safety settings are also handled by the geminiai wrapper function's model init if no session is passed.
    # However, if we start the chat here, we need to define them here for THIS model instance.
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    
    db_setting = db.session.query(Setting).filter_by(key='DEFAULT_GEMINI_MODEL').first()
    model_to_use = ""
    if db_setting and db_setting.value:
        model_to_use = db_setting.value
    else:
        model_to_use = current_app.config.get('DEFAULT_GEMINI_MODEL')
        if not model_to_use: # Ultimate fallback
            current_app.logger.error("DEFAULT_GEMINI_MODEL not found in DB or config, using hardcoded fallback.")
            model_to_use = "gemini-1.5-flash" 
    # --- End Model Initialization ---
    
    chat_session = None
    try:
        model = genai.GenerativeModel(
            model_name=model_to_use, 
            safety_settings=safety_settings, 
            system_instruction=GEMINI_DM_SYSTEM_RULES
        )
        # Start chat with the constructed history from adventure_log
        chat_session = model.start_chat(history=gemini_history_list)
        current_app.logger.info(f"Chat session started for char {character_id} with {len(gemini_history_list)} history entries.")

    except Exception as e:
        current_app.logger.error(f"Failed to initialize Gemini model or chat session in send_chat_message for char {character_id}: {str(e)}")
        return jsonify(error=_("The Dungeon Master is currently re-reading the ancient texts (model/session init failed).")), 500

    # Call the refactored geminiai function
    ai_response_text, _, error_from_geminiai = geminiai(
        prompt_text_to_send=user_message,
        existing_chat_session=chat_session # Pass the session that includes history and system instruction
    )

    if error_from_geminiai:
        current_app.logger.error(f"Error from geminiai function for char {character_id}: {error_from_geminiai}")
        # error_from_geminiai is already a user-facing translated string
        return jsonify(reply=error_from_geminiai), 200 # Return 200 so client displays it as a DM message

    if ai_response_text:
        log_entries.append({"sender": "user", "text": user_message})
        log_entries.append({"sender": "dm", "text": ai_response_text})
        character.adventure_log = json.dumps(log_entries)
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to commit chat message to DB for char {character_id}: {str(e)}")
            db.session.rollback()
            return jsonify(error=_("An error occurred saving your conversation to the chronicles.")), 500
        return jsonify(reply=ai_response_text), 200
    else:
        # This case implies geminiai returned (None, session, None) which means no error but no text.
        current_app.logger.warning(f"Received no text and no error from geminiai for char {character_id}. User message: '{user_message}'")
        # Return a generic "DM is pondering" message rather than an error, as it might not be a hard error.
        return jsonify(reply=_("The Dungeon Master ponders your words but remains silent for now...")), 200


@bp.route('/character/<int:character_id>/inventory/add_item', methods=['POST'])
@login_required
def add_item_to_inventory(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash('You do not have permission to modify this character.', 'error')
        return redirect(url_for('main.adventure', character_id=character_id))

    item_name = request.form.get('item_name', '').strip().title()
    item_description = request.form.get('item_description', '').strip()
    try:
        item_quantity = int(request.form.get('item_quantity', 1))
    except ValueError:
        flash('Invalid quantity. Please enter a number.', 'error')
        return redirect(url_for('main.adventure', character_id=character_id))

    if not item_name:
        flash('Item name cannot be empty.', 'error')
        return redirect(url_for('main.adventure', character_id=character_id))
    
    if item_quantity <= 0:
        flash('Item quantity must be positive.', 'error')
        return redirect(url_for('main.adventure', character_id=character_id))

    existing_item = Item.query.filter_by(character_id=character.id, name=item_name).first()

    if existing_item:
        existing_item.quantity += item_quantity
        flash(f'{item_quantity} {item_name}(s) added. You now have {existing_item.quantity}.', 'success')
    else:
        new_item = Item(
            name=item_name,
            description=item_description,
            quantity=item_quantity,
            character_id=character.id
        )
        db.session.add(new_item)
        flash(f'{item_name} (x{item_quantity}) added to inventory.', 'success')
    
    db.session.commit()
    return redirect(url_for('main.adventure', character_id=character_id) + "#character-sheet-overlay")


@bp.route('/character/<int:character_id>/inventory/remove_item/<int:item_id>', methods=['POST'])
@login_required
def remove_item_from_inventory(character_id, item_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash('You do not have permission to modify this character.', 'error')
        return redirect(url_for('main.adventure', character_id=character_id))

    item_to_remove = Item.query.filter_by(id=item_id, character_id=character.id).first()

    if item_to_remove:
        item_name = item_to_remove.name
        db.session.delete(item_to_remove)
        db.session.commit()
        flash(f'{item_name} removed from inventory.', 'success')
    else:
        flash('Item not found or does not belong to this character.', 'error')
        
    return redirect(url_for('main.adventure', character_id=character_id) + "#character-sheet-overlay")


@bp.route('/character/<int:character_id>/inventory/update_coinage', methods=['POST'])
@login_required
def update_coinage_for_character(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash('You do not have permission to modify this character\'s coinage.', 'error')
        return redirect(url_for('main.adventure', character_id=character_id))

    coin_types = {
        "Gold": "Gold Pieces",
        "Silver": "Silver Pieces",
        "Copper": "Copper Pieces"
    }
    
    updated_any = False

    for form_key, db_name in coin_types.items():
        try:
            quantity_str = request.form.get(f'{form_key.lower()}_quantity', '0')
            # Treat empty string as 0, or if user types non-numeric, catch ValueError
            quantity = int(quantity_str) if quantity_str.strip() else 0 
            if quantity < 0: # Negative quantities not allowed
                flash(f'Invalid quantity for {db_name}. Must be zero or positive.', 'error')
                # Potentially redirect here or collect all errors
                continue 

        except ValueError:
            flash(f'Invalid quantity format for {db_name}. Please enter a number.', 'error')
            # Potentially redirect here or collect all errors
            continue 

        existing_coinage = Coinage.query.filter_by(character_id=character.id, name=db_name).first()

        if existing_coinage:
            if quantity > 0:
                if existing_coinage.quantity != quantity:
                    existing_coinage.quantity = quantity
                    updated_any = True
            else: # quantity is 0 or less (already handled negative)
                db.session.delete(existing_coinage)
                updated_any = True
        elif quantity > 0: # No existing record, but new quantity is positive
            new_coinage_entry = Coinage(name=db_name, quantity=quantity, character_id=character.id)
            db.session.add(new_coinage_entry)
            updated_any = True
            
    if updated_any:
        try:
            db.session.commit()
            flash('Coinage updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating coinage for character {character_id}: {str(e)}")
            flash('An error occurred while updating coinage.', 'error')
    else:
        flash('No changes detected in coinage amounts.', 'info')

    return redirect(url_for('main.adventure', character_id=character_id) + "#character-sheet-overlay")
