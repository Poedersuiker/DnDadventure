import json
import os
# import google.generativeai as genai # Removed
import google.generativeai as genai # Re-add import
import re # Added for gold parsing
from flask import render_template, redirect, url_for, flash, request, session, get_flashed_messages, jsonify, current_app
from flask_babel import _
from flask_login import login_required, current_user
from app import db
# CharacterSpellSlot removed, CharacterLevel added
from app.models import User, Character, Race, Class, Spell, Setting, Item, Coinage, CharacterLevel 
from app.utils import roll_dice, parse_coinage # Changed import to parse_coinage
from app.gemini import geminiai, GEMINI_DM_SYSTEM_RULES
from datetime import datetime
from app.main import bp

# Placeholder for Gemini API Key Configuration
# GEMINI_API_KEY = "YOUR_API_KEY" # Load this from environment variables in a real app
# genai.configure(api_key=GEMINI_API_KEY)

# Helper constant for ASI key mapping - ensure this matches keys in session['level_up_data']['ability_scores']
ABILITY_NAMES_FULL_SESSION_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']
ABILITY_NAMES_FULL = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']


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
    # character.level = 1 # This field is removed from Character
    # Instead, we might want to remove CharacterLevel entries > 1 if that's the desired logic
    # For now, just resetting log and XP. Level will be derived from CharacterLevel.
    character.current_xp = 0
    character.dm_allowed_level = 1


    # Find the level 1 snapshot
    level_1_data = CharacterLevel.query.filter_by(character_id=character.id, level_number=1).first()
    if level_1_data:
        # If there's a L1 snapshot, this character was properly created under the new system.
        # We might want to clear CharacterLevel entries for levels > 1.
        CharacterLevel.query.filter(CharacterLevel.character_id == character.id, CharacterLevel.level_number > 1).delete()
        current_app.logger.info(f"Character {character_id} progress cleared. Kept Level 1 data, removed other levels.")
    else:
        # This case implies the character might be very old or had issues.
        # For now, we'll log this. A more robust solution might try to create a L1 snapshot.
        current_app.logger.warning(f"Character {character_id} progress cleared, but no Level 1 snapshot found. XP and DM level reset.")

    # Clear items and coinage
    Item.query.filter_by(character_id=character.id).delete()
    Coinage.query.filter_by(character_id=character.id).delete()

    db.session.commit()
    flash('Adventure progress cleared. Your character has been reset. Inventory and coinage have been cleared.', 'success')
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
            return render_template('create_character_race.html', races=[])
        return render_template('create_character_race.html', races=races)
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
        session.modified = True 
        flash(f'{selected_race.name} selected!', 'success')
        return redirect(url_for('main.creation_class')) 
    else:
        flash('Please select a valid race.', 'error')
        races = Race.query.all()
        return render_template('create_character_race.html', races=races)

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
        session.modified = True 
        flash(f'{selected_class.name} selected!', 'success')
        return redirect(url_for('main.creation_stats')) 
    else:
        flash('Please select a valid class.', 'error')
        classes = Class.query.all()
        return render_template('create_character_class.html', classes=classes, race_name=char_data.get('race_name'))

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
        session.pop('new_character_data', None) 
        return redirect(url_for('main.creation_race'))
    racial_bonuses_list = json.loads(selected_race.ability_score_increases or '[]')
    primary_ability = selected_class.spellcasting_ability or "Refer to class features"
    standard_array = [15, 14, 13, 12, 10, 8]
    racial_bonuses_dict = {bonus['name']: bonus['bonus'] for bonus in racial_bonuses_list}
    rolled_stats_from_session = session.get('rolled_stats')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'roll_stats':
            rolled_scores = [roll_dice(4, 6, 1)[0] for _ in range(6)]
            session['rolled_stats'] = rolled_scores
            session.modified = True
            return render_template('create_character_stats.html',
                                   race_name=selected_race.name,
                                   class_name=selected_class.name,
                                   racial_bonuses_dict=racial_bonuses_dict,
                                   primary_ability=primary_ability,
                                   standard_array=standard_array,
                                   rolled_stats=rolled_scores,
                                   submitted_scores=request.form)
        base_scores = {}
        errors = False
        ability_map = {
            'strength': 'STR', 'dexterity': 'DEX', 'constitution': 'CON',
            'intelligence': 'INT', 'wisdom': 'WIS', 'charisma': 'CHA'
        }
        form_scores_to_repopulate = {}
        for form_name, score_key in ability_map.items():
            score_val_str = request.form.get(form_name)
            form_scores_to_repopulate[form_name] = score_val_str
            if not score_val_str:
                flash(f'{form_name.capitalize()} score is required.', 'error')
                errors = True
                continue
            try:
                score = int(score_val_str)
                if not (3 <= score <= 18):
                    flash(f'{form_name.capitalize()} score must be between 3 and 18 before racial modifiers.', 'error')
                    errors = True
                base_scores[score_key] = score
            except ValueError:
                flash(f'Invalid score for {form_name.capitalize()}. Must be a number.', 'error')
                errors = True
        if errors:
            return render_template('create_character_stats.html',
                                   race_name=selected_race.name, 
                                   class_name=selected_class.name, 
                                   racial_bonuses_dict=racial_bonuses_dict, 
                                   primary_ability=primary_ability, 
                                   standard_array=standard_array, 
                                   rolled_stats=session.get('rolled_stats'), 
                                   submitted_scores=form_scores_to_repopulate)
        final_scores = base_scores.copy()
        for bonus_item in racial_bonuses_list:
            ability_key = bonus_item.get('name')
            bonus_value = bonus_item.get('bonus', 0)
            if ability_key in final_scores:
                final_scores[ability_key] += bonus_value
        session['new_character_data']['ability_scores'] = final_scores
        session['new_character_data']['base_ability_scores'] = base_scores
        session.modified = True
        session.pop('rolled_stats', None)
        flash('Ability scores saved!', 'success')
        return redirect(url_for('main.creation_background'))
    return render_template('create_character_stats.html',
                           race_name=selected_race.name,
                           class_name=selected_class.name,
                           racial_bonuses_dict=racial_bonuses_dict,
                           primary_ability=primary_ability,
                           standard_array=standard_array,
                           rolled_stats=rolled_stats_from_session,
                           submitted_scores=None)

sample_backgrounds_data = {
    "Acolyte": {"name": "Acolyte", "skill_proficiencies": ["Insight", "Religion"], "tool_proficiencies": [], "languages": ["Two of your choice"], "equipment": "A holy symbol (a gift to you when you entered the priesthood), a prayer book or prayer wheel, 5 sticks of incense, vestments, a set of common clothes, and a pouch containing 15 gp."},
    "Criminal": {"name": "Criminal (Spy)", "skill_proficiencies": ["Deception", "Stealth"], "tool_proficiencies": ["One type of gaming set", "Thieves' tools"], "languages": [], "equipment": "A crowbar, a set of dark common clothes including a hood, and a pouch containing 15 gp."},
    "Sage": {"name": "Sage", "skill_proficiencies": ["Arcana", "History"], "tool_proficiencies": [], "languages": ["Two of your choice"], "equipment": "A bottle of black ink, a quill, a small knife, a letter from a dead colleague posing a question you have not yet been able to answer, a set of common clothes, and a pouch containing 10 gp."},
    "Soldier": {"name": "Soldier", "skill_proficiencies": ["Athletics", "Intimidation"], "tool_proficiencies": ["One type of gaming set", "Vehicles (land)"], "languages": [], "equipment": "An insignia of rank, a trophy taken from a fallen enemy, a set of bone dice or deck of cards, a set of common clothes, and a pouch containing 10 gp."},
    "Entertainer": {"name": "Entertainer", "skill_proficiencies": ["Acrobatics", "Performance"], "tool_proficiencies": ["Disguise kit", "One type of musical instrument"], "languages": [], "equipment": "A musical instrument (one of your choice), the favor of an admirer (love letter, lock of hair, or trinket), a costume, and a pouch containing 15 gp."}
}

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
            session.modified = True
            flash(f"Background '{chosen_bg_data['name']}' selected.", 'success')
            return redirect(url_for('main.creation_skills'))
        else:
            flash('Please select a valid background.', 'error')
            return render_template('create_character_background.html', race_name=char_data.get('race_name'), class_name=char_data.get('class_name'), backgrounds=sample_backgrounds_data)
    return render_template('create_character_background.html', race_name=char_data.get('race_name'), class_name=char_data.get('class_name'), backgrounds=sample_backgrounds_data)

@bp.route('/creation/skills', methods=['GET', 'POST'])
@login_required
def creation_skills():
    char_data = session.get('new_character_data', {})
    if not char_data.get('background_name'):
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
            return render_template('create_character_skills.html', race_name=char_data.get('race_name'), class_name=selected_class.name, background_name=char_data.get('background_name'), skill_options=skill_options_from_class, num_to_choose=num_skills_to_choose, saving_throws=saving_throw_proficiencies, submitted_skills=chosen_skills)
        session['new_character_data']['class_skill_proficiencies'] = chosen_skills
        session['new_character_data']['armor_proficiencies'] = json.loads(selected_class.proficiencies_armor or '[]')
        session['new_character_data']['weapon_proficiencies'] = json.loads(selected_class.proficiencies_weapons or '[]')
        session['new_character_data']['tool_proficiencies_class_fixed'] = json.loads(selected_class.proficiencies_tools or '[]')
        session['new_character_data']['saving_throw_proficiencies'] = saving_throw_proficiencies
        session.modified = True
        flash('Class skills and proficiencies saved!', 'success')
        return redirect(url_for('main.creation_hp'))
    return render_template('create_character_skills.html', race_name=char_data.get('race_name'), class_name=selected_class.name, background_name=char_data.get('background_name'), skill_options=skill_options_from_class, num_to_choose=num_skills_to_choose, saving_throws=saving_throw_proficiencies, submitted_skills=[])

@bp.route('/creation/hp', methods=['GET'])
@login_required
def creation_hp():
    char_data = session.get('new_character_data', {})
    if not char_data.get('armor_proficiencies') and not char_data.get('class_skill_proficiencies'):
        flash('Please complete the skills and proficiencies step first.', 'error')
        return redirect(url_for('main.creation_skills'))
    required_keys = ['race_id', 'class_id', 'ability_scores']
    if not all(key in char_data for key in required_keys):
        flash('Missing critical data (race, class, or scores). Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))
    selected_race = Race.query.get(char_data['race_id'])
    selected_class = Class.query.get(char_data['class_id'])
    ability_scores = char_data.get('ability_scores', {})
    if not selected_race or not selected_class:
        flash('Selected race or class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))
    if not ability_scores.get('CON') or not ability_scores.get('DEX'):
        flash('Constitution or Dexterity scores not found. Please complete the stats step.', 'error')
        return redirect(url_for('main.creation_stats'))
    con_score = ability_scores.get('CON', 10)
    con_modifier = (con_score - 10) // 2
    try:
        hit_die_value = int(selected_class.hit_die[1:]) if selected_class.hit_die else 8
    except (ValueError, TypeError, IndexError):
        flash('Error parsing hit die for the class. Defaulting HP calculation.', 'warning')
        hit_die_value = 8
    max_hp = hit_die_value + con_modifier
    dex_score = ability_scores.get('DEX', 10)
    dex_modifier = (dex_score - 10) // 2
    ac_base = 10 + dex_modifier
    speed = selected_race.speed
    session['new_character_data']['max_hp'] = max_hp
    session['new_character_data']['current_hp'] = max_hp
    session['new_character_data']['armor_class_base'] = ac_base
    session['new_character_data']['speed'] = speed
    session.modified = True
    return render_template('create_character_hp.html', race_name=selected_race.name, class_name=selected_class.name, background_name=char_data.get('background_name', 'N/A'), ability_scores_summary=ability_scores, max_hp=max_hp, ac_base=ac_base, speed=speed)

def parse_starting_equipment(starting_equipment_data_json):
    fixed_items = []
    choice_groups = []
    if not starting_equipment_data_json:
        return fixed_items, choice_groups
    starting_equipment_data = json.loads(starting_equipment_data_json)
    for i, item_or_choice in enumerate(starting_equipment_data):
        if 'equipment' in item_or_choice and 'quantity' in item_or_choice:
            fixed_items.append(item_or_choice)
        elif 'choose' in item_or_choice and 'from' in item_or_choice:
            options_list = []
            actual_options_source = item_or_choice['from'].get('options', [])
            for opt in actual_options_source:
                if opt.get('option_type') == 'counted_reference' and 'of' in opt:
                    options_list.append({"name": opt['of'].get('name', opt['of'].get('index', 'Unknown Item')), "index": opt['of'].get('index', 'unknown-item-' + str(i)), "quantity": opt.get('count', 1)})
                elif opt.get('option_type') == 'reference' and 'item' in opt:
                     options_list.append({"name": opt['item'].get('name', opt['item'].get('index', 'Unknown Item')), "index": opt['item'].get('index', 'unknown-item-' + str(i)), "quantity": 1})
            if options_list:
                choice_groups.append({"id": f"choice_{i}", "desc": item_or_choice.get('desc', f"Choose {item_or_choice['choose']}"), "choose": item_or_choice['choose'], "options": options_list})
    return fixed_items, choice_groups

@bp.route('/creation/equipment', methods=['GET', 'POST'])
@login_required
def creation_equipment():
    char_data = session.get('new_character_data', {})
    if not char_data.get('max_hp'):
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
        for item_data in fixed_items:
            if item_data.get('equipment'):
                item_name = item_data['equipment'].get('name', item_data['equipment'].get('index', 'Unknown Fixed Item'))
                chosen_equipment_list.append(f"{item_name} (x{item_data.get('quantity', 1)})")
        for group in choice_groups:
            group_id = group['id']
            if group['choose'] == 1:
                selected_option_index = request.form.get(group_id)
                if selected_option_index:
                    found_option = next((opt for opt in group['options'] if opt['index'] == selected_option_index), None)
                    if found_option:
                        chosen_equipment_list.append(f"{found_option['name']} (x{found_option.get('quantity',1)})")
        if background_equipment_string:
            chosen_equipment_list.append(f"Background: {background_equipment_string}")
        session['new_character_data']['final_equipment'] = chosen_equipment_list
        session.modified = True
        flash('Starting equipment chosen!', 'success')
        if selected_class.spellcasting_ability:
            return redirect(url_for('main.creation_spells'))
        else:
            return redirect(url_for('main.creation_review'))
    return render_template('create_character_equipment.html', race_name=char_data.get('race_name'), class_name=selected_class.name, background_name=char_data.get('background_name'), fixed_items=fixed_items, choice_groups=choice_groups, background_equipment_string=background_equipment_string)

@bp.route('/creation/spells', methods=['GET', 'POST'])
@login_required
def creation_spells():
    char_data = session.get('new_character_data', {})
    if not char_data.get('final_equipment'):
        flash('Please complete the equipment step first.', 'error')
        return redirect(url_for('main.creation_equipment'))
    selected_class = Class.query.get(char_data.get('class_id'))
    if not selected_class:
        flash('Selected class not found. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))
    if not selected_class.spellcasting_ability:
        return redirect(url_for('main.creation_review'))
    num_cantrips_to_select = 0
    num_level_1_spells_to_select = 0
    class_name = selected_class.name
    if class_name == "Wizard":
        num_cantrips_to_select = 3
        num_level_1_spells_to_select = 6
    elif class_name == "Sorcerer":
        num_cantrips_to_select = 4
        num_level_1_spells_to_select = 2
    elif class_name == "Bard":
        num_cantrips_to_select = 2
        num_level_1_spells_to_select = 4
    elif class_name == "Cleric":
        num_cantrips_to_select = 3
        num_level_1_spells_to_select = 0
    elif class_name == "Druid":
        num_cantrips_to_select = 2
        num_level_1_spells_to_select = 0
    elif class_name == "Warlock":
        num_cantrips_to_select = 2
        num_level_1_spells_to_select = 2
    search_pattern = f'%"{selected_class.name}"%'
    available_cantrips = Spell.query.filter(Spell.level == 0, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all()
    available_level_1_spells = Spell.query.filter(Spell.level == 1, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all()
    if num_cantrips_to_select == 0 and num_level_1_spells_to_select == 0 and request.method == 'GET':
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
            return render_template('create_character_spells.html', race_name=char_data.get('race_name'), class_name=selected_class.name, background_name=char_data.get('background_name'), available_cantrips=available_cantrips, num_cantrips_to_select=num_cantrips_to_select, available_level_1_spells=available_level_1_spells, num_level_1_spells_to_select=num_level_1_spells_to_select, submitted_cantrips=chosen_cantrip_ids_str, submitted_level_1_spells=chosen_level_1_spell_ids_str)
        try:
            session['new_character_data']['chosen_cantrip_ids'] = [int(id_str) for id_str in chosen_cantrip_ids_str]
            session['new_character_data']['chosen_level_1_spell_ids'] = [int(id_str) for id_str in chosen_level_1_spell_ids_str]
        except ValueError:
            flash('Invalid spell ID submitted. Please try again.', 'error')
            return render_template('create_character_spells.html', race_name=char_data.get('race_name'), class_name=selected_class.name, background_name=char_data.get('background_name'), available_cantrips=available_cantrips, num_cantrips_to_select=num_cantrips_to_select, available_level_1_spells=available_level_1_spells, num_level_1_spells_to_select=num_level_1_spells_to_select, submitted_cantrips=chosen_cantrip_ids_str, submitted_level_1_spells=chosen_level_1_spell_ids_str)
        session.modified = True
        flash('Spells selected!', 'success')
        return redirect(url_for('main.creation_review'))
    return render_template('create_character_spells.html', race_name=char_data.get('race_name'), class_name=selected_class.name, background_name=char_data.get('background_name'), available_cantrips=available_cantrips, num_cantrips_to_select=num_cantrips_to_select, available_level_1_spells=available_level_1_spells, num_level_1_spells_to_select=num_level_1_spells_to_select, submitted_cantrips=[], submitted_level_1_spells=[])

@bp.route('/creation/review', methods=['GET', 'POST'])
@login_required
def creation_review():
    char_data = session.get('new_character_data', {})
    if not char_data.get('ability_scores'):
        flash('Please complete the core character creation steps first, starting with ability scores.', 'error')
        return redirect(url_for('main.creation_stats')) 
    race = Race.query.get(char_data.get('race_id'))
    char_class_obj = Class.query.get(char_data.get('class_id')) 
    if not race or not char_class_obj:
        flash('Race or Class data missing or invalid. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))
    cantrips = Spell.query.filter(Spell.id.in_(char_data.get('chosen_cantrip_ids', []))).all()
    level_1_spells = Spell.query.filter(Spell.id.in_(char_data.get('chosen_level_1_spell_ids', []))).all()
    all_skill_proficiencies = set(char_data.get('background_skill_proficiencies', []))
    all_skill_proficiencies.update(char_data.get('class_skill_proficiencies', []))
    all_tool_proficiencies = set(char_data.get('background_tool_proficiencies', []))
    all_tool_proficiencies.update(char_data.get('tool_proficiencies_class_fixed', []))
    all_language_proficiencies = set(char_data.get('background_languages', []))
    if request.method == 'POST':
        character_name = request.form.get('character_name')
        alignment = request.form.get('alignment')
        char_description = request.form.get('character_description')
        if not character_name:
            flash('Character name is required.', 'error')
            return render_template('create_character_review.html', data=char_data, race=race, char_class=char_class_obj, cantrips=cantrips, level_1_spells=level_1_spells, all_skill_proficiencies=list(all_skill_proficiencies), all_tool_proficiencies=list(all_tool_proficiencies), all_language_proficiencies=list(all_language_proficiencies), submitted_name=character_name, submitted_alignment=alignment, submitted_description=char_description)
        current_skills_set = set(char_data.get('background_skill_proficiencies', []))
        current_skills_set.update(char_data.get('class_skill_proficiencies', []))
        current_tools_set = set(char_data.get('background_tool_proficiencies', []))
        current_tools_set.update(char_data.get('tool_proficiencies_class_fixed', []))
        current_languages_set = set(char_data.get('background_languages', []))
        new_char = Character(
            name=character_name,
            description=char_description,
            user_id=current_user.id,
            race_id=char_data.get('race_id'),
            class_id=char_data.get('class_id'),
            alignment=alignment,
            background_name=char_data.get('background_name'),
            background_proficiencies=json.dumps( 
                char_data.get('background_skill_proficiencies', []) +
                char_data.get('background_tool_proficiencies', []) +
                char_data.get('background_languages', [])
            ),
            adventure_log=json.dumps([]), 
            dm_allowed_level=1,
            current_xp=0
        )
        db.session.add(new_char)
        db.session.flush() 
        level_1_proficiencies = {
            'skills': list(current_skills_set),
            'tools': list(current_tools_set),
            'languages': list(current_languages_set), 
            'armor': char_data.get('armor_proficiencies', []),
            'weapons': char_data.get('weapon_proficiencies', []),
            'saving_throws': char_data.get('saving_throw_proficiencies', [])
        }
        spell_slots_L1 = {}
        if char_class_obj and char_class_obj.spell_slots_by_level:
            try:
                all_class_level_slots = json.loads(char_class_obj.spell_slots_by_level)
                slots_for_char_level_1_list = all_class_level_slots.get("1") 
                if slots_for_char_level_1_list:
                    for spell_lvl_idx, num_slots in enumerate(slots_for_char_level_1_list):
                        if num_slots > 0: 
                            spell_slots_L1[str(spell_lvl_idx + 1)] = num_slots
            except json.JSONDecodeError:
                current_app.logger.error(f"Failed to parse spell_slots_by_level for class {char_class_obj.name}")
        ability_scores_from_session = char_data.get('ability_scores', {})
        new_char_level_1 = CharacterLevel(
            character_id=new_char.id,
            level_number=1,
            xp_at_level_up=0,
            strength=ability_scores_from_session.get('STR', 10),
            dexterity=ability_scores_from_session.get('DEX', 10),
            constitution=ability_scores_from_session.get('CON', 10),
            intelligence=ability_scores_from_session.get('INT', 10),
            wisdom=ability_scores_from_session.get('WIS', 10),
            charisma=ability_scores_from_session.get('CHA', 10),
            hp=char_data.get('max_hp', 0),
            max_hp=char_data.get('max_hp', 0),
            armor_class=char_data.get('armor_class_base'),
            hit_dice_rolled="Max HP at L1", 
            proficiencies=json.dumps(level_1_proficiencies),
            features_gained=json.dumps(["Initial class features", "Initial race features"]), 
            spells_known_ids=json.dumps(char_data.get('chosen_cantrip_ids', []) + char_data.get('chosen_level_1_spell_ids', [])),
            spells_prepared_ids=json.dumps([]), 
            spell_slots_snapshot=json.dumps(spell_slots_L1),
            created_at=datetime.utcnow()
        )
        db.session.add(new_char_level_1)
        final_equipment_from_session = char_data.get('final_equipment', [])
        background_equipment_str = char_data.get('background_equipment', '') 
        parsed_coins = parse_coinage(background_equipment_str)
        for coin_type, quantity in parsed_coins.items():
            if quantity > 0:
                coin_name = f"{coin_type.title()} Pieces" 
                coin_entry = Coinage(name=coin_name, quantity=quantity, character_id=new_char.id)
                db.session.add(coin_entry)
        all_item_strings_to_parse = []
        if background_equipment_str:
            potential_bg_items = re.split(r',\s*|\s+and\s+', background_equipment_str)
            for p_item in potential_bg_items:
                p_item_clean = p_item.strip()
                if "gp" in p_item_clean.lower() or "gold pieces" in p_item_clean.lower() or "gold" in p_item_clean.lower():
                    continue 
                if p_item_clean and not p_item_clean.lower().startswith("a pouch containing"): 
                    all_item_strings_to_parse.append(p_item_clean)
        for item_string_from_session in final_equipment_from_session:
            if item_string_from_session.lower().startswith("background:"):
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
        aggregated_items = {}
        for item_string in all_item_strings_to_parse:
            item_name_raw = item_string
            quantity = 1
            description = "Starting equipment" 
            qty_match_suffix = re.match(r'^(.*?)\s*\(x(\d+)\)$', item_string) 
            qty_match_prefix = re.match(r'(\d+)\s+(.*)', item_string)   
            if qty_match_suffix:
                item_name_raw = qty_match_suffix.group(1).strip()
                quantity = int(qty_match_suffix.group(2))
            elif qty_match_prefix:
                quantity = int(qty_match_prefix.group(1))
                item_name_raw = qty_match_prefix.group(2).strip()
            normalized_item_name = item_name_raw.strip().title()
            if not normalized_item_name: 
                continue
            if normalized_item_name in aggregated_items:
                aggregated_items[normalized_item_name]['quantity'] += quantity
                if aggregated_items[normalized_item_name]['description'] == "Starting equipment" and description != "Starting equipment":
                    aggregated_items[normalized_item_name]['description'] = description
            else:
                aggregated_items[normalized_item_name] = {'quantity': quantity, 'description': description }
        for name, data in aggregated_items.items():
            item = Item(name=name, quantity=data['quantity'], character_id=new_char.id, description=data['description'])
            db.session.add(item)
        db.session.commit() 
        session.pop('new_character_data', None) 
        flash('Character created successfully!', 'success')
        return redirect(url_for('main.index'))
    return render_template('create_character_review.html', data=char_data, race=race, char_class=char_class_obj, cantrips=cantrips, level_1_spells=level_1_spells, all_skill_proficiencies=list(all_skill_proficiencies), all_tool_proficiencies=list(all_tool_proficiencies), all_language_proficiencies=list(all_language_proficiencies), submitted_name=char_data.get('character_name_draft',''), submitted_alignment=char_data.get('alignment_draft',''), submitted_description=char_data.get('description_draft',''))

ALL_SKILLS_LIST = [
    ("Acrobatics", "DEX"), ("Animal Handling", "WIS"), ("Arcana", "INT"),
    ("Athletics", "STR"), ("Deception", "CHA"), ("History", "INT"),
    ("Insight", "WIS"), ("Intimidation", "CHA"), ("Investigation", "INT"),
    ("Medicine", "WIS"), ("Nature", "INT"), ("Perception", "WIS"),
    ("Performance", "CHA"), ("Persuasion", "CHA"), ("Religion", "INT"),
    ("Sleight of Hand", "DEX"), ("Stealth", "DEX"), ("Survival", "WIS")
]
# ABILITY_NAMES_FULL is defined a bit lower, but used by get_character_level_data.
# For consistency and to avoid potential NameError if functions are ever reordered, define it here.
# ABILITY_NAMES_FULL = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma'] # Defined globally now


@bp.route('/<int:character_id>/adventure', methods=['GET', 'POST'])
@login_required
def adventure(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash(_('This character does not belong to you.'))
        return redirect(url_for('main.index'))

    # Fetch all level records for the character to determine current and achieved levels
    character_levels = CharacterLevel.query.filter_by(character_id=character.id).order_by(CharacterLevel.level_number).all()
    
    if not character_levels:
        # This case should ideally not happen if characters are created with a level 1 entry.
        flash(_("Character has no level data. Please contact support or try resetting the character."), 'error')
        return redirect(url_for('main.index'))

    achieved_levels_list = sorted(list(set(cl.level_number for cl in character_levels)))
    current_actual_level = achieved_levels_list[-1] if achieved_levels_list else 1
    
    # Fetch the CharacterLevel data for the current actual level
    # For now, we always display the current actual level. Future changes might allow viewing past levels.
    viewed_level_number = current_actual_level 
    current_character_level_data = None
    for cl_data in character_levels:
        if cl_data.level_number == viewed_level_number:
            current_character_level_data = cl_data
            break
    
    if not current_character_level_data:
        # This is a critical error if current_actual_level was determined but no matching record found.
        flash(_("Could not load level-specific data for your character's current level. Please contact support."), 'error')
        return redirect(url_for('main.index'))

    # --- Spell Slot Management LOGIC REMOVED ---
    # Spell slots are now part of CharacterLevel.spell_slots_snapshot

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
            initial_prompt_proficiencies = json.loads(current_character_level_data.proficiencies or '{}')
            temp_skills_str = ", ".join(initial_prompt_proficiencies.get('skills', [])) or "None"
            temp_saving_throws_str = ", ".join(initial_prompt_proficiencies.get('saving_throws', [])) or "None"
            temp_armor_prof_str = ", ".join(initial_prompt_proficiencies.get('armor', [])) or "None"
            temp_weapon_prof_str = ", ".join(initial_prompt_proficiencies.get('weapons', [])) or "None"
            temp_tool_prof_str = ", ".join(initial_prompt_proficiencies.get('tools', [])) or "None"
            temp_languages_str = ", ".join(initial_prompt_proficiencies.get('languages', [])) or "None"

            items_list_for_prompt = [f"{item.name} (x{item.quantity})" + (f" - {item.description}" if item.description else "") for item in character.items]
            coinage_list_for_prompt = [f"{coin.quantity} {coin.name}" for coin in character.coinage]
            full_equipment_list_for_prompt = items_list_for_prompt + coinage_list_for_prompt
            temp_equipment_str = "\n".join([f"- {item_str}" for item_str in full_equipment_list_for_prompt]) if full_equipment_list_for_prompt else "None"
            
            xp_thresholds = {1: 300, 2: 900, 3: 2700, 4: 6500, 5: 14000, 6: 23000, 7: 34000, 8: 48000, 9: 64000, 10: 85000, 11: 100000, 12: 120000, 13: 140000, 14: 165000, 15: 195000, 16: 225000, 17: 265000, 18: 305000, 19: 355000}
            xp_for_next = xp_thresholds.get(current_actual_level, "N/A for current level")

            character_sheet_prompt = (
                f"PLAYER CHARACTER SHEET:\n"
                f"Name: {character.name}\n"
                f"Race: {character.race.name if character.race else 'N/A'}\n"
                f"Class: {character.char_class.name if character.char_class else 'N/A'}\n"
                f"Level: {current_actual_level}\n\n" 
                f"Ability Scores:\n"
                f"  Strength: {current_character_level_data.strength}\n"
                f"  Dexterity: {current_character_level_data.dexterity}\n"
                f"  Constitution: {current_character_level_data.constitution}\n"
                f"  Intelligence: {current_character_level_data.intelligence}\n"
                f"  Wisdom: {current_character_level_data.wisdom}\n"
                f"  Charisma: {current_character_level_data.charisma}\n\n"
                f"Combat Stats:\n"
                f"  HP: {current_character_level_data.hp}/{current_character_level_data.max_hp}\n"
                f"  Armor Class: {current_character_level_data.armor_class}\n\n"
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
                f"  Current XP: {character.current_xp or 0}\n" 
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
    proficiency_bonus = (viewed_level_number - 1) // 4 + 2

    proficiencies_data = {}
    try:
        proficiencies_data = json.loads(current_character_level_data.proficiencies or '{}')
        if not isinstance(proficiencies_data, dict): 
            proficiencies_data = {}
            current_app.logger.warning(f"Proficiencies for char {character_id} L{viewed_level_number} was not a dict, reset to empty.")
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse proficiencies JSON for char {character_id} L{viewed_level_number}: {current_character_level_data.proficiencies}")
        proficiencies_data = {}

    proficient_skills = proficiencies_data.get('skills', [])
    proficient_tools = proficiencies_data.get('tools', [])
    proficient_languages = proficiencies_data.get('languages', [])
    proficient_armor = proficiencies_data.get('armor', [])
    proficient_weapons = proficiencies_data.get('weapons', [])
    proficient_saving_throws = proficiencies_data.get('saving_throws', [])

    character_items = character.items
    character_coinage = character.coinage

    spells_by_level = {}
    known_spell_ids = []
    if current_character_level_data.spells_known_ids:
        try:
            known_spell_ids = json.loads(current_character_level_data.spells_known_ids)
        except json.JSONDecodeError:
            current_app.logger.error(f"Failed to parse spells_known_ids for char {character_id} L{viewed_level_number}")
    
    if known_spell_ids:
        known_spells_objects = Spell.query.filter(Spell.id.in_(known_spell_ids)).all()
        for spell in known_spells_objects:
            if spell.level not in spells_by_level:
                spells_by_level[spell.level] = []
            spells_by_level[spell.level].append(spell)
        for level in spells_by_level:
            spells_by_level[level].sort(key=lambda s: s.name)

    spell_slots_data = {}
    if current_character_level_data.spell_slots_snapshot:
        try:
            spell_slots_data = json.loads(current_character_level_data.spell_slots_snapshot)
        except json.JSONDecodeError:
            current_app.logger.error(f"Failed to parse spell_slots_snapshot for char {character_id} L{viewed_level_number}")

    saving_throws_data = []
    for ability_name_full in ABILITY_NAMES_FULL:
        ability_attr_lower = ability_name_full.lower()
        ability_attr_short = ability_name_full[:3].upper()
        base_score = getattr(current_character_level_data, ability_attr_lower, 10)
        base_modifier = (base_score - 10) // 2
        is_proficient = ability_attr_short in proficient_saving_throws
        final_modifier = base_modifier + proficiency_bonus if is_proficient else base_modifier
        saving_throws_data.append({
            "name": ability_name_full,
            "attribute_short": ability_attr_short,
            "modifier": final_modifier,
            "is_proficient": is_proficient
        })

    skills_data = []
    ability_abbr_to_attr_lower = {
        "STR": "strength", "DEX": "dexterity", "CON": "constitution",
        "INT": "intelligence", "WIS": "wisdom", "CHA": "charisma"
    }
    for skill_name, skill_ability_abbr in ALL_SKILLS_LIST:
        ability_attr_lower = ability_abbr_to_attr_lower.get(skill_ability_abbr)
        base_score = getattr(current_character_level_data, ability_attr_lower, 10) if ability_attr_lower else 10
        base_modifier = (base_score - 10) // 2
        is_proficient = skill_name in proficient_skills
        final_modifier = base_modifier + proficiency_bonus if is_proficient else base_modifier
        skills_data.append({
            "name": skill_name,
            "ability_abbr": skill_ability_abbr,
            "modifier": final_modifier,
            "is_proficient": is_proficient
        })

    abilities_data = []
    ability_full_to_short_map = {
        'Strength': 'STR', 'Dexterity': 'DEX', 'Constitution': 'CON',
        'Intelligence': 'INT', 'Wisdom': 'WIS', 'Charisma': 'CHA'
    }
    for ability_name_full in ABILITY_NAMES_FULL:
        attr_lower = ability_name_full.lower()
        score = getattr(current_character_level_data, attr_lower, 10)
        modifier = (score - 10) // 2
        abilities_data.append({
            "name_full": ability_name_full,
            "name_short": ability_full_to_short_map.get(ability_name_full, "UNK"),
            "score": score,
            "modifier": modifier
        })
    
    return render_template('adventure.html', 
                           title=_('Adventure'),
                           character=character, # Still pass the main character object
                           current_character_level_data=current_character_level_data, # Pass the specific level data
                           log_entries=log_entries,
                           all_skills_list=ALL_SKILLS_LIST, 
                           ability_names_full=ABILITY_NAMES_FULL, 
                           proficiency_bonus=proficiency_bonus,
                           # The following are now derived from current_character_level_data or calculated directly
                           proficient_skills=proficient_skills, 
                           proficient_saving_throws=proficient_saving_throws,
                           proficient_tools=proficient_tools,
                           proficient_languages=proficient_languages,
                           proficient_armor=proficient_armor,
                           proficient_weapons=proficient_weapons,
                           character_items=character_items,
                           character_coinage=character_coinage,
                           spells_by_level=spells_by_level,
                           spell_slots_data=spell_slots_data, # This is now a dict from JSON
                           saving_throws_data=saving_throws_data,
                           skills_data=skills_data,
                           abilities_data=abilities_data,
                           # New context variables
                           current_actual_level=current_actual_level,
                           dm_allowed_level=character.dm_allowed_level,
                           achieved_levels_list=achieved_levels_list
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

    # Add user message to log first
    log_entries.append({"sender": "user", "text": user_message})

    original_ai_response_text = ai_response_text # Keep a copy for the return value if not modified for display

    if ai_response_text:
        # Check for level-up command
        # Using re.MULTILINE and ^$ to ensure the command is on its own line.
        # Adjusted regex to capture potential preceding/succeeding newlines to remove the line cleanly.
        levelup_pattern = r"^(SYSTEM: LEVELUP GRANTED TO LEVEL (\d+))\s*$"
        levelup_match = re.search(levelup_pattern, ai_response_text, re.IGNORECASE | re.MULTILINE)

        if levelup_match:
            command_full_line = levelup_match.group(0) # The whole line e.g., "SYSTEM: LEVELUP GRANTED TO LEVEL 2\n"
            extracted_level_str = levelup_match.group(2)
            try:
                extracted_level_int = int(extracted_level_str)
                character.dm_allowed_level = extracted_level_int
                # db.session.add(character) # Character is already in session, commit will save it.
                
                system_message_text = _("Congratulations! You can now advance to Level %(level)s.", level=extracted_level_int)
                log_entries.append({"sender": "system", "text": system_message_text})
                current_app.logger.info(f"Level up to {extracted_level_int} granted for character {character_id}.")

                # Remove the command line from ai_response_text for display
                ai_response_text = ai_response_text.replace(command_full_line, "").strip()
                
            except ValueError:
                current_app.logger.error(f"Extracted level '{extracted_level_str}' is not a valid integer for character {character_id}.")
        
        # Add DM's response to log if it's not empty after potentially stripping the command
        if ai_response_text and not ai_response_text.isspace():
            log_entries.append({"sender": "dm", "text": ai_response_text})
        elif not levelup_match: # If no level up command and response is empty/whitespace
             current_app.logger.warning(f"AI response was empty or whitespace for char {character_id}. User message: '{user_message}'")
             # This case will be handled by the final check for original_ai_response_text below

    character.adventure_log = json.dumps(log_entries)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to commit chat message and/or level up to DB for char {character_id}: {str(e)}")
        db.session.rollback()
        return jsonify(error=_("An error occurred saving your conversation to the chronicles.")), 500

    # Return the original AI response (or parts of it if command was stripped but other text remained)
    # If original_ai_response_text was None or empty, and no system message was added, this could still be an issue.
    # The check below handles if the AI truly sent nothing.
    if original_ai_response_text:
         # If we stripped the command and ai_response_text became empty,
         # we should still return a success, but the 'reply' might be empty.
         # The system message in log_entries is the main notification for level up.
         # The client will receive original_ai_response_text (which may or may not include the command line based on UX preference)
         # For this implementation, we send back the potentially modified ai_response_text (command stripped).
         # If UX prefers to see the command, send original_ai_response_text.
         # Let's send back the version *without* the command for cleaner display.
        return jsonify(reply=ai_response_text if ai_response_text and not ai_response_text.isspace() else _("DM's message processed.")), 200
    else: # AI genuinely sent no text and no error occurred
        current_app.logger.warning(f"Received no text and no error from geminiai for char {character_id}. User message: '{user_message}'")
        return jsonify(reply=_("The Dungeon Master ponders your words but remains silent for now...")), 200


@bp.route('/character/<int:character_id>/inventory/add_item', methods=['POST'])
@login_required
def add_item_to_inventory(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized: You do not own this character."), 403

    data = request.json
    if not data:
        return jsonify(status="error", message="No data provided."), 400

    item_name = data.get('item_name', '').strip().title()
    item_description = data.get('item_description', '').strip()
    
    try:
        item_quantity_str = data.get('item_quantity')
        if item_quantity_str is None: # Field not sent
            return jsonify(status="error", message="Item quantity is required."), 400
        item_quantity = int(item_quantity_str)
    except ValueError:
        return jsonify(status="error", message="Invalid quantity format. Must be a number."), 400
    except TypeError: # Handles if item_quantity_str is None and int() fails (already caught by check above but good for safety)
        return jsonify(status="error", message="Item quantity must be a valid number."), 400

    if not item_name:
        return jsonify(status="error", message="Item name cannot be empty."), 400
    
    if item_quantity <= 0:
        return jsonify(status="error", message="Item quantity must be positive."), 400

    existing_item = Item.query.filter_by(character_id=character.id, name=item_name).first()
    item_for_response = None
    status_code = 200 # Default to 200 (OK)

    if existing_item:
        existing_item.quantity += item_quantity
        item_for_response = existing_item
        message = f'{item_quantity} {item_name}(s) added. You now have {existing_item.quantity}.'
    else:
        new_item = Item(
            name=item_name,
            description=item_description,
            quantity=item_quantity,
            character_id=character.id
        )
        db.session.add(new_item)
        # We need to flush to get the ID for the new_item if we want to return it
        # However, if we commit here, a rollback for a potential outer transaction might be an issue.
        # For now, let's assume this is an atomic operation. If not, we might need to adjust.
        # A common pattern is to commit and then query the item, or ensure the ORM populates the ID after add+flush.
        # For simplicity, we'll commit and then use the new_item object.
        # db.session.flush() # Or commit later, see note below
        item_for_response = new_item
        message = f'{item_name} (x{item_quantity}) added to inventory.'
        status_code = 201 # 201 (Created) for new resource
    
    try:
        db.session.commit()
        # Ensure item_for_response is populated for the JSON, especially its ID after commit
        # If it was a new_item, its ID is now populated.
        return jsonify(
            status="success", 
            message=message,
            item={
                'id': item_for_response.id,
                'name': item_for_response.name,
                'quantity': item_for_response.quantity,
                'description': item_for_response.description
            }
        ), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding/updating item for character {character_id}: {str(e)}")
        return jsonify(status="error", message="An internal error occurred while saving the item."), 500


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
        return jsonify(status="error", message="Unauthorized: You do not own this character."), 403

    data = request.json
    if not data:
        return jsonify(status="error", message="No data provided."), 400

    coin_quantities = {}
    coin_keys = ["gold_quantity", "silver_quantity", "copper_quantity"]
    db_coin_names = {
        "gold_quantity": "Gold Pieces",
        "silver_quantity": "Silver Pieces",
        "copper_quantity": "Copper Pieces"
    }

    for key in coin_keys:
        if key not in data:
            return jsonify(status="error", message=f"Missing '{key}' in request."), 400
        try:
            quantity = int(data[key])
            if quantity < 0:
                return jsonify(status="error", message=f"Quantity for {db_coin_names[key]} must be non-negative."), 400
            coin_quantities[key] = quantity
        except (ValueError, TypeError):
            return jsonify(status="error", message=f"Invalid quantity for {db_coin_names[key]}. Must be an integer."), 400
    
    updated_any = False
    updated_coin_details = [] # To send back the state of coins after update

    for key, quantity in coin_quantities.items():
        db_name = db_coin_names[key]
        existing_coinage = Coinage.query.filter_by(character_id=character.id, name=db_name).first()

        if existing_coinage:
            if quantity > 0:
                if existing_coinage.quantity != quantity:
                    existing_coinage.quantity = quantity
                    updated_any = True
                updated_coin_details.append({'name': db_name, 'quantity': existing_coinage.quantity})
            else: # quantity is 0
                db.session.delete(existing_coinage)
                updated_any = True
                # No details to append for deleted coin, or could append with quantity 0
        elif quantity > 0: # No existing record, but new quantity is positive
            new_coinage_entry = Coinage(name=db_name, quantity=quantity, character_id=character.id)
            db.session.add(new_coinage_entry)
            updated_any = True
            # To get ID, we'd need to flush or commit. For now, just return name/qty.
            updated_coin_details.append({'name': db_name, 'quantity': new_coinage_entry.quantity})
            
    if updated_any:
        try:
            db.session.commit()
            # Re-fetch to ensure all data is current, especially if new items were added.
            # This is a bit inefficient but ensures data consistency for the response.
            # A more optimized way might involve only adding/updating specific items in updated_coin_details.
            final_coinage_state = []
            for _, db_name_iter in db_coin_names.items():
                coin_obj = Coinage.query.filter_by(character_id=character.id, name=db_name_iter).first()
                if coin_obj:
                    final_coinage_state.append({'name': coin_obj.name, 'quantity': coin_obj.quantity})
                else: # Ensure all types are represented, even if 0
                    final_coinage_state.append({'name': db_name_iter, 'quantity': 0})

            return jsonify(status="success", message="Coinage updated successfully.", coinage=final_coinage_state), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating coinage for character {character_id}: {str(e)}")
            return jsonify(status="error", message="An internal error occurred while updating coinage."), 500
    else:
        # Even if no changes, return current state for consistency
        current_coinage_state = []
        for _, db_name_iter in db_coin_names.items():
            coin_obj = Coinage.query.filter_by(character_id=character.id, name=db_name_iter).first()
            if coin_obj:
                current_coinage_state.append({'name': coin_obj.name, 'quantity': coin_obj.quantity})
            else:
                current_coinage_state.append({'name': db_name_iter, 'quantity': 0})
        return jsonify(status="success", message="No changes detected in coinage amounts.", coinage=current_coinage_state), 200


@bp.route('/character/<int:character_id>/inventory/edit_item/<int:item_id>', methods=['POST'])
@login_required
def edit_item_in_inventory(character_id, item_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized: You do not own this character."), 403

    item_to_edit = Item.query.filter_by(id=item_id, character_id=character.id).first()
    if not item_to_edit:
        return jsonify(status="error", message="Item not found or does not belong to this character."), 404

    data = request.json
    if not data:
        return jsonify(status="error", message="No data provided."), 400

    new_name = data.get('item_name', '').strip().title()
    new_description = data.get('item_description', '').strip()
    
    try:
        new_quantity_str = data.get('item_quantity')
        if new_quantity_str is None: # Field not sent
             return jsonify(status="error", message="Item quantity is required."), 400
        new_quantity = int(new_quantity_str)
    except ValueError:
        return jsonify(status="error", message="Invalid quantity format. Must be a number."), 400
    except TypeError: # Handles if new_quantity_str is None and int() fails
        return jsonify(status="error", message="Item quantity must be a valid number."), 400


    if not new_name:
        return jsonify(status="error", message="Item name cannot be empty."), 400
    
    if new_quantity <= 0:
        # If quantity is zero or less, client should use remove_item route.
        # For edit, we expect a positive quantity.
        return jsonify(status="error", message="Item quantity must be positive. To remove an item, use the remove function."), 400

    item_to_edit.name = new_name
    item_to_edit.description = new_description
    item_to_edit.quantity = new_quantity

    try:
        db.session.commit()
        return jsonify(
            status="success", 
            message="Item updated successfully!", 
            item={
                'id': item_to_edit.id,
                'name': item_to_edit.name,
                'quantity': item_to_edit.quantity,
                'description': item_to_edit.description
            }
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating item {item_id} for character {character_id}: {str(e)}")
        return jsonify(status="error", message="An internal error occurred while updating the item."), 500


# --- Spell Slot and Rest Management Routes ---

@bp.route('/character/<int:character_id>/spellslot/use/<int:spell_level>', methods=['POST'])
@login_required
def use_spell_slot(character_id, spell_level):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    # spell_slot_info = CharacterSpellSlot.query.filter_by(
    #     character_id=character.id,
    #     spell_level=spell_level
    # ).first()
    spell_slot_info = None # Placeholder

    # if spell_slot_info and spell_slot_info.slots_used < spell_slot_info.slots_total:
        # spell_slot_info.slots_used += 1
    current_app.logger.warning(f"Spell slot usage for char {character_id}, level {spell_level} - LOGIC TEMPORARILY DISABLED.")
    if False: # Keep structure, effectively disable
        try:
            db.session.commit()
            return jsonify(
                status="success",
                message="Spell slot used (LOGIC TEMPORARILY DISABLED)",
                slots_used=-1, # spell_slot_info.slots_used,
                slots_total=-1, # spell_slot_info.slots_total,
                spell_level=spell_level
            ), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error using spell slot for char {character_id}, level {spell_level}: {str(e)}")
            return jsonify(status="error", message="Database error using spell slot (LOGIC TEMPORARILY DISABLED)."), 500
    else:
        return jsonify(
            status="error", 
            message="No slots available or slot data not found (LOGIC TEMPORARILY DISABLED)",
            slots_used=-1, # spell_slot_info.slots_used if spell_slot_info else -1, 
            slots_total=-1, # spell_slot_info.slots_total if spell_slot_info else -1,
            spell_level=spell_level
        ), 400


@bp.route('/character/<int:character_id>/spellslot/regain/<int:spell_level>/<int:count>', methods=['POST'])
@login_required
def regain_spell_slot(character_id, spell_level, count):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    if count <= 0:
        return jsonify(status="error", message="Invalid count for regaining slots."), 400

    # spell_slot_info = CharacterSpellSlot.query.filter_by(
    #     character_id=character.id,
    #     spell_level=spell_level
    # ).first()
    spell_slot_info = None # Placeholder
    current_app.logger.warning(f"Spell slot regain for char {character_id}, level {spell_level} - LOGIC TEMPORARILY DISABLED.")

    if False: # Keep structure, effectively disable
        # spell_slot_info.slots_used = max(0, spell_slot_info.slots_used - count)
        try:
            db.session.commit()
            return jsonify(
                status="success",
                message=f"{count} spell slot(s) regained for level {spell_level} (LOGIC TEMPORARILY DISABLED)",
                slots_used=-1, # spell_slot_info.slots_used,
                slots_total=-1, # spell_slot_info.slots_total,
                spell_level=spell_level
            ), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error regaining spell slot for char {character_id}, level {spell_level}: {str(e)}")
            return jsonify(status="error", message="Database error regaining spell slot (LOGIC TEMPORARILY DISABLED)."), 500
    else:
        return jsonify(status="error", message="Slot data not found for this level (LOGIC TEMPORARILY DISABLED)."), 404


@bp.route('/character/<int:character_id>/rest/short', methods=['POST'])
@login_required
def short_rest(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    # Placeholder for future short rest mechanics (e.g., hit dice, class features)
    current_app.logger.info(f"Character {character.name} (ID: {character.id}) takes a short rest.")
    
    # Here, you could also add a system message to the character's adventure_log
    # to inform the DM within the game context if desired.
    # For now, the message is primarily for the client-side to display.

    return jsonify(
        status="success",
        message=f"{character.name} takes a short rest. DM has been notified." 
    ), 200


@bp.route('/character/<int:character_id>/rest/long', methods=['POST'])
@login_required
def long_rest(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    # Reset all spell slots for the character (Temporarily Commented Out)
    updated_slots_info = []
    # spell_slots_for_character = CharacterSpellSlot.query.filter_by(character_id=character.id).all()
    # for slot_info in spell_slots_for_character:
    #     slot_info.slots_used = 0
    #     updated_slots_info.append({
    #         'spell_level': slot_info.spell_level,
    #         'slots_used': slot_info.slots_used,
    #         'slots_total': slot_info.slots_total
    #     })
    current_app.logger.warning(f"Long rest for char {character_id} - Spell slot refresh LOGIC TEMPORARILY DISABLED.")
    # (Future: Implement other long rest mechanics like full HP recovery, hit dice regain, etc.)
    # Example: character.hp = character.max_hp 
    # (if you add this, ensure character.max_hp is correctly populated)

    try:
        db.session.commit()
        current_app.logger.info(f"Character {character.name} (ID: {character.id}) takes a long rest. Spell slots refreshed.")
        return jsonify(
            status="success",
            message=f"{character.name} takes a long rest. Spell slots have been refreshed. DM has been notified.",
            refreshed_slots=True,
            all_slots_data=updated_slots_info # Send back the state of all slots
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during long rest for char {character_id}: {str(e)}")
        return jsonify(status="error", message="Database error during long rest."), 500

# --- New Route for Getting Character Level Data ---
@bp.route('/character/<int:character_id>/get_level_data/<int:level_number>', methods=['GET'])
@login_required
def get_character_level_data(character_id, level_number):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(error="Unauthorized"), 403

    character_level_record = CharacterLevel.query.filter_by(
        character_id=character.id, 
        level_number=level_number
    ).first()

    if not character_level_record:
        return jsonify(error="Level data not found for this character and level number."), 404

    level_data_dict = {
        'id': character_level_record.id,
        'character_id': character_level_record.character_id,
        'level_number': character_level_record.level_number,
        'xp_at_level_up': character_level_record.xp_at_level_up,
        'stats': {
            'strength': character_level_record.strength,
            'dexterity': character_level_record.dexterity,
            'constitution': character_level_record.constitution,
            'intelligence': character_level_record.intelligence,
            'wisdom': character_level_record.wisdom,
            'charisma': character_level_record.charisma,
        },
        'hp': character_level_record.hp,
        'max_hp': character_level_record.max_hp,
        'hit_dice_rolled': character_level_record.hit_dice_rolled,
        'armor_class': character_level_record.armor_class,
        'proficiencies': {},
        'features_gained': "",
        'spells_known_ids_raw': [], # Store raw IDs here, details below
        'spells_known_details': [], # Detailed spell objects will go here
        'spells_prepared_ids': [],
        'spell_slots_snapshot': {},
        'created_at': character_level_record.created_at.isoformat() if character_level_record.created_at else None,
        'speed': character.race.speed if character.race else 30 
    }
    
    try:
        level_data_dict['proficiencies'] = json.loads(character_level_record.proficiencies or '{}')
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse proficiencies JSON for CLID {character_level_record.id}")
    
    try:
        level_data_dict['features_gained'] = json.loads(character_level_record.features_gained or '""')
    except json.JSONDecodeError: # If not JSON, assume it's plain text
        level_data_dict['features_gained'] = character_level_record.features_gained
    
    raw_spell_ids = []
    try:
        raw_spell_ids = json.loads(character_level_record.spells_known_ids or '[]')
        level_data_dict['spells_known_ids_raw'] = raw_spell_ids
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse spells_known_ids JSON for CLID {character_level_record.id}")

    try:
        level_data_dict['spells_prepared_ids'] = json.loads(character_level_record.spells_prepared_ids or '[]')
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse spells_prepared_ids JSON for CLID {character_level_record.id}")

    try:
        level_data_dict['spell_slots_snapshot'] = json.loads(character_level_record.spell_slots_snapshot or '{}')
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse spell_slots_snapshot JSON for CLID {character_level_record.id}")
    
    level_data_dict['character_class_name'] = character.char_class.name if character.char_class else "Unknown"

    if raw_spell_ids and isinstance(raw_spell_ids, list):
        try:
            known_spells_objects = Spell.query.filter(Spell.id.in_(raw_spell_ids)).all()
            spells_details_list = []
            for spell_obj in known_spells_objects:
                spells_details_list.append({
                    'id': spell_obj.id, 'index': spell_obj.index, 'name': spell_obj.name,
                    'level': spell_obj.level, 'school': spell_obj.school,
                    'casting_time': spell_obj.casting_time, 'range': spell_obj.range,
                    'components': spell_obj.components, 'material': spell_obj.material,
                    'duration': spell_obj.duration, 'concentration': spell_obj.concentration,
                    'description': spell_obj.description, # Already JSON string of paragraphs
                    'higher_level': spell_obj.higher_level # Already JSON string of paragraphs
                })
            level_data_dict['spells_known_details'] = spells_details_list
        except Exception as e:
            current_app.logger.error(f"Error processing spells_known_details for CLID {character_level_record.id}: {str(e)}")

    return jsonify(level_data_dict)
# --- End of New Route ---

# --- Routes for Character Level Up Process (Example Structure) ---
@bp.route('/character/<int:character_id>/level_up/start', methods=['GET'])
@login_required
def level_up_start(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash("Unauthorized access. This character does not belong to you.", "error")
        return redirect(url_for('main.index'))

    latest_level_data = CharacterLevel.query.filter_by(character_id=character.id).order_by(CharacterLevel.level_number.desc()).first()
    if not latest_level_data:
        flash("Character has no level data. Cannot start level up.", "error")
        return redirect(url_for('main.adventure', character_id=character_id))

    current_level_number = latest_level_data.level_number
    new_level_number = current_level_number + 1

    if new_level_number > character.dm_allowed_level:
        flash(f"Your DM has not yet allowed you to advance to Level {new_level_number}. Current DM max: Level {character.dm_allowed_level}.", "warning")
        return redirect(url_for('main.adventure', character_id=character_id))

    if not character.char_class: # Ensure the character has a class associated
        flash("Character has no class information. Cannot proceed with level up.", "error")
        return redirect(url_for('main.adventure', character_id=character_id))

    session['level_up_data'] = {
        'character_id': character.id,
        'current_level_number': current_level_number,
        'new_level_number': new_level_number,
        'class_id': character.class_id,
        'class_name': character.char_class.name,
        'hit_die': character.char_class.hit_die,
        'ability_scores': {
            'STR': latest_level_data.strength,
            'DEX': latest_level_data.dexterity,
            'CON': latest_level_data.constitution,
            'INT': latest_level_data.intelligence,
            'WIS': latest_level_data.wisdom,
            'CHA': latest_level_data.charisma,
        },
        'previous_spells_known_ids': json.loads(latest_level_data.spells_known_ids or '[]') # Store for spell selection
    }
    session.modified = True
    
    current_app.logger.info(f"Level up started for char {character_id} from L{current_level_number} to L{new_level_number}. Session data: {session['level_up_data']}")
    # Redirect to the first step, e.g., HP determination
    return redirect(url_for('main.level_up_hp', character_id=character_id))


@bp.route('/character/<int:character_id>/level_up/hp', methods=['GET', 'POST'])
@login_required
def level_up_hp(character_id):
    level_up_data = session.get('level_up_data')
    if not level_up_data or level_up_data.get('character_id') != character_id:
        flash("Level up session data not found or invalid. Please start the level up process again.", "error")
        return redirect(url_for('main.adventure', character_id=character_id))

    char_class_name = level_up_data.get('class_name', 'Unknown Class')
    new_level_number = level_up_data.get('new_level_number', 'Unknown')
    hit_die_str = level_up_data.get('hit_die', 'd8') # e.g., "d8"
    
    ability_scores = level_up_data.get('ability_scores', {})
    con_score = ability_scores.get('CON', 10)
    con_modifier = (con_score - 10) // 2

    try:
        die_sides = int(hit_die_str[1:])
    except (TypeError, ValueError, IndexError):
        current_app.logger.error(f"Invalid hit_die format: {hit_die_str} for char {character_id}. Defaulting to d8 (4 sides for fixed).")
        die_sides = 8 # Default if parsing fails
    
    fixed_hp_gain_map = { 4:3, 6:4, 8:5, 10:6, 12:7 }
    fixed_hp_gain_value = fixed_hp_gain_map.get(die_sides, die_sides // 2 + 1) # Default to average rounded up if not in map

    if request.method == 'POST':
        hp_choice = request.form.get('hp_choice')
        hp_gained_this_level = 0
        hp_info_log = ""

        if hp_choice == 'roll':
            rolled_hp_value_str = request.form.get('rolled_hp_value')
            if not rolled_hp_value_str:
                flash("You chose to roll, but no rolled value was submitted. Please roll the die.", "error")
                return redirect(url_for('main.level_up_hp', character_id=character_id))
            try:
                rolled_hp_value = int(rolled_hp_value_str)
                if not (1 <= rolled_hp_value <= die_sides):
                    flash(f"Invalid roll value. Must be between 1 and {die_sides}.", "error")
                    return redirect(url_for('main.level_up_hp', character_id=character_id))
                hp_gained_this_level = rolled_hp_value + con_modifier
                hp_info_log = f"Rolled: {rolled_hp_value} (Die: {hit_die_str}, CON Mod: {con_modifier})"
            except ValueError:
                flash("Invalid rolled HP value. Please ensure it's a number.", "error")
                return redirect(url_for('main.level_up_hp', character_id=character_id))
        elif hp_choice == 'fixed':
            hp_gained_this_level = fixed_hp_gain_value + con_modifier
            hp_info_log = f"Fixed: {fixed_hp_gain_value} (CON Mod: {con_modifier})"
        else:
            flash("Invalid HP choice submitted.", "error")
            return redirect(url_for('main.level_up_hp', character_id=character_id))

        # Ensure minimum HP gain is 1
        hp_gained_this_level = max(1, hp_gained_this_level)
        
        level_up_data['hp_info'] = {
            'method': hp_choice,
            'gain': hp_gained_this_level,
            'log_details': hp_info_log # Store how it was determined for later record
        }
        session['level_up_data'] = level_up_data
        session.modified = True
        
        flash(f"HP gain of {hp_gained_this_level} recorded for level {new_level_number}.", "success")
        return redirect(url_for('main.level_up_features_asi', character_id=character_id)) 

    return render_template('level_up/level_up_hp.html',
                           character_id=character_id,
                           class_name=char_class_name,
                           new_level_number=new_level_number,
                           hit_die=hit_die_str,
                           con_modifier=con_modifier,
                           fixed_hp_gain_value=fixed_hp_gain_value)


@bp.route('/character/<int:character_id>/level_up/features_asi', methods=['GET', 'POST'])
@login_required
def level_up_features_asi(character_id):
    level_up_data = session.get('level_up_data')
    if not level_up_data or level_up_data.get('character_id') != character_id or not level_up_data.get('hp_info'):
        flash("Level up process not started correctly or HP step missed. Please start over.", "error")
        return redirect(url_for('main.level_up_start', character_id=character_id))

    char_class_id = level_up_data.get('class_id')
    char_class = Class.query.get(char_class_id)
    if not char_class:
        flash("Could not retrieve class data. Aborting level up.", "error")
        session.pop('level_up_data', None)
        return redirect(url_for('main.adventure', character_id=character_id))

    new_level_number = level_up_data.get('new_level_number')
    # These are for GET request display, might be overwritten by POST
    new_features_at_this_level = level_up_data.get('new_features_list', [])
    asi_count_at_this_level = level_up_data.get('asi_count_available', 0)


    if request.method == 'GET': 
        if char_class.level_specific_data:
            try:
                level_specific_progression = json.loads(char_class.level_specific_data)
                current_level_prog_data = level_specific_progression.get(str(new_level_number))
                if current_level_prog_data:
                    new_features_at_this_level = current_level_prog_data.get('features', [])
                    asi_count_at_this_level = current_level_prog_data.get('asi_count', 0)
            except json.JSONDecodeError:
                current_app.logger.error(f"Could not parse level_specific_data for class {char_class.name}")
                flash("Error reading class progression data.", "error")
        
        level_up_data['new_features_list'] = new_features_at_this_level
        level_up_data['asi_count_available'] = asi_count_at_this_level
        level_up_data.setdefault('chosen_asi', {}) 
        level_up_data.setdefault('asi_choices_log', [])
        session.modified = True
            
    if request.method == 'POST':
        asi_count_available_in_session = level_up_data.get('asi_count_available', 0)
        # Important: work on a copy for ability scores until all validation passes
        current_ability_scores_copy = level_up_data.get('ability_scores', {}).copy()
        asi_choices_log_list = [] 

        for i in range(asi_count_available_in_session):
            choice_type = request.form.get(f'asi_{i}_choice_type')
            
            score1_plus_two_field = f'asi_{i}_score1_plus_two'
            score1_plus_one_field = f'asi_{i}_score1_plus_one'
            score2_plus_one_field = f'asi_{i}_score2_plus_one'

            if choice_type == "plus_two":
                score1_abbr = request.form.get(score1_plus_two_field)
                if not score1_abbr or score1_abbr not in ABILITY_NAMES_FULL_SESSION_KEYS: 
                    flash(f"Invalid ability selected for ASI choice #{i+1} (+2). Please select an ability.", "error")
                    return render_template('level_up/level_up_features_asi.html',
                                           character_id=character_id, class_name=level_up_data.get('class_name'),
                                           new_level_number=new_level_number, current_ability_scores=level_up_data.get('ability_scores'),
                                           new_features=level_up_data.get('new_features_list', []), asi_count=asi_count_available_in_session, 
                                           ability_names=ABILITY_NAMES_FULL)
                
                current_ability_scores_copy[score1_abbr] = current_ability_scores_copy.get(score1_abbr, 10) + 2
                asi_choices_log_list.append(f"ASI #{i+1}: +2 to {score1_abbr}")

            elif choice_type == "plus_one_plus_one":
                score1_abbr = request.form.get(score1_plus_one_field)
                score2_abbr = request.form.get(score2_plus_one_field)

                if not score1_abbr or score1_abbr not in ABILITY_NAMES_FULL_SESSION_KEYS or \
                   not score2_abbr or score2_abbr not in ABILITY_NAMES_FULL_SESSION_KEYS:
                    flash(f"Invalid ability selected for ASI choice #{i+1} (+1/+1). Please select two abilities.", "error")
                    return render_template('level_up/level_up_features_asi.html',
                                           character_id=character_id, class_name=level_up_data.get('class_name'),
                                           new_level_number=new_level_number, current_ability_scores=level_up_data.get('ability_scores'),
                                           new_features=level_up_data.get('new_features_list', []), asi_count=asi_count_available_in_session,
                                           ability_names=ABILITY_NAMES_FULL)
                if score1_abbr == score2_abbr:
                    flash(f"For ASI choice #{i+1} (+1/+1), you must select two different abilities.", "error")
                    return render_template('level_up/level_up_features_asi.html',
                                           character_id=character_id, class_name=level_up_data.get('class_name'),
                                           new_level_number=new_level_number, current_ability_scores=level_up_data.get('ability_scores'),
                                           new_features=level_up_data.get('new_features_list', []), asi_count=asi_count_available_in_session,
                                           ability_names=ABILITY_NAMES_FULL)

                current_ability_scores_copy[score1_abbr] = current_ability_scores_copy.get(score1_abbr, 10) + 1
                current_ability_scores_copy[score2_abbr] = current_ability_scores_copy.get(score2_abbr, 10) + 1
                asi_choices_log_list.append(f"ASI #{i+1}: +1 to {score1_abbr}, +1 to {score2_abbr}")
            
            elif not choice_type or choice_type == "none": 
                 asi_choices_log_list.append(f"ASI #{i+1}: No ability score increase taken.")
            else: 
                flash(f"Invalid ASI choice type '{choice_type}' for ASI #{i+1}.", "error")
                return render_template('level_up/level_up_features_asi.html',
                                       character_id=character_id, class_name=level_up_data.get('class_name'),
                                       new_level_number=new_level_number, current_ability_scores=level_up_data.get('ability_scores'),
                                       new_features=level_up_data.get('new_features_list', []), asi_count=asi_count_available_in_session,
                                       ability_names=ABILITY_NAMES_FULL)


        level_up_data['ability_scores'] = current_ability_scores_copy 
        level_up_data['asi_choices_log'] = asi_choices_log_list 
        level_up_data['chosen_features_details_list'] = level_up_data.get('new_features_list', [])
        session['level_up_data'] = level_up_data
        session.modified = True
        
        flash("Features and ASI choices processed.", "success")
        if char_class.spellcasting_ability:
            cantrips_known_map = json.loads(char_class.cantrips_known_by_level or '{}')
            spells_known_map = json.loads(char_class.spells_known_by_level or '{}')
            
            cantrips_now = int(cantrips_known_map.get(str(new_level_number), 0))
            cantrips_before = int(cantrips_known_map.get(str(level_up_data['current_level_number']), 0))
            
            spells_now = int(spells_known_map.get(str(new_level_number), 0))
            spells_before = int(spells_known_map.get(str(level_up_data['current_level_number']), 0))

            learns_new_cantrips = cantrips_now > cantrips_before
            learns_new_spells = spells_now > spells_before
            if char_class.name == "Wizard": # Wizards always get to add 2 spells
                learns_new_spells = True 

            if learns_new_cantrips or learns_new_spells or char_class.can_prepare_spells:
                 return redirect(url_for('main.level_up_spells', character_id=character_id))
        return redirect(url_for('main.level_up_review', character_id=character_id))

    # For GET request
    return render_template('level_up/level_up_features_asi.html',
                            character_id=character_id,
                            class_name=level_up_data.get('class_name'),
                            new_level_number=new_level_number,
                            current_ability_scores=level_up_data.get('ability_scores'), 
                            new_features=new_features_at_this_level, 
                            asi_count=asi_count_at_this_level, 
                            ability_names=ABILITY_NAMES_FULL 
                           )


@bp.route('/character/<int:character_id>/level_up/spells', methods=['GET', 'POST'])
@login_required
def level_up_spells(character_id):
    level_up_data = session.get('level_up_data')
    if not level_up_data or level_up_data.get('character_id') != character_id \
            or not level_up_data.get('hp_info') \
            or not level_up_data.get('new_features_list'): 
        flash("Level up process not started correctly or a step was missed. Please start over.", "error")
        return redirect(url_for('main.level_up_start', character_id=character_id))

    char_class_id = level_up_data.get('class_id')
    char_class = Class.query.get(char_class_id)
    new_level_number_str = str(level_up_data.get('new_level_number'))
    current_level_number_str = str(level_up_data.get('current_level_number'))

    if not char_class or not char_class.spellcasting_ability:
        level_up_data['selected_new_cantrip_ids'] = [] 
        level_up_data['selected_new_spell_ids'] = []
        session['level_up_data'] = level_up_data
        session.modified = True
        return redirect(url_for('main.level_up_review', character_id=character_id))

    num_new_cantrips_to_choose = 0
    num_new_spells_to_choose = 0

    try:
        cantrips_known_map = json.loads(char_class.cantrips_known_by_level or '{}')
        spells_known_map = json.loads(char_class.spells_known_by_level or '{}')

        cantrips_at_new_level = int(cantrips_known_map.get(new_level_number_str, 0))
        cantrips_at_current_level = int(cantrips_known_map.get(current_level_number_str, 0))
        num_new_cantrips_to_choose = max(0, cantrips_at_new_level - cantrips_at_current_level)

        spells_at_new_level = int(spells_known_map.get(new_level_number_str, 0))
        spells_at_current_level = int(spells_known_map.get(current_level_number_str, 0))
        
        if char_class.name == "Wizard": 
            num_new_spells_to_choose = 2 
        else: 
            num_new_spells_to_choose = max(0, spells_at_new_level - spells_at_current_level)

    except (json.JSONDecodeError, ValueError) as e:
        current_app.logger.error(f"Could not parse cantrips/spells known for class {char_class.name}: {e}")
        flash("Error reading class spell progression data.", "error")
        return redirect(url_for('main.level_up_review', character_id=character_id))

    if num_new_cantrips_to_choose == 0 and num_new_spells_to_choose == 0 and not char_class.can_prepare_spells:
        level_up_data['selected_new_cantrip_ids'] = []
        level_up_data['selected_new_spell_ids'] = []
        session['level_up_data'] = level_up_data
        session.modified = True
        flash("No new spells to learn or choose at this level.", "info")
        return redirect(url_for('main.level_up_review', character_id=character_id))
    
    previous_spells_known_ids = set(level_up_data.get('previous_spells_known_ids', []))
    
    max_spell_level_castable = 0
    if char_class.spell_slots_by_level:
        try:
            slots_by_char_level = json.loads(char_class.spell_slots_by_level)
            slots_for_new_level = slots_by_char_level.get(new_level_number_str, [])
            for i, num_slots in reversed(list(enumerate(slots_for_new_level))):
                if num_slots > 0:
                    max_spell_level_castable = i + 1 
                    break
        except json.JSONDecodeError:
            current_app.logger.error(f"Could not parse spell_slots_by_level for class {char_class.name}")


    available_cantrips_query = Spell.query.filter(
        Spell.level == 0, 
        Spell.classes_that_can_use.like(f'%"{char_class.name}"%')
    )
    if previous_spells_known_ids: 
        available_cantrips_query = available_cantrips_query.filter(~Spell.id.in_(previous_spells_known_ids))
    available_cantrips = available_cantrips_query.order_by(Spell.name).all()
    
    available_spells_query = Spell.query.filter(
        Spell.level > 0,
        Spell.level <= max_spell_level_castable, 
        Spell.classes_that_can_use.like(f'%"{char_class.name}"%')
    )
    if previous_spells_known_ids: 
        available_spells_query = available_spells_query.filter(~Spell.id.in_(previous_spells_known_ids))
    available_spells = available_spells_query.order_by(Spell.level, Spell.name).all()


    if request.method == 'POST':
        selected_cantrip_ids = [int(id_str) for id_str in request.form.getlist('new_cantrips')]
        selected_spell_ids = [int(id_str) for id_str in request.form.getlist('new_spells')]

        if len(selected_cantrip_ids) != num_new_cantrips_to_choose:
            flash(f"Please select exactly {num_new_cantrips_to_choose} new cantrip(s).", "error")
            return render_template('level_up/level_up_spells.html', character_id=character_id, 
                                   level_up_data=level_up_data, char_class=char_class,
                                   num_new_cantrips_to_choose=num_new_cantrips_to_choose, 
                                   num_new_spells_to_choose=num_new_spells_to_choose,
                                   available_cantrips=available_cantrips, available_spells=available_spells,
                                   previous_spells_known_ids=list(previous_spells_known_ids),
                                   max_spell_level_castable=max_spell_level_castable)

        if len(selected_spell_ids) != num_new_spells_to_choose:
            flash(f"Please select exactly {num_new_spells_to_choose} new spell(s).", "error")
            return render_template('level_up/level_up_spells.html', character_id=character_id,
                                   level_up_data=level_up_data, char_class=char_class,
                                   num_new_cantrips_to_choose=num_new_cantrips_to_choose, 
                                   num_new_spells_to_choose=num_new_spells_to_choose,
                                   available_cantrips=available_cantrips, available_spells=available_spells,
                                   previous_spells_known_ids=list(previous_spells_known_ids),
                                   max_spell_level_castable=max_spell_level_castable)
        
        level_up_data['selected_new_cantrip_ids'] = selected_cantrip_ids
        level_up_data['selected_new_spell_ids'] = selected_spell_ids
        session['level_up_data'] = level_up_data
        session.modified = True

        flash("Spell selections saved.", "success")
        return redirect(url_for('main.level_up_review', character_id=character_id))

    return render_template('level_up/level_up_spells.html', 
                           character_id=character_id,
                           level_up_data=level_up_data,
                           char_class=char_class,
                           num_new_cantrips_to_choose=num_new_cantrips_to_choose,
                           num_new_spells_to_choose=num_new_spells_to_choose,
                           available_cantrips=available_cantrips,
                           available_spells=available_spells,
                           previous_spells_known_ids=list(previous_spells_known_ids), 
                           max_spell_level_castable=max_spell_level_castable
                           )


@bp.route('/character/<int:character_id>/level_up/review', methods=['GET'])
@login_required
def level_up_review(character_id):
    level_up_data = session.get('level_up_data')
    if not level_up_data or level_up_data.get('character_id') != character_id: 
        flash("Level up process not started correctly or a step was missed. Please start over.", "error")
        return redirect(url_for('main.level_up_start', character_id=character_id))
    
    # Prepare data for review template
    review_data = {
        'character_id': character_id,
        'class_name': level_up_data.get('class_name'),
        'current_level_number': level_up_data.get('current_level_number'),
        'new_level_number': level_up_data.get('new_level_number'),
        'hp_info': level_up_data.get('hp_info'),
        'new_features_list': level_up_data.get('new_features_list', []),
        'asi_choices_log': level_up_data.get('asi_choices_log', []),
        'final_ability_scores': level_up_data.get('ability_scores', {}), # These are the scores *after* ASI
        'selected_new_cantrips': Spell.query.filter(Spell.id.in_(level_up_data.get('selected_new_cantrip_ids', []))).all(),
        'selected_new_spells': Spell.query.filter(Spell.id.in_(level_up_data.get('selected_new_spell_ids', []))).all()
    }
    return render_template('level_up/level_up_review.html', **review_data)


@bp.route('/character/<int:character_id>/level_up/apply', methods=['POST']) 
@login_required
def level_up_apply(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash("Unauthorized", "error")
        return redirect(url_for('main.index'))
    
    level_up_data = session.get('level_up_data')
    if not level_up_data or level_up_data.get('character_id') != character_id or not level_up_data.get('hp_info'):
        flash("Level up data is incomplete or missing. Please restart the level up process.", "error")
        return redirect(url_for('main.level_up_start', character_id=character_id))

    current_level_entry = CharacterLevel.query.filter_by(character_id=character.id, level_number=level_up_data['current_level_number']).first()
    if not current_level_entry:
        flash("Could not find previous level data for the character.", "error")
        return redirect(url_for('main.adventure', character_id=character_id))

    if character.dm_allowed_level < level_up_data['new_level_number']:
         flash(f"DM has not allowed leveling up to {level_up_data['new_level_number']} yet.", "error")
         return redirect(url_for('main.adventure', character_id=character_id))
    
    final_ability_scores = level_up_data.get('ability_scores', {}).copy() 

    gained_features_list = level_up_data.get('new_features_list', [])
    asi_log_list = level_up_data.get('asi_choices_log', [])
    combined_features_log = gained_features_list + asi_log_list

    old_spells_known_ids = set(level_up_data.get('previous_spells_known_ids', []))
    newly_selected_cantrips = set(level_up_data.get('selected_new_cantrip_ids', []))
    newly_selected_spells = set(level_up_data.get('selected_new_spell_ids', []))
    all_known_spell_ids = list(old_spells_known_ids.union(newly_selected_cantrips).union(newly_selected_spells))

    # Update spell_slots_snapshot based on new level and class data
    new_spell_slots_snapshot_dict = {}
    char_class = Class.query.get(level_up_data['class_id'])
    if char_class and char_class.spell_slots_by_level:
        try:
            all_slots_data = json.loads(char_class.spell_slots_by_level)
            slots_for_new_level_list = all_slots_data.get(str(level_up_data['new_level_number'])) # list like [4,2,0,0...]
            if slots_for_new_level_list:
                for i, num_slots in enumerate(slots_for_new_level_list):
                    if num_slots > 0:
                        new_spell_slots_snapshot_dict[str(i + 1)] = num_slots # Store as {"1": count, "2": count}
        except json.JSONDecodeError:
            current_app.logger.error(f"Could not parse spell_slots_by_level for class {char_class.name} during level up apply.")
            # Fallback to previous level's snapshot if parsing fails
            new_spell_slots_snapshot_dict = json.loads(current_level_entry.spell_slots_snapshot or '{}')


    new_level_data = CharacterLevel(
        character_id=character.id,
        level_number=level_up_data['new_level_number'],
        xp_at_level_up=character.current_xp, 
        strength=final_ability_scores.get('STR', current_level_entry.strength), 
        dexterity=final_ability_scores.get('DEX', current_level_entry.dexterity),
        constitution=final_ability_scores.get('CON', current_level_entry.constitution),
        intelligence=final_ability_scores.get('INT', current_level_entry.intelligence),
        wisdom=final_ability_scores.get('WIS', current_level_entry.wisdom),
        charisma=final_ability_scores.get('CHA', current_level_entry.charisma),
        hp=current_level_entry.max_hp + level_up_data['hp_info']['gain'], 
        max_hp=current_level_entry.max_hp + level_up_data['hp_info']['gain'], 
        hit_dice_rolled=level_up_data['hp_info'].get('log_details', "N/A"), 
        armor_class=current_level_entry.armor_class, 
        proficiencies=current_level_entry.proficiencies, # Placeholder - should update if new profs gained
        features_gained=json.dumps(combined_features_log), 
        spells_known_ids=json.dumps(all_known_spell_ids), 
        spells_prepared_ids=current_level_entry.spells_prepared_ids, # Placeholder for prepared casters
        spell_slots_snapshot=json.dumps(new_spell_slots_snapshot_dict), 
        created_at=datetime.utcnow()
    )
    
    db.session.add(new_level_data)
    try:
        db.session.commit()
        session.pop('level_up_data', None) 
        flash(f"Successfully leveled up to Level {new_level_data.level_number}!", "success")
        return redirect(url_for('main.adventure', character_id=character_id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying level up for char {character_id} to L{new_level_data.level_number}: {str(e)}")
        flash("Error applying level up. Please try again.", "error")
        return redirect(url_for('main.level_up_start', character_id=character_id))

[end of app/main/routes.py]
