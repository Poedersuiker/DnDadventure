import json # Added json import
import json # Added json import (already present but good to ensure)
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app import db
from app.models import User, Character, Race, Class, Spell # Added Spell model
from app.main import bp

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

@bp.route('/create_character', methods=['GET', 'POST'])
@login_required
def create_character():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Character name is required.', 'error')
            return render_template('create_character.html')

        new_character = Character(name=name, description=description, user_id=current_user.id)
        db.session.add(new_character)
        db.session.commit()
        flash('Character created successfully!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('create_character.html')

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
        # session.modified = True # Ensure session is saved if nested dicts are modified directly
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
        # session.modified = True # Ensure session is saved
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


    if request.method == 'POST':
        base_scores = {}
        final_scores = {}
        errors = False
        ability_names = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
        
        for ability in ability_names:
            score_val = request.form.get(ability)
            if not score_val:
                flash(f'{ability.capitalize()} score is required.', 'error')
                errors = True
                continue
            try:
                score = int(score_val)
                if not (3 <= score <= 18): # Basic validation for manually entered base scores
                    flash(f'{ability.capitalize()} score must be between 3 and 18 before racial modifiers.', 'error')
                    errors = True
                base_scores[ability.upper()] = score # Store with uppercase key e.g. STR
            except ValueError:
                flash(f'Invalid score for {ability.capitalize()}. Must be a number.', 'error')
                errors = True
        
        if errors:
            return render_template('create_character_stats.html',
                                   race_name=selected_race.name,
                                   class_name=selected_class.name,
                                   racial_bonuses_dict=racial_bonuses_dict,
                                   primary_ability=primary_ability,
                                   standard_array=standard_array,
                                   submitted_scores=request.form) # Pass back submitted form data

        # Calculate final scores
        final_scores = base_scores.copy()
        for bonus_item in racial_bonuses_list:
            ability_key = bonus_item.get('name') # e.g., "STR"
            bonus_value = bonus_item.get('bonus', 0)
            if ability_key in final_scores:
                final_scores[ability_key] += bonus_value
            else: # Should not happen if base_scores keys are correct
                final_scores[ability_key] = bonus_value 


        session['new_character_data']['ability_scores'] = final_scores
        session['new_character_data']['base_ability_scores'] = base_scores
        # session.modified = True
        flash('Ability scores saved!', 'success')
        return redirect(url_for('main.creation_background')) # Next step

    # GET request
    return render_template('create_character_stats.html',
                           race_name=selected_race.name,
                           class_name=selected_class.name,
                           racial_bonuses_dict=racial_bonuses_dict, # Pass the dict
                           primary_ability=primary_ability,
                           standard_array=standard_array,
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
            # session.modified = True # Ensure session is saved if nested dicts are modified directly

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
        # session.modified = True

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
    # session.modified = True

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
        # session.modified = True

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
        
        # session.modified = True
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
            background_equipment=json.dumps(char_data.get('background_equipment', '')), # Stored as string from background
            current_proficiencies=json.dumps({
                'skills': list(current_skills_set),
                'tools': list(current_tools_set),
                'languages': list(current_languages_set),
                'armor': char_data.get('armor_proficiencies', []),
                'weapons': char_data.get('weapon_proficiencies', []),
                'saving_throws': char_data.get('saving_throw_proficiencies', [])
            }),
            current_equipment=json.dumps(char_data.get('final_equipment', []))
        )

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
