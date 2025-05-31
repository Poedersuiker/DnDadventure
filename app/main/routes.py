import json
import os
# import google.generativeai as genai # Removed
import google.generativeai as genai # Re-add import
import re # Added for gold parsing
import requests # Added for requests.exceptions.RequestException
from flask import render_template, redirect, url_for, flash, request, session, get_flashed_messages, jsonify, current_app
from flask_babel import _
from flask_login import login_required, current_user
from app import db
# CharacterSpellSlot removed, CharacterLevel added
from app.models import User, Character, Race, Class, Spell, Setting, Item, Coinage, CharacterLevel
from app.dnd5e_api import get_all_races, get_all_classes, get_class_details, get_class_level_details, get_all_backgrounds, get_background_details, get_resource_details, get_class_learnable_spells # Added get_resource_details
from app.utils import roll_dice, parse_coinage, ALL_SKILLS_LIST, XP_THRESHOLDS, generate_character_sheet_text # Added generate_character_sheet_text
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
        session['new_character_data'] = {}
        races_data = []
        try:
            races_data = get_all_races()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"API Error fetching races: {e}")
            flash('Error fetching races from the D&D API. Please try again later or contact an administrator.', 'error')
        except Exception as e: # Catch any other unexpected errors
            current_app.logger.error(f"Unexpected error fetching races: {e}")
            flash('An unexpected error occurred while fetching races. Please try again later or contact an administrator.', 'error')

        if not races_data: # Handles both API error and empty results
             # Flash message already set if API error, avoid double flashing
            if not get_flashed_messages(category_filter=['error']): # Only flash if no error message exists yet
                flash('No races could be fetched at this time. Please try again later.', 'info') # Use info if it's just empty
            return render_template('create_character_race.html', races=[]) # Pass empty list

        return render_template('create_character_race.html', races=races_data)

    # POST request logic
    selected_race_index = request.form.get('race_index')
    if not selected_race_index:
        flash('Please select a race.', 'error')
        # Need to fetch races again for re-rendering
        races_data_for_retry = []
        try:
            races_data_for_retry = get_all_races()
        except requests.exceptions.RequestException:
            flash('Error fetching races from the D&D API. Please try again later.', 'error')
        return render_template('create_character_race.html', races=races_data_for_retry)

    all_races_from_api = []
    try:
        all_races_from_api = get_all_races()
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"API Error fetching races during POST: {e}")
        flash('Error fetching race details from the D&D API. Please try again.', 'error')
        return render_template('create_character_race.html', races=[]) # Render with empty if API fails here
    except Exception as e:
        current_app.logger.error(f"Unexpected error fetching races during POST: {e}")
        flash('An unexpected error occurred while fetching race details. Please try again.', 'error')
        return render_template('create_character_race.html', races=[])


    selected_race_name = None
    if all_races_from_api:
        for race_api_item in all_races_from_api:
            if race_api_item.get('index') == selected_race_index:
                selected_race_name = race_api_item.get('name')
                break

    if selected_race_name:
        # Storing index and name from API. ID is no longer used from local DB.
        session['new_character_data']['race_index'] = selected_race_index
        session['new_character_data']['race_name'] = selected_race_name

        try:
            api_race_details = get_resource_details("races", selected_race_index)
            session['new_character_data']['api_race_details'] = api_race_details
            session['new_character_data']['race_languages'] = [lang.get('name') for lang in api_race_details.get('languages', []) if lang.get('name')]
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"API error fetching details for race '{selected_race_index}': {e}")
            flash(f"Could not fetch detailed data for {selected_race_name}. Some features like languages and ability bonuses might be unavailable.", "warning")
            session['new_character_data']['api_race_details'] = None # Ensure it's None if fetch fails
            session['new_character_data']['race_languages'] = []


        # Local DB race_id for compatibility if needed, but API is primary
        temp_local_race_for_id = Race.query.filter_by(name=selected_race_name).first()
        if temp_local_race_for_id:
            session['new_character_data']['race_id'] = temp_local_race_for_id.id
        else:
            flash(f"Warning: Could not find a local database entry for '{selected_race_name}'. Using API data primarily.", 'info')
            session['new_character_data']['race_id'] = None

        session.modified = True
        flash(f'{selected_race_name} selected!', 'success')
        return redirect(url_for('main.creation_class'))
    else:
        flash('Selected race not found or API error. Please try again.', 'error')
        # Re-render with races fetched again
        races_data_for_error_case = []
        try:
            races_data_for_error_case = get_all_races()
        except requests.exceptions.RequestException:
            flash('Error fetching races from the D&D API for selection.', 'error')
        return render_template('create_character_race.html', races=races_data_for_error_case)

@bp.route('/creation/class', methods=['GET', 'POST'])
@login_required
def creation_class():
    char_data = session.get('new_character_data', {})
    # Changed to check for race_name or race_index as race_id might be None if local DB entry not found
    if not char_data.get('race_name') and not char_data.get('race_index'):
        flash('Please select a race first.', 'error')
        return redirect(url_for('main.creation_race'))

    if request.method == 'GET':
        classes_data = []
        try:
            classes_data = get_all_classes()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"API Error fetching classes: {e}")
            flash('Error fetching classes from the D&D API. Please try again later or contact an administrator.', 'error')
        except Exception as e: # Catch any other unexpected errors
            current_app.logger.error(f"Unexpected error fetching classes: {e}")
            flash('An unexpected error occurred while fetching classes. Please try again later or contact an administrator.', 'error')

        if not classes_data:
            if not get_flashed_messages(category_filter=['error']):
                flash('No classes could be fetched at this time. Please try again later.', 'info')
            return render_template('create_character_class.html', classes=[], race_name=char_data.get('race_name'))

        return render_template('create_character_class.html', classes=classes_data, race_name=char_data.get('race_name'))

    # POST request logic
    selected_class_index = request.form.get('class_index')
    if not selected_class_index:
        flash('Please select a class.', 'error')
        classes_data_for_retry = []
        try:
            classes_data_for_retry = get_all_classes()
        except requests.exceptions.RequestException:
            flash('Error fetching classes from the D&D API. Please try again later.', 'error')
        return render_template('create_character_class.html', classes=classes_data_for_retry, race_name=char_data.get('race_name'))

    all_classes_from_api = []
    try:
        all_classes_from_api = get_all_classes()
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"API Error fetching classes during POST: {e}")
        flash('Error fetching class details from the D&D API. Please try again.', 'error')
        return render_template('create_character_class.html', classes=[], race_name=char_data.get('race_name'))
    except Exception as e:
        current_app.logger.error(f"Unexpected error fetching classes during POST: {e}")
        flash('An unexpected error occurred while fetching class details. Please try again.', 'error')
        return render_template('create_character_class.html', classes=[], race_name=char_data.get('race_name'))

    selected_class_name = None
    if all_classes_from_api:
        for class_api_item in all_classes_from_api:
            if class_api_item.get('index') == selected_class_index:
                selected_class_name = class_api_item.get('name')
                break

    if selected_class_name:
        session['new_character_data']['class_index'] = selected_class_index
        session['new_character_data']['class_name'] = selected_class_name

        try:
            api_class_details = get_class_details(selected_class_index)
            session['new_character_data']['api_class_details'] = api_class_details
            api_class_level_1_details = get_class_level_details(selected_class_index, 1)
            session['new_character_data']['api_class_level_1_details'] = api_class_level_1_details
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"API error fetching details for class '{selected_class_index}': {e}")
            flash(f"Could not fetch detailed data for {selected_class_name}. Proceeding with limited information.", "warning")
            session['new_character_data']['api_class_details'] = None
            session['new_character_data']['api_class_level_1_details'] = None

        # Attempt to find local Class entry for compatibility or if API fails
        temp_local_class_for_id = Class.query.filter_by(name=selected_class_name).first()
        if temp_local_class_for_id:
            session['new_character_data']['class_id'] = temp_local_class_for_id.id
        else:
            session['new_character_data']['class_id'] = None # Explicitly set to None
            if not session['new_character_data'].get('api_class_details'): # Only warn if API also failed
                 flash(f"Warning: Could not find a local database entry for class '{selected_class_name}' and API fetch failed. Some features might not work.", 'error')


        session.modified = True
        flash(f'{selected_class_name} selected!', 'success')
        return redirect(url_for('main.creation_stats'))
    else:
        flash('Selected class not found or API error. Please try again.', 'error')
        classes_data_for_error_case = []
        try:
            classes_data_for_error_case = get_all_classes()
        except requests.exceptions.RequestException:
            flash('Error fetching classes from the D&D API for selection.', 'error')
        return render_template('create_character_class.html', classes=classes_data_for_error_case, race_name=char_data.get('race_name'))

@bp.route('/creation/stats', methods=['GET', 'POST'])
@login_required
def creation_stats():
    char_data = session.get('new_character_data', {})
    # Check for race_name or race_index from API, also class_name (instead of class_id)
    if not (char_data.get('race_name') or char_data.get('race_index')):
        flash('Please select a race first.', 'error')
        return redirect(url_for('main.creation_race'))
    if not char_data.get('class_name'): # Changed from class_id to class_name
        flash('Please select a class first.', 'error')
        return redirect(url_for('main.creation_class'))

    selected_race = None # Will hold local Race object if found
    # selected_race (local DB object) is less critical now if API details are present
    # if char_data.get('race_id'):
    #     selected_race = Race.query.get(char_data['race_id'])

    class_name_to_display = char_data.get('class_name') # Default to whatever is in session
    primary_ability = "Refer to class features" # Default
    ability_short_to_full = {
        "str": "Strength", "dex": "Dexterity", "con": "Constitution",
        "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"
    }

    api_class_details = char_data.get('api_class_details') # Should be populated from creation_class

    if api_class_details:
        class_name_to_display = api_class_details.get('name', char_data.get('class_name'))
        spellcasting_info = api_class_details.get('spellcasting')
        if spellcasting_info and spellcasting_info.get('spellcasting_ability'):
            sa_index = spellcasting_info['spellcasting_ability'].get('index')
            primary_ability = ability_short_to_full.get(sa_index, "Refer to class features")
        current_app.logger.info(f"creation_stats: Loaded class details from API session data for {class_name_to_display}. Primary ability: {primary_ability}")
    elif char_data.get('class_id'): # Fallback to local DB if API details are missing from session
        selected_class_local = Class.query.get(char_data['class_id'])
        if selected_class_local:
            class_name_to_display = selected_class_local.name
            primary_ability = selected_class_local.spellcasting_ability or "Refer to class features"
            current_app.logger.info(f"creation_stats: Loaded class details from local DB for {class_name_to_display}. Primary ability: {primary_ability}")
        else:
            flash('Selected class (local) not found. Please restart character creation.', 'error')
            return redirect(url_for('main.creation_class'))
    else: # Critical data missing
        flash('Class details not found in session. Please go back and select a class.', 'error')
        return redirect(url_for('main.creation_class'))

    racial_bonuses_list = []
    api_race_details = char_data.get('api_race_details')
    if api_race_details and 'ability_bonuses' in api_race_details:
        try:
            for bonus_info in api_race_details['ability_bonuses']:
                if bonus_info.get('ability_score') and bonus_info.get('bonus') is not None:
                    racial_bonuses_list.append({
                        'name': bonus_info['ability_score'].get('name'),
                        'bonus': bonus_info.get('bonus')
                    })
            if not racial_bonuses_list and 'ability_bonuses' in api_race_details : # If data was there but parsing failed to populate
                 flash('Could not parse racial ability bonuses from API data. Proceeding with base scores only.', 'warning')
        except Exception as e: # Catch any error during parsing
            current_app.logger.error(f"Error parsing racial bonuses from API details: {e}")
            flash('Error processing racial bonuses from API. Proceeding with base scores only.', 'warning')
    elif char_data.get('race_id'): # Fallback to local DB if API details are missing
        selected_race_local_for_bonus = Race.query.get(char_data['race_id'])
        if selected_race_local_for_bonus and selected_race_local_for_bonus.ability_score_increases:
            try:
                racial_bonuses_list = json.loads(selected_race_local_for_bonus.ability_score_increases)
            except json.JSONDecodeError:
                 flash('Could not parse local racial bonuses. Proceeding with base scores only.', 'warning')
        else:
            flash('Could not load racial bonuses from API or local data. Proceeding with base scores only for racial adjustments.', 'warning')
    else: # No API details and no local race_id
        flash('Racial bonus data is unavailable. Proceeding with base scores only.', 'warning')


    standard_array = [15, 14, 13, 12, 10, 8]
    racial_bonuses_dict = {bonus['name']: bonus['bonus'] for bonus in racial_bonuses_list if bonus.get('name')} # Ensure name exists
    rolled_stats_from_session = session.get('rolled_stats')

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'roll_stats':
            rolled_scores = [roll_dice(4, 6, 1)[0] for _ in range(6)]
            session['rolled_stats'] = rolled_scores
            session.modified = True
            # Re-render with updated context
            return render_template('create_character_stats.html',
                                   race_name=char_data.get('race_name', 'Unknown Race'),
                                   class_name=class_name_to_display,
                                   racial_bonuses_dict=racial_bonuses_dict,
                                   primary_ability=primary_ability,
                                   standard_array=standard_array,
                                   rolled_stats=rolled_scores, # Pass new rolls
                                   submitted_scores=request.form) # Pass current form for repopulation if needed

        base_scores = {}
        errors = False
        ability_map = {
            'strength': 'STR', 'dexterity': 'DEX', 'constitution': 'CON',
            'intelligence': 'INT', 'wisdom': 'WIS', 'charisma': 'CHA'
        }
        form_scores_to_repopulate = {} # For re-rendering form with user's previous input on error

        for form_name, score_key in ability_map.items():
            score_val_str = request.form.get(form_name)
            form_scores_to_repopulate[form_name] = score_val_str # Store for re-population
            if not score_val_str:
                flash(f'{form_name.capitalize()} score is required.', 'error')
                errors = True
                continue
            try:
                score = int(score_val_str)
                if not (3 <= score <= 18): # Validate base score range
                    flash(f'{form_name.capitalize()} score must be between 3 and 18 before racial modifiers.', 'error')
                    errors = True
                base_scores[score_key] = score
            except ValueError:
                flash(f'Invalid score for {form_name.capitalize()}. Must be a number.', 'error')
                errors = True

        if errors:
            return render_template('create_character_stats.html',
                                   race_name=char_data.get('race_name', 'Unknown Race'),
                                   class_name=class_name_to_display,
                                   racial_bonuses_dict=racial_bonuses_dict,
                                   primary_ability=primary_ability,
                                   standard_array=standard_array,
                                   rolled_stats=session.get('rolled_stats'), # Use session rolls if any
                                   submitted_scores=form_scores_to_repopulate) # Pass back submitted scores

        final_scores = base_scores.copy()
        for bonus_item in racial_bonuses_list: # racial_bonuses_list is now from API or local DB
            ability_key = bonus_item.get('name')
            bonus_value = bonus_item.get('bonus', 0)
            if ability_key in final_scores: # Ensure the key from bonus_item is valid
                final_scores[ability_key] += bonus_value
            else:
                current_app.logger.warning(f"Racial bonus ability key '{ability_key}' not found in base scores. Bonus not applied.")


        session['new_character_data']['ability_scores'] = final_scores
        session['new_character_data']['base_ability_scores'] = base_scores # Store base scores separately if needed
        session.modified = True
        session.pop('rolled_stats', None)
        flash('Ability scores saved!', 'success')
        return redirect(url_for('main.creation_background'))
    return render_template('create_character_stats.html',
                           race_name=char_data.get('race_name', 'Unknown Race'),
                           class_name=class_name_to_display, # Use updated class_name
                           racial_bonuses_dict=racial_bonuses_dict,
                           primary_ability=primary_ability, # Use updated primary_ability
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

    if request.method == 'GET':
        detailed_backgrounds = []
        try:
            background_list = get_all_backgrounds()
            for bg_summary in background_list:
                try:
                    bg_detail = get_background_details(bg_summary['index'])
                    detailed_backgrounds.append(bg_detail)
                except requests.exceptions.RequestException as e:
                    current_app.logger.error(f"API Error fetching details for background '{bg_summary['index']}': {e}")
                    flash(f"Error fetching details for background '{bg_summary['name']}'. It may be unavailable.", 'warning')
                except Exception as e:
                    current_app.logger.error(f"Unexpected error processing background '{bg_summary['index']}': {e}")
                    flash(f"An unexpected error occurred processing background '{bg_summary['name']}'.", 'warning')

            if not background_list and not get_flashed_messages(category_filter=['error', 'warning']): # Only flash if no specific errors were already flashed for individual items
                 flash('Could not fetch the list of backgrounds at this time. Please try again later.', 'info')

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"API Error fetching all backgrounds: {e}")
            flash('Major error fetching backgrounds from the D&D API. Please try again later.', 'error')
        except Exception as e:
            current_app.logger.error(f"Unexpected error fetching all backgrounds: {e}")
            flash('An unexpected error occurred while fetching backgrounds. Please try again later.', 'error')

        return render_template('create_character_background.html',
                               race_name=char_data.get('race_name'),
                               class_name=char_data.get('class_name'),
                               backgrounds=detailed_backgrounds) # Pass detailed_backgrounds

    # POST request logic
    selected_background_index = request.form.get('background_index') # Value from form will be 'background.index'
    if not selected_background_index:
        flash('Please select a background.', 'error')
        # Refetch backgrounds for re-rendering
        detailed_backgrounds_for_retry = []
        try:
            background_list = get_all_backgrounds()
            for bg_summary in background_list:
                try:
                    detailed_backgrounds_for_retry.append(get_background_details(bg_summary['index']))
                except requests.exceptions.RequestException: # Simplified error handling for retry
                    pass # Warnings already flashed potentially in GET, or will be if user retries GET
        except requests.exceptions.RequestException:
            flash('Error fetching backgrounds list for selection. Please try again.', 'error')

        return render_template('create_character_background.html',
                               race_name=char_data.get('race_name'),
                               class_name=char_data.get('class_name'),
                               backgrounds=detailed_backgrounds_for_retry)

    try:
        chosen_bg_data = get_background_details(selected_background_index)
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"API Error fetching selected background '{selected_background_index}': {e}")
        flash(f"Error fetching details for the selected background. Please try selecting again.", 'error')
        # Refetch all for re-render
        detailed_backgrounds_for_error = []
        try:
            background_list = get_all_backgrounds()
            for bg_summary in background_list:
                try:
                    detailed_backgrounds_for_error.append(get_background_details(bg_summary['index']))
                except requests.exceptions.RequestException:
                    pass
        except requests.exceptions.RequestException:
            flash('Error fetching backgrounds list for selection. Please try again.', 'error')
        return render_template('create_character_background.html',
                               race_name=char_data.get('race_name'),
                               class_name=char_data.get('class_name'),
                               backgrounds=detailed_backgrounds_for_error)
    except Exception as e: # Catch other potential errors like KeyError if API response is malformed
        current_app.logger.error(f"Unexpected error processing selected background '{selected_background_index}': {e}")
        flash('An unexpected error occurred while processing the selected background. Please try again.', 'error')
        # Refetch all for re-render (similar to above)
        detailed_backgrounds_for_unexpected_error = []
        try:
            background_list = get_all_backgrounds()
            for bg_summary in background_list:
                try:
                    detailed_backgrounds_for_unexpected_error.append(get_background_details(bg_summary['index']))
                except requests.exceptions.RequestException:
                    pass
        except requests.exceptions.RequestException:
            flash('Error fetching backgrounds list. Please try again.', 'error')
        return render_template('create_character_background.html',
                               race_name=char_data.get('race_name'),
                               class_name=char_data.get('class_name'),
                               backgrounds=detailed_backgrounds_for_unexpected_error)


    if chosen_bg_data:
        session['new_character_data']['background_name'] = chosen_bg_data.get('name')

        skill_proficiencies = []
        for prof in chosen_bg_data.get('starting_proficiencies', []):
            if prof.get('name', '').startswith('Skill: '):
                skill_proficiencies.append(prof['name'].replace('Skill: ', ''))
        session['new_character_data']['background_skill_proficiencies'] = skill_proficiencies

        tool_proficiencies = []
        for prof in chosen_bg_data.get('starting_proficiencies', []):
            # D&D API sometimes uses "Tools: " prefix, sometimes just the tool name.
            # And sometimes it's nested under equipment_category.
            # This is a simplified check for now.
            prof_name = prof.get('name', '')
            if prof_name.startswith('Tool: ') or prof_name.startswith("Tools: "): # Common prefixes
                 tool_proficiencies.append(prof_name.split(': ', 1)[1])
            # Add more specific checks if general tool proficiencies are directly listed by name without "Tool:"
            # For now, this catches explicitly prefixed tool profs.
            # Example: "Thieves' Tools" might not have a "Tool:" prefix in some API responses.
            # A more robust solution would check `prof.get('index')` against a list of known tool indices or categories.
            # For now, if it's not prefixed, it won't be caught as a tool proficiency here.
            # The prompt specifically asked for "Tool: " prefix.
        session['new_character_data']['background_tool_proficiencies'] = tool_proficiencies

        language_options = chosen_bg_data.get('language_options', {})
        if language_options and language_options.get('choose', 0) > 0:
            session['new_character_data']['background_languages'] = [f"Choose {language_options['choose']} language(s)"]
        else:
            session['new_character_data']['background_languages'] = [] # No languages or no choice

        equipment_parts = []
        for item_data in chosen_bg_data.get('starting_equipment', []):
            if item_data.get('equipment') and item_data.get('quantity'):
                equipment_parts.append(f"{item_data['equipment']['name']} (x{item_data['quantity']})")

        for choice in chosen_bg_data.get('starting_equipment_options', []):
            num_to_choose = choice.get('choose', 1)
            desc = choice.get('desc')
            if not desc and choice.get('from', {}).get('option_set_type') == 'equipment_category':
                category_name = choice['from']['equipment_category'].get('name', 'a category choice')
                desc = f"from {category_name}"
            elif not desc:
                desc = "from available options" # Fallback description
            equipment_parts.append(f"Choose {num_to_choose} {desc}")

        session['new_character_data']['background_equipment'] = ", ".join(equipment_parts) if equipment_parts else "None"

        session.modified = True
        flash(f"Background '{chosen_bg_data.get('name')}' selected.", 'success')
        return redirect(url_for('main.creation_skills'))
    else:
        flash('Selected background data could not be processed. Please try again.', 'error')
        # Refetch all for re-render (similar to above error handling)
        detailed_backgrounds_for_final_error = []
        try:
            background_list = get_all_backgrounds()
            for bg_summary in background_list:
                try:
                    detailed_backgrounds_for_final_error.append(get_background_details(bg_summary['index']))
                except requests.exceptions.RequestException:
                    pass
        except requests.exceptions.RequestException:
            flash('Error fetching backgrounds list. Please try again.', 'error')
        return render_template('create_character_background.html',
                               race_name=char_data.get('race_name'),
                               class_name=char_data.get('class_name'),
                               backgrounds=detailed_backgrounds_for_final_error)

@bp.route('/creation/skills', methods=['GET', 'POST'])
@login_required
def creation_skills():
    char_data = session.get('new_character_data', {})
    if not char_data.get('background_name'):
        flash('Please choose your background first.', 'error')
        return redirect(url_for('main.creation_background'))

    api_class_details = char_data.get('api_class_details') # Expected to be in session
    class_id = char_data.get('class_id') # May be None
    # class_index = char_data.get('class_index') # Less critical if api_class_details is present
    class_name_from_session = char_data.get('class_name', 'Unknown Class')

    skill_options_to_render = []
    num_skills_to_choose = 0
    saving_throws_to_render = []
    class_name_to_display = class_name_from_session

    # Data source determination logic for GET request
    if api_class_details: # API path
        class_name_to_display = api_class_details.get('name', class_name_from_session)
        saving_throws_to_render = [st.get('name') for st in api_class_details.get('saving_throws', []) if st.get('name')]

        # Extract skill choices
        api_proficiency_choices = api_class_details.get('proficiency_choices', [])
        for choice_block in api_proficiency_choices:
            desc = choice_block.get('desc', '').lower()
            # More robust check for skill choices
            if 'skill' in desc and choice_block.get('choose') and choice_block.get('from', {}).get('options'):
                num_skills_to_choose = choice_block.get('choose', 0)
                options_data = choice_block.get('from', {}).get('options', [])
                for opt in options_data:
                    if opt.get('option_type') == 'reference' and opt.get('item', {}).get('name','').startswith('Skill:'):
                        skill_name = opt['item']['name'].replace('Skill: ', '').strip()
                        skill_options_to_render.append({'name': skill_name}) # Match expected format for template if it's a list of dicts
                    elif opt.get('option_type') == 'choice' and 'skills' in opt.get('choice',{}).get('desc','').lower(): # Handling nested choices like in Ranger
                        num_skills_to_choose = opt['choice'].get('choose',0)
                        for sub_opt in opt.get('choice',{}).get('from',{}).get('options',[]):
                             if sub_opt.get('option_type') == 'reference' and sub_opt.get('item',{}).get('name','').startswith('Skill:'):
                                 skill_name = sub_opt['item']['name'].replace('Skill: ', '').strip()
                                 skill_options_to_render.append({'name': skill_name})
                if num_skills_to_choose > 0 and skill_options_to_render: # Found skill choices
                    break
        current_app.logger.info(f"API Path: Skills for {class_name_to_display}: Options: {len(skill_options_to_render)}, Choose: {num_skills_to_choose}, Saving Throws: {saving_throws_to_render}")

    elif class_id is not None: # Local DB path
        selected_class_local = Class.query.get(class_id)
        if not selected_class_local:
            flash('Selected class (local) not found. Please restart character creation.', 'error')
            return redirect(url_for('main.creation_class'))

        class_name_to_display = selected_class_local.name
        # Local skill_proficiencies_options is a list of strings, convert to list of dicts
        local_skill_names = json.loads(selected_class_local.skill_proficiencies_options or '[]')
        skill_options_to_render = [{'name': name} for name in local_skill_names]
        num_skills_to_choose = selected_class_local.skill_proficiencies_option_count
        saving_throws_to_render = json.loads(selected_class_local.proficiency_saving_throws or '[]')
        current_app.logger.info(f"Local DB Path: Skills for {class_name_to_display}: Options: {len(skill_options_to_render)}, Choose: {num_skills_to_choose}, Saving Throws: {saving_throws_to_render}")

    else: # Critical data missing
        flash('Class data not found. Please select your class again.', 'error')
        return redirect(url_for('main.creation_class'))

    if request.method == 'POST':
        chosen_skills = request.form.getlist('chosen_skill')
        # Validation for number of chosen skills needs num_skills_to_choose determined above
        if len(chosen_skills) != num_skills_to_choose:
            flash(f'Please choose exactly {num_skills_to_choose} skill(s). You chose {len(chosen_skills)}.', 'error')
            # Re-render template with all necessary context
            return render_template('create_character_skills.html',
                                   race_name=char_data.get('race_name'),
                                   class_name=class_name_to_display,
                                   background_name=char_data.get('background_name'),
                                   skill_options=skill_options_to_render, # Use the already processed list of dicts
                                   num_to_choose=num_skills_to_choose,
                                   saving_throws=saving_throws_to_render,
                                   submitted_skills=chosen_skills)

        session['new_character_data']['class_skill_proficiencies'] = chosen_skills
        session['new_character_data']['saving_throw_proficiencies'] = saving_throws_to_render # Already correctly formatted

        if api_class_details: # API Data source for other proficiencies
            api_fixed_proficiencies = api_class_details.get('proficiencies', [])
            armor_prof = []
            weapon_prof = []
            tool_prof = []
            # Example categorization logic (needs refinement based on actual API names/indices)
            for p in api_fixed_proficiencies:
                p_name = p.get('name', '').lower()
                p_index = p.get('index', '').lower()
                if any(keyword in p_name for keyword in ["armor", "shield"]) or \
                   any(keyword in p_index for keyword in ["armor", "shield"]):
                    armor_prof.append(p.get('name'))
                elif any(keyword in p_name for keyword in ["weapon", "bow", "sword", "axe", "mace", "dagger"]) or \
                     any(keyword in p_index for keyword in ["weapon", "bow", "sword", "axe", "mace", "dagger"]):
                    weapon_prof.append(p.get('name'))
                elif p.get('name'): # Catch tools and others not caught by above
                    tool_prof.append(p.get('name'))

            session['new_character_data']['armor_proficiencies'] = list(set(armor_prof)) # Ensure unique
            session['new_character_data']['weapon_proficiencies'] = list(set(weapon_prof))
            session['new_character_data']['tool_proficiencies_class_fixed'] = list(set(tool_prof))
            current_app.logger.info(f"API Path POST: Armor: {armor_prof}, Weapons: {weapon_prof}, Tools: {tool_prof}")

        elif class_id is not None: # Local DB source for other proficiencies
            selected_class_local = Class.query.get(class_id) # Should exist from GET
            session['new_character_data']['armor_proficiencies'] = json.loads(selected_class_local.proficiencies_armor or '[]')
            session['new_character_data']['weapon_proficiencies'] = json.loads(selected_class_local.proficiencies_weapons or '[]')
            session['new_character_data']['tool_proficiencies_class_fixed'] = json.loads(selected_class_local.proficiencies_tools or '[]')
            current_app.logger.info(f"Local DB Path POST: Using local proficiencies for class ID {class_id}")

        session.modified = True
        flash('Class skills and proficiencies saved!', 'success')
        return redirect(url_for('main.creation_hp'))

    # GET request rendering
    return render_template('create_character_skills.html',
                           race_name=char_data.get('race_name'),
                           class_name=class_name_to_display,
                           background_name=char_data.get('background_name'),
                           skill_options=skill_options_to_render, # Use the processed list of dicts
                           num_to_choose=num_skills_to_choose,
                           saving_throws=saving_throws_to_render,
                           submitted_skills=[])

@bp.route('/creation/hp', methods=['GET'])
@login_required
def creation_hp():
    char_data = session.get('new_character_data', {})
    if not char_data.get('armor_proficiencies') and not char_data.get('class_skill_proficiencies'):
        flash('Please complete the skills and proficiencies step first.', 'error')
        return redirect(url_for('main.creation_skills'))

    # Ensure skills and ability scores are present
    if not char_data.get('class_skill_proficiencies') or not char_data.get('ability_scores'):
        flash('Please complete skills and ability scores first.', 'error')
        # Redirect to skills if scores are done, else to stats
        if char_data.get('ability_scores'):
            return redirect(url_for('main.creation_skills'))
        else:
            return redirect(url_for('main.creation_stats'))

    api_class_details = char_data.get('api_class_details') # Expected to be in session
    class_id = char_data.get('class_id') # May be None
    # class_index = char_data.get('class_index') # Less critical
    class_name_from_session = char_data.get('class_name', 'Unknown Class')
    hit_die_value = None
    class_name_to_display = class_name_from_session # Default

    if api_class_details:
        class_name_to_display = api_class_details.get('name', class_name_from_session)
        hit_die_value = api_class_details.get('hit_die')
        if not isinstance(hit_die_value, int):
            current_app.logger.warning(f"API returned non-integer hit_die: {hit_die_value} for {class_name_to_display}. Defaulting to 8.")
            hit_die_value = 8 # Default if API data is malformed
        current_app.logger.info(f"HP Calc (API Path): Class: {class_name_to_display}, Hit Die Value: {hit_die_value}")
    elif class_id is not None:
        selected_class_local = Class.query.get(class_id)
        if not selected_class_local:
            flash('Selected class (local) not found. Please restart character creation.', 'error')
            return redirect(url_for('main.creation_class'))
        class_name_to_display = selected_class_local.name
        try:
            hit_die_value = int(selected_class_local.hit_die[1:]) if selected_class_local.hit_die else 8
        except (ValueError, TypeError, IndexError):
            flash('Error parsing local hit die. Defaulting HP calculation.', 'warning')
            current_app.logger.warning(f"Error parsing local hit_die: {selected_class_local.hit_die} for {class_name_to_display}. Defaulting to 8.")
            hit_die_value = 8
        current_app.logger.info(f"HP Calc (Local DB Path): Class: {class_name_to_display}, Hit Die Value: {hit_die_value}")
    else:
        flash('Class information is critically missing. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    ability_scores = char_data.get('ability_scores', {})
    if not ability_scores.get('CON') or not ability_scores.get('DEX'): # Should be caught by initial check, but good safeguard
        flash('Constitution or Dexterity scores not found. Please complete the stats step.', 'error')
        return redirect(url_for('main.creation_stats'))

    con_score = ability_scores.get('CON', 10)
    con_modifier = (con_score - 10) // 2
    max_hp = hit_die_value + con_modifier

    dex_score = ability_scores.get('DEX', 10)
    dex_modifier = (dex_score - 10) // 2
    ac_base = 10 + dex_modifier

    # Determine speed from API race details if available, else fallback
    speed = 30 # Default speed
    api_race_details_for_speed = char_data.get('api_race_details')
    if api_race_details_for_speed and 'speed' in api_race_details_for_speed:
        speed = api_race_details_for_speed['speed']
        current_app.logger.info(f"Speed {speed} loaded from API race details for {char_data.get('race_name')}.")
    elif char_data.get('race_id'): # Fallback to local DB if API details missing speed
        selected_race_local_for_speed = Race.query.get(char_data['race_id'])
        if selected_race_local_for_speed:
            speed = selected_race_local_for_speed.speed
            current_app.logger.info(f"Speed {speed} loaded from local DB for {char_data.get('race_name')}.")
        else:
            flash(f"Warning: Could not determine race speed from local DB for {char_data.get('race_name', 'selected race')}. Defaulting to {speed}.", 'warning')
    else: # No API details with speed and no local race_id
        flash(f"Warning: Race speed data unavailable for {char_data.get('race_name', 'selected race')}. Defaulting to {speed}.", 'warning')

    session['new_character_data']['speed'] = speed # Store resolved speed

    session['new_character_data']['max_hp'] = max_hp
    session['new_character_data']['current_hp'] = max_hp
    session['new_character_data']['armor_class_base'] = ac_base
    # Speed is already set in session above
    session.modified = True

    return render_template('create_character_hp.html',
                           race_name=char_data.get('race_name','Unknown Race'),
                           class_name=class_name_to_display,
                           background_name=char_data.get('background_name', 'N/A'),
                           ability_scores_summary=ability_scores,
                           max_hp=max_hp,
                           ac_base=ac_base,
                           speed=speed)

# Renamed for clarity and to distinguish from a potential future API-specific one if structures diverge significantly.
def _parse_local_db_starting_equipment(starting_equipment_data_json):
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

def _parse_api_equipment_data(api_starting_equipment, api_starting_equipment_options):
    fixed_items_api = []
    choice_groups_api = []

    for item_data in api_starting_equipment:
        if item_data.get('equipment') and item_data.get('quantity'):
            fixed_items_api.append({
                'equipment': {'name': item_data['equipment'].get('name'), 'index': item_data['equipment'].get('index')},
                'quantity': item_data['quantity']
            })

    for i, choice_block in enumerate(api_starting_equipment_options):
        group_id = f"choice_{i}"
        desc = choice_block.get('desc', f"Choose {choice_block.get('choose', 1)}")
        choose = choice_block.get('choose', 1)
        options_list = []

        options_source = choice_block.get('from', {}).get('options', [])
        option_set_type = choice_block.get('from', {}).get('option_set_type')

        if option_set_type == 'equipment_category':
            # Placeholder for equipment category choices
            category_ref = choice_block.get('from', {}).get('equipment_category', {})
            category_name = category_ref.get('name', category_ref.get('index', 'Unknown Category'))
            options_list.append({
                "name": f"Choose from category: {category_name}",
                "index": f"category-{category_ref.get('index', str(i))}", # Make a unique index
                "quantity": 1
            })
        elif option_set_type == 'options_array':
            for opt in options_source:
                if opt.get('option_type') == 'counted_reference' and opt.get('of'):
                    item_ref = opt.get('of')
                    options_list.append({
                        "name": item_ref.get('name', item_ref.get('index', f'unknown-item-ref-{str(i)}')),
                        "index": item_ref.get('index', f'unknown-item-ref-{str(i)}-{len(options_list)}'),
                        "quantity": opt.get('count', 1)
                    })
                elif opt.get('option_type') == 'reference' and opt.get('item'):
                    item_ref = opt.get('item')
                    options_list.append({
                        "name": item_ref.get('name', item_ref.get('index', f'unknown-item-{str(i)}')),
                        "index": item_ref.get('index', f'unknown-item-{str(i)}-{len(options_list)}'),
                        "quantity": 1
                    })
                elif opt.get('option_type') == 'choice': # Nested choice
                     # Placeholder for nested choices
                    nested_choice_desc = opt.get('choice', {}).get('desc', 'Nested Choice')
                    options_list.append({
                        "name": f"Further choice: {nested_choice_desc}",
                        "index": f"nested-choice-{str(i)}-{len(options_list)}",
                        "quantity": 1
                    })


        if options_list: # Only add group if there are processable options
            choice_groups_api.append({
                "id": group_id,
                "desc": desc,
                "choose": choose,
                "options": options_list
            })

    return fixed_items_api, choice_groups_api

@bp.route('/creation/equipment', methods=['GET', 'POST'])
@login_required
def creation_equipment():
    char_data = session.get('new_character_data', {})
    if not char_data.get('max_hp'): # Prerequisite from HP step
        flash('Please complete the HP & combat stats step first.', 'error')
        return redirect(url_for('main.creation_hp'))

    api_class_details = char_data.get('api_class_details') # Expected to be in session
    class_id = char_data.get('class_id') # May be None
    # class_index = char_data.get('class_index') # Less critical
    class_name_from_session = char_data.get('class_name', 'Unknown Class')
    spellcasting_ability_exists = False
    class_name_to_display = class_name_from_session # Default
    fixed_items = []
    choice_groups = []

    if api_class_details:
        class_name_to_display = api_class_details.get('name', class_name_from_session)
        spellcasting_ability_exists = bool(api_class_details.get('spellcasting'))
        api_starting_eq = api_class_details.get('starting_equipment', [])
        api_starting_eq_options = api_class_details.get('starting_equipment_options', [])
        fixed_items, choice_groups = _parse_api_equipment_data(api_starting_eq, api_starting_eq_options)
        current_app.logger.info(f"Equip (API): Class: {class_name_to_display}, Spellcasting: {spellcasting_ability_exists}, Fixed: {len(fixed_items)}, Choices: {len(choice_groups)}")
    elif class_id is not None:
        selected_class_local = Class.query.get(class_id)
        if not selected_class_local:
            flash('Selected class (local) not found. Please restart character creation.', 'error')
            return redirect(url_for('main.creation_class'))
        class_name_to_display = selected_class_local.name
        spellcasting_ability_exists = bool(selected_class_local.spellcasting_ability)
        class_starting_equipment_json = selected_class_local.starting_equipment or '[]' # This is for the old parser
        # The old parser `parse_starting_equipment` needs to be renamed or adapted.
        # For now, assuming it's renamed to _parse_local_db_starting_equipment
        fixed_items, choice_groups = _parse_local_db_starting_equipment(class_starting_equipment_json)
        current_app.logger.info(f"Equip (Local DB): Class: {class_name_to_display}, Spellcasting: {spellcasting_ability_exists}, Fixed: {len(fixed_items)}, Choices: {len(choice_groups)}")

    else:
        flash('Class information is critically missing for equipment selection. Please restart character creation.', 'error')
        session.pop('new_character_data', None)
        return redirect(url_for('main.creation_race'))

    background_equipment_string = char_data.get('background_equipment', '')

    if request.method == 'POST':
        chosen_equipment_list = []
        for item_data in fixed_items: # Fixed items should have 'equipment.name' and 'quantity'
            if item_data.get('equipment') and item_data['equipment'].get('name'):
                item_name = item_data['equipment']['name']
                chosen_equipment_list.append(f"{item_name} (x{item_data.get('quantity', 1)})")

        for group in choice_groups:
            group_id = group['id'] # e.g., "choice_0"
            # For 'choose' > 1, form might submit multiple values for the same group_id if using multi-select checkboxes
            # For 'choose' == 1 (radio/select), it's simpler.
            # Assuming 'choose' is 1 for now as per typical starting equipment choices.
            # If 'choose' can be > 1, request.form.getlist(group_id) would be needed.
            selected_option_indices = request.form.getlist(group_id) # Use getlist to handle multi-selects for "choose > 1"

            for selected_option_index in selected_option_indices:
                if selected_option_index.startswith("category-") or selected_option_index.startswith("nested-choice-"):
                    # Handle placeholder option: retrieve its name for now.
                    # In a real scenario, this would require another step or more complex UI.
                    found_placeholder_option = next((opt for opt in group['options'] if opt['index'] == selected_option_index), None)
                    if found_placeholder_option:
                         chosen_equipment_list.append(f"{found_placeholder_option['name']} (Selected Placeholder)")
                    continue

                found_option = next((opt for opt in group['options'] if opt['index'] == selected_option_index), None)
                if found_option:
                    chosen_equipment_list.append(f"{found_option['name']} (x{found_option.get('quantity',1)})")
                else:
                    current_app.logger.warning(f"Could not find selected option index '{selected_option_index}' in group '{group_id}'")

        if background_equipment_string: # Add background equipment string as is
            chosen_equipment_list.append(f"Background: {background_equipment_string}")

        session['new_character_data']['final_equipment'] = chosen_equipment_list
        session.modified = True
        flash('Starting equipment chosen!', 'success')

        if spellcasting_ability_exists:
            return redirect(url_for('main.creation_spells'))
        else:
            return redirect(url_for('main.creation_review'))

    return render_template('create_character_equipment.html',
                           race_name=char_data.get('race_name'),
                           class_name=class_name_to_display,
                           background_name=char_data.get('background_name'),
                           fixed_items=fixed_items,
                           choice_groups=choice_groups,
                           background_equipment_string=background_equipment_string)

@bp.route('/creation/spells', methods=['GET', 'POST'])
@login_required
def creation_spells():
    char_data = session.get('new_character_data', {})
    if not char_data.get('final_equipment'):
        flash('Please complete the equipment step first.', 'error')
        return redirect(url_for('main.creation_equipment'))

    api_class_details = char_data.get('api_class_details') # Expected
    api_class_level_1_details = char_data.get('api_class_level_1_details') # Expected
    class_id = char_data.get('class_id')
    class_name_from_session = char_data.get('class_name', 'Unknown Class')
    spellcasting_ability_exists = False
    class_name_to_display = class_name_from_session # Default

    if api_class_details:
        class_name_to_display = api_class_details.get('name', class_name_from_session)
        spellcasting_ability_exists = bool(api_class_details.get('spellcasting'))
        # api_class_level_1_details should already be in session from creation_class
        if not api_class_level_1_details: # Safety check if it's somehow missing
             flash('Critical class level 1 details are missing from session. Please re-select your class.', 'error')
             return redirect(url_for('main.creation_class'))
    elif class_id: # Fallback to local DB if API details are critically missing
        selected_class_local = Class.query.get(class_id)
        if selected_class_local:
            class_name_to_display = selected_class_local.name
            spellcasting_ability_exists = bool(selected_class_local.spellcasting_ability)
            # Note: spell counts will rely on local DB hardcoded values in this fallback
            current_app.logger.warning(f"creation_spells: Using local DB fallback for {class_name_to_display} as API details were missing.")
        else:
            flash('Selected class (local) not found. Please restart character creation.', 'error')
            return redirect(url_for('main.creation_class'))
    else:
        flash('Critical class information (API or local) missing. Please restart character creation.', 'error')
        return redirect(url_for('main.creation_race'))

    if not spellcasting_ability_exists:
        flash(f'{class_name_to_display} does not have spellcasting. Skipping spell selection.', 'info')
        return redirect(url_for('main.creation_review'))

    num_cantrips_to_select = 0
    num_level_1_spells_to_select = 0

    if api_class_level_1_details and api_class_details: # API Path for spell counts
        # Spellcasting data at level 1 is nested under 'spellcasting' key in level details
        level_1_spellcasting_info = api_class_level_1_details.get('spellcasting', {})
        num_cantrips_to_select = level_1_spellcasting_info.get('cantrips_known', 0)

        # For spells_known, it's more complex. Some classes (Sorcerer, Bard) have it directly.
        # Wizards get 6 L1 spells in their spellbook.
        # Clerics/Druids/Paladins prepare spells, so spells_known for selection here might be 0.
        if class_name_to_display == "Wizard":
            num_level_1_spells_to_select = 6
        else:
            # This key might not exist for all casters, or might be 0 for preparers
            num_level_1_spells_to_select = level_1_spellcasting_info.get('spells_known', 0)

        # Ensure they are not None
        num_cantrips_to_select = num_cantrips_to_select if num_cantrips_to_select is not None else 0
        num_level_1_spells_to_select = num_level_1_spells_to_select if num_level_1_spells_to_select is not None else 0
        current_app.logger.info(f"Spells (API): {class_name_to_display} - Cantrips: {num_cantrips_to_select}, L1 Spells: {num_level_1_spells_to_select}")

    elif class_id: # Local DB path for spell counts (existing logic)
        # This uses selected_class_local which should be defined if class_id is not None
        if class_name_to_display == "Wizard":
            num_cantrips_to_select = 3
            num_level_1_spells_to_select = 6
        elif class_name_to_display == "Sorcerer":
            num_cantrips_to_select = 4
            num_level_1_spells_to_select = 2
        # ... (other existing local class logic) ...
        elif class_name_to_display == "Bard":
            num_cantrips_to_select = 2
            num_level_1_spells_to_select = 4
        elif class_name_to_display == "Cleric": # Clerics prepare, but choose cantrips
            num_cantrips_to_select = 3
            num_level_1_spells_to_select = 0
        elif class_name_to_display == "Druid": # Druids prepare, but choose cantrips
            num_cantrips_to_select = 2
            num_level_1_spells_to_select = 0
        elif class_name_to_display == "Warlock":
            num_cantrips_to_select = 2
            num_level_1_spells_to_select = 2
        # Paladin & Ranger are half-casters, usually no spells at L1 from spellcasting feature itself
        # but might get some from sub-class or other features not covered here.
        # For now, default to 0 if not explicitly listed.
        current_app.logger.info(f"Spells (Local DB Fallback): {class_name_to_display} - Cantrips: {num_cantrips_to_select}, L1 Spells: {num_level_1_spells_to_select}")

    available_cantrips_api = []
    available_level_1_spells_api = []

    if api_class_details and class_index: # Prefer API for learnable spells
        try:
            learnable_spells_data = get_class_learnable_spells(class_index)
            for spell_data in learnable_spells_data:
                # The API for class spells returns a list of spell summaries.
                # We need to fetch full spell details to get the level.
                # This is inefficient here. A better approach would be if /classes/{index}/spells included level,
                # or if we had a local spell list that's kept up to date.
                # For now, we'll assume the Spell model is populated from API and query it,
                # but ideally, this step should avoid N+1 queries if possible.
                # The prompt says: "Filter learnable_spells_data for spell['level'] == 0"
                # This implies learnable_spells_data should have level.
                # Let's assume for now /api/classes/{class_index}/spells DOES return level,
                # or we adjust get_class_learnable_spells to fetch details if needed.
                # For this implementation, we'll filter based on a 'level' key presumed to be in spell_data.
                # This is a deviation if the API only returns summaries.
                # A quick check on dnd5eapi.co shows /api/classes/{class_index}/spells returns only name/index/url.
                # This means the requirement to filter learnable_spells_data by level is not directly possible
                # without either:
                #   a) fetching details for each spell (very inefficient)
                #   b) relying on local DB (which we are trying to move away from for this part)
                #   c) changing get_class_learnable_spells (out of scope for this subtask if it means new API functions)
                # Given the constraint, I will revert to using local DB for "available spells" for now,
                # as the API structure doesn't directly support filtering learnable spells by level from the /spells endpoint of a class.
                # The prompt "Filter learnable_spells_data for spell['level'] == 0" implies a structure that isn't there.
                # So, I will keep the existing local DB query for available_cantrips and available_level_1_spells.
                # This part of point 8 cannot be fully implemented as written due to API structure.
                pass # Keep existing local DB query below
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"API Error fetching learnable spells for '{class_index}': {e}")
            flash('Could not fetch learnable spells from API. Using local data as fallback.', 'warning')
        except Exception as e: # Catch other potential errors
            current_app.logger.error(f"Error processing learnable spells for '{class_index}': {e}")
            flash('Error processing learnable spells. Using local data as fallback.', 'warning')


    # Fetch available spells from local DB (fallback or primary if API structure is insufficient)
    search_pattern = f'%"{class_name_to_display}"%' # class_name_to_display is resolved from API or local
    available_cantrips = Spell.query.filter(Spell.level == 0, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all()
    available_level_1_spells = Spell.query.filter(Spell.level == 1, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all()

    # Skip spell selection if no spells/cantrips to choose (and not a preparer like Cleric/Druid for L1 spells)
    is_preparer_for_l1 = class_name_to_display in ["Cleric", "Druid", "Paladin"] # Paladin also prepares
    if num_cantrips_to_select == 0 and (num_level_1_spells_to_select == 0 and not is_preparer_for_l1) and request.method == 'GET':
        session['new_character_data']['chosen_cantrip_ids'] = []
        session['new_character_data']['chosen_level_1_spell_ids'] = []
        session.modified = True
        flash('No spells to select at Level 1 for your class in this step.', 'info')
        return redirect(url_for('main.creation_review'))

    if request.method == 'POST':
        chosen_cantrip_ids_str = request.form.getlist('chosen_cantrip')
        chosen_level_1_spell_ids_str = request.form.getlist('chosen_level_1_spell')
        errors = False
        if len(chosen_cantrip_ids_str) != num_cantrips_to_select:
            flash(f'Please select exactly {num_cantrips_to_select} cantrip(s). You chose {len(chosen_cantrip_ids_str)}.', 'error')
            errors = True

        # For classes that prepare L1 spells (Cleric, Druid, Paladin), num_level_1_spells_to_select will be 0 here.
        # So this check is fine.
        if len(chosen_level_1_spell_ids_str) != num_level_1_spells_to_select:
            flash(f'Please select exactly {num_level_1_spells_to_select} 1st-level spell(s). You chose {len(chosen_level_1_spell_ids_str)}.', 'error')
            errors = True

        if errors:
            return render_template('create_character_spells.html',
                                   race_name=char_data.get('race_name'),
                                   class_name=class_name_to_display,
                                   background_name=char_data.get('background_name'),
                                   available_cantrips=available_cantrips,
                                   num_cantrips_to_select=num_cantrips_to_select,
                                   available_level_1_spells=available_level_1_spells,
                                   num_level_1_spells_to_select=num_level_1_spells_to_select,
                                   submitted_cantrips=chosen_cantrip_ids_str,
                                   submitted_level_1_spells=chosen_level_1_spell_ids_str)
        try:
            session['new_character_data']['chosen_cantrip_ids'] = [int(id_str) for id_str in chosen_cantrip_ids_str]
            session['new_character_data']['chosen_level_1_spell_ids'] = [int(id_str) for id_str in chosen_level_1_spell_ids_str]
        except ValueError:
            flash('Invalid spell ID submitted. Please try again.', 'error')
            return render_template('create_character_spells.html',
                                   race_name=char_data.get('race_name'),
                                   class_name=class_name_to_display,
                                   background_name=char_data.get('background_name'),
                                   available_cantrips=available_cantrips,
                                   num_cantrips_to_select=num_cantrips_to_select,
                                   available_level_1_spells=available_level_1_spells,
                                   num_level_1_spells_to_select=num_level_1_spells_to_select,
                                   submitted_cantrips=chosen_cantrip_ids_str,
                                   submitted_level_1_spells=chosen_level_1_spell_ids_str)
        session.modified = True
        flash('Spells selected!', 'success')
        return redirect(url_for('main.creation_review'))

    return render_template('create_character_spells.html',
                           race_name=char_data.get('race_name'),
                           class_name=class_name_to_display,
                           background_name=char_data.get('background_name'),
                           available_cantrips=available_cantrips,
                           num_cantrips_to_select=num_cantrips_to_select,
                           available_level_1_spells=available_level_1_spells,
                           num_level_1_spells_to_select=num_level_1_spells_to_select,
                           submitted_cantrips=[],
                           submitted_level_1_spells=[])

@bp.route('/creation/review', methods=['GET', 'POST'])
@login_required
def creation_review():
    char_data = session.get('new_character_data', {})
    if not char_data.get('background_name'): # Check if background was selected
        flash('Please complete the background selection step first.', 'error')
        return redirect(url_for('main.creation_background'))
    if not char_data.get('ability_scores'): # Should be caught by earlier steps, but good safeguard
        flash('Please complete the core character creation steps first, starting with ability scores.', 'error')
        return redirect(url_for('main.creation_stats'))

    # Ensure API details are loaded if needed (e.g., direct navigation to review)
    api_class_details = char_data.get('api_class_details')
    api_class_level_1_details = char_data.get('api_class_level_1_details')
    class_id = char_data.get('class_id') # Local DB ID
    class_index = char_data.get('class_index') # API index

    if class_id is None and class_index: # API path likely
        if not api_class_details:
            try:
                current_app.logger.info(f"creation_review: Fetching class details for {class_index}")
                api_class_details = get_class_details(class_index)
                session['new_character_data']['api_class_details'] = api_class_details
            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"API Error fetching class details in review: {e}")
                flash('Error fetching critical class information. Please try class selection again.', 'error')
                return redirect(url_for('main.creation_class'))
            except Exception as e:
                current_app.logger.error(f"Error processing class details in review: {e}")
                flash('Error processing critical class information. Please try class selection again.', 'error')
                return redirect(url_for('main.creation_class'))

        if not api_class_level_1_details: # L1 details might be missing if spell step was skipped for non-caster
            try:
                current_app.logger.info(f"creation_review: Fetching L1 class details for {class_index}")
                api_class_level_1_details = get_class_level_details(class_index, 1)
                session['new_character_data']['api_class_level_1_details'] = api_class_level_1_details
            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"API Error fetching L1 class details in review: {e}")
                # Non-critical for review display itself, but POST might fail for spell slots.
                # For now, allow GET to proceed, POST will handle missing spell slots.
                flash('Warning: Could not fetch L1 class details from API for spell slot information.', 'warning')
            except Exception as e:
                current_app.logger.error(f"Error processing L1 class details in review: {e}")
                flash('Warning: Error processing L1 class details for spell slot information.', 'warning')
        session.modified = True


    race_name_for_review = char_data.get('race_name', "Unknown Race")
    class_name_for_review = char_data.get('class_name', "Unknown Class") # This should always be set from class selection step

    race_for_review_obj = None
    if char_data.get('race_id'):
        race_for_review_obj = Race.query.get(char_data.get('race_id'))

    char_class_obj_local = None # This is the local DB object
    if class_id: # class_id is the local DB id
        char_class_obj_local = Class.query.get(class_id)
        if not char_class_obj_local :
             # This implies class_id was in session but not found in DB - data inconsistency
            flash(f"Warning: Local class data for ID {class_id} not found. Character finalization might be incomplete for some DB fields.", "warning")
            # Allow to proceed with API data if available, otherwise POST might fail certain aspects.

    # If char_class_obj_local is None (either class_id was None or not found),
    # and we don't have api_class_details (e.g. API fetch failed earlier and user ended up here),
    # then we have a problem for the POST part. GET might still render basic names.
    if not char_class_obj_local and not api_class_details:
        flash('Critical class information is missing. Please restart character creation from class selection.', 'error')
        return redirect(url_for('main.creation_class'))


    cantrips = Spell.query.filter(Spell.id.in_(char_data.get('chosen_cantrip_ids', []))).all()
    level_1_spells = Spell.query.filter(Spell.id.in_(char_data.get('chosen_level_1_spell_ids', []))).all()
    all_skill_proficiencies = set(char_data.get('background_skill_proficiencies', []))
    all_skill_proficiencies.update(char_data.get('class_skill_proficiencies', []))
    all_tool_proficiencies = set(char_data.get('background_tool_proficiencies', []))
    all_tool_proficiencies.update(char_data.get('tool_proficiencies_class_fixed', []))

    # Aggregate languages from race and background
    all_language_proficiencies = set(char_data.get('race_languages', []))
    # Background languages might be a list with a "Choose X" string, or actual languages if parsed differently.
    # Assuming background_languages is a list of language names or descriptive strings for now.
    # If it contains "Choose X", it will be added as is. This might need further refinement if actual language choices are made earlier.
    background_langs = char_data.get('background_languages', [])
    if isinstance(background_langs, list):
        all_language_proficiencies.update(background_langs)
    elif isinstance(background_langs, str): # Handle if it's a single string
        all_language_proficiencies.add(background_langs)
    # No class languages are typically added directly at L1 beyond choices made, which would be part of other prof fields.

    # player_notes is handled by default in model

    if request.method == 'POST':
        character_name = request.form.get('character_name')
        alignment = request.form.get('alignment')
        char_description = request.form.get('character_description')
        if not character_name:
            flash('Character name is required.', 'error')
            return render_template('create_character_review.html', data=char_data,
                                   race_name=race_name_for_review, race=race_for_review_obj,
                                   class_name=class_name_for_review, char_class=char_class_obj_local, # Pass local obj for template
                                   cantrips=cantrips, level_1_spells=level_1_spells,
                                   all_skill_proficiencies=list(all_skill_proficiencies),
                                   all_tool_proficiencies=list(all_tool_proficiencies),
                                   all_language_proficiencies=list(all_language_proficiencies),
                                   submitted_name=character_name, submitted_alignment=alignment,
                                   submitted_description=char_description)

        current_skills_set = set(all_skill_proficiencies) # Use the already aggregated set
        current_tools_set = set(all_tool_proficiencies)   # Use the already aggregated set
        current_languages_set = set(all_language_proficiencies) # Use the already aggregated set

        new_char = Character(
            name=character_name,
            description=char_description,
            user_id=current_user.id,
            race_id=char_data.get('race_id'), # Can be None
            class_id=char_data.get('class_id'), # Can be None
            alignment=alignment,
            background_name=char_data.get('background_name'),
            background_proficiencies=json.dumps( 
                char_data.get('background_skill_proficiencies', []) +
                char_data.get('background_tool_proficiencies', []) +
                char_data.get('background_languages', [])
            ),
            adventure_log=json.dumps([]), 
            dm_allowed_level=1,
            current_xp=0,
            current_hit_dice=1,
            player_notes=""
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
        api_lvl1_details = char_data.get('api_class_level_1_details')

        if api_lvl1_details and 'spellcasting' in api_lvl1_details:
            spellcasting_data = api_lvl1_details['spellcasting']
            for i in range(1, 10): # Check for spell_slot_level_1 to spell_slot_level_9
                slot_key = f'spell_slots_level_{i}'
                if slot_key in spellcasting_data and spellcasting_data[slot_key] > 0:
                    spell_slots_L1[str(i)] = spellcasting_data[slot_key]
            current_app.logger.info(f"Spell slots from API L1 details: {spell_slots_L1}")
        elif char_class_obj_local and char_class_obj_local.spell_slots_by_level:
            try:
                all_class_level_slots = json.loads(char_class_obj_local.spell_slots_by_level)
                slots_for_char_level_1_list = all_class_level_slots.get("1") 
                if slots_for_char_level_1_list:
                    for spell_lvl_idx, num_slots in enumerate(slots_for_char_level_1_list):
                        if num_slots > 0: 
                            spell_slots_L1[str(spell_lvl_idx + 1)] = num_slots
                current_app.logger.info(f"Spell slots from local DB: {spell_slots_L1}")
            except json.JSONDecodeError:
                current_app.logger.error(f"Failed to parse local spell_slots_by_level for {char_class_obj_local.name}")
        else:
            current_app.logger.warning(f"Could not determine L1 spell slots for class {class_name_for_review}. Defaulting to empty.")

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
            speed=char_data.get('speed', 30), # Add speed here
            hit_dice_rolled="Max HP at L1", 
            proficiencies=json.dumps(level_1_proficiencies),
            features_gained=json.dumps(list(set( # Use set to ensure uniqueness
                [trait.get('name') for trait in char_data.get('api_race_details', {}).get('traits', []) if trait.get('name')] +
                [feature.get('name') for feature in char_data.get('api_class_level_1_details', {}).get('features', []) if feature.get('name')]
            ))),
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
    # Pass race_name_for_review and the potentially None race_for_review_obj
    return render_template('create_character_review.html', data=char_data, race_name=race_name_for_review, race=race_for_review_obj, char_class=char_class_obj, cantrips=cantrips, level_1_spells=level_1_spells, all_skill_proficiencies=list(all_skill_proficiencies), all_tool_proficiencies=list(all_tool_proficiencies), all_language_proficiencies=list(all_language_proficiencies), submitted_name=char_data.get('character_name_draft',''), submitted_alignment=char_data.get('alignment_draft',''), submitted_description=char_data.get('description_draft',''))

# ALL_SKILLS_LIST and XP_THRESHOLDS moved to app.utils

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
            
            # XP_THRESHOLDS is now imported from app.utils
            xp_for_next = XP_THRESHOLDS.get(current_actual_level, "N/A for current level")

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
    ai_response_text, _returned_chat_session, error_from_geminiai = geminiai(
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
    
    # Variable to hold the successfully parsed level if a level-up command occurs
    processed_levelup_level = None

    if ai_response_text:
        # Check for level-up command
        levelup_pattern = r"^(SYSTEM: LEVELUP GRANTED TO LEVEL (\d+))\s*$"
        levelup_match = re.search(levelup_pattern, ai_response_text, re.IGNORECASE | re.MULTILINE)

        if levelup_match:
            command_full_line = levelup_match.group(0)
            extracted_level_str = levelup_match.group(2)
            try:
                extracted_level_int_val = int(extracted_level_str)
                # Ensure character.dm_allowed_level is updated as per requirement 1
                character.dm_allowed_level = extracted_level_int_val 
                
                system_message_text = _("Congratulations! You can now advance to Level %(level)s.", level=extracted_level_int_val)
                log_entries.append({"sender": "system", "text": system_message_text})
                current_app.logger.info(f"Level up to {extracted_level_int_val} granted for character {character_id}.")

                ai_response_text = ai_response_text.replace(command_full_line, "").strip()
                processed_levelup_level = extracted_level_int_val # Store for JSON response
                
            except ValueError:
                current_app.logger.error(f"Extracted level '{extracted_level_str}' is not a valid integer for character {character_id}.")
                # processed_levelup_level remains None if parsing fails, so levelUpGranted won't be added
        
        # Add DM's response to log if it's not empty after potentially stripping the command
        if ai_response_text and not ai_response_text.isspace():
            log_entries.append({"sender": "dm", "text": ai_response_text})
        elif not levelup_match and (not ai_response_text or ai_response_text.isspace()): 
             current_app.logger.warning(f"AI response was empty or whitespace (and not a levelup command processing error) for char {character_id}. User message: '{user_message}'")

    character.adventure_log = json.dumps(log_entries)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to commit chat message and/or level up to DB for char {character_id}: {str(e)}")
        db.session.rollback()
        return jsonify(error=_("An error occurred saving your conversation to the chronicles.")), 500

    # Prepare the JSON response payload
    response_payload = {}
    if processed_levelup_level is not None:
        response_payload['levelUpGranted'] = True
        response_payload['newDmAllowedLevel'] = processed_levelup_level

    # Determine the reply text based on original_ai_response_text and if a level up occurred
    if original_ai_response_text or processed_levelup_level is not None:
        # If ai_response_text (potentially stripped of command) is not empty, use it.
        # Else, if a level up happened (even if command was the only text), use "DM's message processed."
        if ai_response_text and not ai_response_text.isspace():
            response_payload['reply'] = ai_response_text
        elif processed_levelup_level is not None: # Level up occurred, but no other text from AI after stripping command
            response_payload['reply'] = _("DM's message processed.")
        else: # Original AI response was empty/whitespace, and no level up occurred.
            current_app.logger.warning(f"Received no text (original was empty/whitespace) and no error from geminiai for char {character_id}. User message: '{user_message}'")
            response_payload['reply'] = _("The Dungeon Master ponders your words but remains silent for now...")
    else: # AI genuinely sent no text (original_ai_response_text was None or empty) AND no level up occurred
        current_app.logger.warning(f"Received no text and no error from geminiai for char {character_id}. User message: '{user_message}'")
        response_payload['reply'] = _("The Dungeon Master ponders your words but remains silent for now...")
        # Note: if processed_levelup_level was somehow set without original_ai_response_text, it's already in payload.

    return jsonify(response_payload), 200


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

    data = request.get_json()
    if not data:
        return jsonify(status="error", message="No data provided for short rest."), 400

    try:
        dice_to_spend = int(data.get('dice_to_spend'))
    except (ValueError, TypeError, TypeError):
        return jsonify(status="error", message="Invalid number of dice to spend."), 400

    if not character.char_class or not character.char_class.hit_die:
        return jsonify(status="error", message="Character class or hit die information missing."), 500

    if dice_to_spend <= 0:
        return jsonify(status="error", message="Number of dice to spend must be positive."), 400

    if dice_to_spend > character.current_hit_dice:
        return jsonify(status="error", message="Not enough Hit Dice available."), 400

    # Get latest CharacterLevel record for CON modifier and current HP/Max HP
    latest_level_data = CharacterLevel.query.filter_by(character_id=character.id).order_by(CharacterLevel.level_number.desc()).first()
    if not latest_level_data:
        return jsonify(status="error", message="Character has no level data."), 500

    con_modifier = (latest_level_data.constitution - 10) // 2

    try:
        hit_die_sides = int(character.char_class.hit_die[1:]) # e.g., "d8" -> 8
    except (TypeError, ValueError, IndexError):
        current_app.logger.error(f"Invalid hit_die format: {character.char_class.hit_die} for char {character_id}.")
        return jsonify(status="error", message="Invalid hit die format for character's class."), 500

    total_hp_recovered_from_rolls = 0
    rolls_detail_list = [] # Optional: to store individual roll results

    for _ in range(dice_to_spend):
        roll_result, _ = roll_dice(1, hit_die_sides) # roll_dice returns (sum, list_of_rolls)
        hp_from_this_die = roll_result + con_modifier
        # Standard D&D rule: if CON mod is negative, a die roll can still grant 0 HP min, not negative.
        # Some tables rule min 1 HP per die spent if character is conscious. For simplicity, min 0.
        hp_from_this_die = max(0, hp_from_this_die)
        total_hp_recovered_from_rolls += hp_from_this_die
        rolls_detail_list.append(f"{roll_result}+{con_modifier}={hp_from_this_die}")


    original_hp = latest_level_data.hp
    new_hp_calculated = min(latest_level_data.max_hp, latest_level_data.hp + total_hp_recovered_from_rolls)
    hp_actually_gained = new_hp_calculated - original_hp

    latest_level_data.hp = new_hp_calculated
    character.current_hit_dice -= dice_to_spend

    # If this is the character's current actual level, update main Character.hp too
    if latest_level_data.level_number == character.levels.order_by(CharacterLevel.level_number.desc()).first().level_number:
        character.hp = new_hp_calculated

    try:
        db.session.commit()
        current_app.logger.info(f"Character {character.name} (ID: {character.id}) spent {dice_to_spend} Hit Dice ({character.char_class.hit_die}) and recovered {hp_actually_gained} HP. Rolls: {', '.join(rolls_detail_list)}. New HP: {latest_level_data.hp}. HD Remaining: {character.current_hit_dice}")
        return jsonify(
            status="success",
            message=f"Recovered {hp_actually_gained} HP by spending {dice_to_spend} Hit Dice.",
            new_hp=latest_level_data.hp,
            max_hp=latest_level_data.max_hp,
            hit_dice_remaining=character.current_hit_dice,
            rolls_detail=", ".join(rolls_detail_list), # Send details to client
            hp_actually_gained=hp_actually_gained # For client to display exact amount gained
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during short rest DB commit for char {character_id}: {str(e)}")
        return jsonify(status="error", message="Database error during short rest."), 500


@bp.route('/character/<int:character_id>/rest/long', methods=['POST'])
@login_required
def long_rest(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    latest_character_level = CharacterLevel.query.filter_by(character_id=character.id).order_by(CharacterLevel.level_number.desc()).first()
    if not latest_character_level:
        return jsonify(status="error", message="Character level data not found."), 404

    if not character.char_class:
        return jsonify(status="error", message="Character class information not found."), 500

    # HP Recovery
    latest_character_level.hp = latest_character_level.max_hp
    character.hp = latest_character_level.max_hp # Keep main Character object consistent

    # Hit Dice Recovery
    # Recover half of the character's total number of Hit Dice (minimum of 1 die)
    # This is a common interpretation, though SRD says "regain spent HD". Simpler to set to max for now.
    # For this implementation, we restore ALL hit dice, as per a full rest.
    character.current_hit_dice = latest_character_level.level_number
    if character.current_hit_dice < 1: # Should not happen if level_number is always >= 1
        character.current_hit_dice = 1

    # Spell Slot Recovery
    new_spell_slots_snapshot_dict = {}
    if character.char_class.spell_slots_by_level:
        try:
            all_class_slots_data = json.loads(character.char_class.spell_slots_by_level)
            # Slots for the character's current class level
            slots_for_character_level_list = all_class_slots_data.get(str(latest_character_level.level_number))

            if slots_for_character_level_list:
                for spell_level_index, num_slots in enumerate(slots_for_character_level_list):
                    if num_slots > 0:
                        # Spell levels are 1-indexed in snapshot keys
                        new_spell_slots_snapshot_dict[str(spell_level_index + 1)] = num_slots

            latest_character_level.spell_slots_snapshot = json.dumps(new_spell_slots_snapshot_dict)
            current_app.logger.info(f"Spell slots for char {character_id} L{latest_character_level.level_number} reset to: {new_spell_slots_snapshot_dict}")

        except json.JSONDecodeError:
            current_app.logger.error(f"Could not parse spell_slots_by_level for class {character.char_class.name} during long rest for char {character_id}.")
            # Not returning error, as HP/HD might still be fine. Log is important.
        except Exception as e:
            current_app.logger.error(f"Unexpected error processing spell slots during long rest for char {character_id}: {str(e)}")

    try:
        db.session.commit()
        current_app.logger.info(f"Character {character.name} (ID: {character.id}) completed a long rest. HP, Hit Dice, and Spell Slots restored.")
        return jsonify(
            status="success",
            message=f"{character.name} takes a long rest. HP, Hit Dice, and spell slots have been restored.",
            new_hp=latest_character_level.hp,
            max_hp=latest_character_level.max_hp,
            hit_dice_remaining=character.current_hit_dice,
            spell_slots_refreshed=True,
            new_spell_slots_snapshot=new_spell_slots_snapshot_dict # Send the new state
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during long rest DB commit for char {character_id}: {str(e)}")
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
    new_features_at_this_level_names = level_up_data.get('new_features_list', []) # Renamed for clarity
    asi_count_at_this_level = level_up_data.get('asi_count_available', 0)
    gained_proficiencies_from_features = level_up_data.get('gained_proficiencies', {'skills': [], 'tools': [], 'languages': [], 'armor': [], 'weapons': [], 'saving_throws': []})


    if request.method == 'GET': 
        if char_class.level_specific_data:
            try:
                level_specific_progression = json.loads(char_class.level_specific_data)
                current_level_prog_data = level_specific_progression.get(str(new_level_number))
                if current_level_prog_data:
                    new_features_at_this_level_names = current_level_prog_data.get('features', [])
                    asi_count_at_this_level = current_level_prog_data.get('asi_count', 0)

                    # Parse features for proficiencies
                    # This is a simplified approach. A robust solution needs structured feature data.
                    gained_proficiencies_from_features = {'skills': [], 'tools': [], 'languages': [], 'armor': [], 'weapons': [], 'saving_throws': []}
                    for feature_name in new_features_at_this_level_names:
                        if feature_name.startswith("Skill Proficiency:"):
                            prof_name = feature_name.replace("Skill Proficiency:", "").strip()
                            if prof_name: gained_proficiencies_from_features['skills'].append(prof_name)
                        elif feature_name.startswith("Tool Proficiency:"):
                            prof_name = feature_name.replace("Tool Proficiency:", "").strip()
                            if prof_name: gained_proficiencies_from_features['tools'].append(prof_name)
                        elif feature_name.startswith("Language Proficiency:"):
                            prof_name = feature_name.replace("Language Proficiency:", "").strip()
                            if prof_name: gained_proficiencies_from_features['languages'].append(prof_name)
                        elif feature_name.startswith("Armor Proficiency:"):
                            prof_name = feature_name.replace("Armor Proficiency:", "").strip()
                            if prof_name: gained_proficiencies_from_features['armor'].append(prof_name)
                        elif feature_name.startswith("Weapon Proficiency:"):
                            prof_name = feature_name.replace("Weapon Proficiency:", "").strip()
                            if prof_name: gained_proficiencies_from_features['weapons'].append(prof_name)
                        elif feature_name.startswith("Saving Throw Proficiency:"):
                            prof_name = feature_name.replace("Saving Throw Proficiency:", "").strip()
                            if prof_name: gained_proficiencies_from_features['saving_throws'].append(prof_name)

            except json.JSONDecodeError:
                current_app.logger.error(f"Could not parse level_specific_data for class {char_class.name}")
                flash("Error reading class progression data.", "error")
        
        level_up_data['new_features_list'] = new_features_at_this_level_names # Store the raw names
        level_up_data['asi_count_available'] = asi_count_at_this_level
        level_up_data['gained_proficiencies'] = gained_proficiencies_from_features # Store parsed proficiencies
        level_up_data.setdefault('chosen_asi', {}) 
        level_up_data.setdefault('asi_choices_log', [])
        session.modified = True
            
    if request.method == 'POST':
        # Ensure gained_proficiencies is loaded from session if POST, as GET block might not run
        # or might be overwritten if we POST multiple times (e.g. validation error)
        # However, 'gained_proficiencies' should ideally be set during GET and remain unchanged during POST
        # as features are determined when the page loads, not by user POST data on this specific form.
        # So, we rely on it being correctly populated in the session from the GET request.
        gained_proficiencies_from_features = level_up_data.get('gained_proficiencies', {'skills': [], 'tools': [], 'languages': [], 'armor': [], 'weapons': [], 'saving_throws': []})

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
        # 'chosen_features_details_list' should just be the names from 'new_features_list'
        level_up_data['chosen_features_details_list'] = level_up_data.get('new_features_list', [])
        # 'gained_proficiencies' is already updated in session from GET part
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
                            new_features=level_up_data.get('new_features_list', []), # Use 'new_features_list' which holds the names
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
    
    # Fetch the Class object to pass to the template
    char_class = Class.query.get(level_up_data.get('class_id'))
    if char_class:
        review_data['char_class'] = char_class
    else:
        # Handle case where class_id might be invalid or not found, though session should be reliable.
        # Setting to None or a default object, or flashing an error might be options.
        # For now, if not found, it won't be in review_data, template needs to handle potential absence.
        current_app.logger.warning(f"Could not find class with ID {level_up_data.get('class_id')} during level_up_review for char {character_id}.")
        review_data['char_class'] = None # Explicitly set to None if not found

    return render_template('level_up/level_up_review.html', level_up_data=level_up_data, **review_data)


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
        armor_class=current_level_entry.armor_class, # AC changes are not handled by this level up feature step yet
        # proficiencies=current_level_entry.proficiencies, # Placeholder - should update if new profs gained
        features_gained=json.dumps(combined_features_log), 
        spells_known_ids=json.dumps(all_known_spell_ids), 
        spells_prepared_ids=current_level_entry.spells_prepared_ids, # Placeholder for prepared casters
        spell_slots_snapshot=json.dumps(new_spell_slots_snapshot_dict), 
        created_at=datetime.utcnow()
    )

    # Merge proficiencies
    existing_proficiencies_json = current_level_entry.proficiencies or '{}'
    try:
        existing_proficiencies_dict = json.loads(existing_proficiencies_json)
        if not isinstance(existing_proficiencies_dict, dict): # Ensure it's a dict
             current_app.logger.warning(f"Existing proficiencies for char {character_id} L{current_level_entry.level_number} was not a dict. Resetting. Value: {existing_proficiencies_json}")
             existing_proficiencies_dict = {}
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to parse existing_proficiencies_json for char {character_id} L{current_level_entry.level_number}. Value: {existing_proficiencies_json}")
        existing_proficiencies_dict = {}

    gained_proficiencies_from_session = level_up_data.get('gained_proficiencies', {})

    merged_proficiencies_dict = existing_proficiencies_dict.copy()

    for prof_type, prof_list in gained_proficiencies_from_session.items():
        if not prof_list: # Skip if the list of gained proficiencies for this type is empty
            continue

        # Ensure the proficiency type category exists in merged_proficiencies_dict
        if prof_type not in merged_proficiencies_dict:
            merged_proficiencies_dict[prof_type] = []
        elif not isinstance(merged_proficiencies_dict[prof_type], list): # Ensure it's a list
            current_app.logger.warning(f"Proficiency type '{prof_type}' in existing profs for char {character_id} was not a list. Resetting for this type. Value: {merged_proficiencies_dict[prof_type]}")
            merged_proficiencies_dict[prof_type] = []

        for prof_name in prof_list:
            if prof_name not in merged_proficiencies_dict[prof_type]:
                merged_proficiencies_dict[prof_type].append(prof_name)

    new_level_data.proficiencies = json.dumps(merged_proficiencies_dict)


    # Update the main Character object with new HP, Max HP, and AC
    character.hp = new_level_data.hp
    character.max_hp = new_level_data.max_hp
    # AC is not changed by features in this step, it uses the value from the previous level data
    # which is already set in new_level_data.armor_class.
    # character.armor_class = new_level_data.armor_class # This line is effectively redundant if AC isn't changing

    # Update character's current_hit_dice to new level number
    character.current_hit_dice = new_level_data.level_number
    if character.current_hit_dice < 1: # Should always be >= 1
        character.current_hit_dice = 1

    db.session.add(new_level_data)
    # character object is already in the session, so changes will be committed.
    try:
        db.session.commit() # First commit for level up data

        # Generate character sheet text and append to adventure log
        char_class = Class.query.get(character.class_id) # Fetch class object
        known_spell_ids_list = json.loads(new_level_data.spells_known_ids or '[]')
        known_spell_objects = Spell.query.filter(Spell.id.in_(known_spell_ids_list)).all() if known_spell_ids_list else []

        sheet_text = generate_character_sheet_text(character, new_level_data, char_class, known_spell_objects)
        dm_update_message = f"SYSTEM: {character.name} has reached Level {new_level_data.level_number}. Their character sheet has been updated as follows:\n\n{sheet_text}"

        try:
            log_entries = json.loads(character.adventure_log or '[]')
            if not isinstance(log_entries, list):
                log_entries = []
        except json.JSONDecodeError:
            log_entries = []

        log_entries.append({"sender": "system", "text": dm_update_message})
        character.adventure_log = json.dumps(log_entries)
        db.session.commit() # Second commit for adventure log update

        session.pop('level_up_data', None) 
        # Enhanced flash message and server log
        flash(f"Successfully leveled up to Level {new_level_data.level_number}! Your character sheet is updated and ready for your DM.", "success")
        current_app.logger.info(f"Character '{character.name}' (ID: {character.id}) successfully leveled up to Level {new_level_data.level_number}. DM notified (conceptually via adventure log).")
        return redirect(url_for('main.adventure', character_id=character_id))
    except Exception as e:
        db.session.rollback() # Rollback any pending changes from both potential commits if error
        current_app.logger.error(f"Error applying level up or updating adventure log for char {character_id} to L{new_level_data.level_number}: {str(e)}")
        flash("Error applying level up. Please try again.", "error")
        return redirect(url_for('main.level_up_start', character_id=character_id))

@bp.route('/character/<int:character_id>/update_hp', methods=['POST'])
@login_required
def update_hp(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    data = request.get_json()
    if not data:
        return jsonify(status="error", message="No data provided"), 400

    try:
        new_hp = int(data.get('new_hp'))
        level_number_for_update = int(data.get('level_number_for_update'))
    except (ValueError, TypeError):
        return jsonify(status="error", message="Invalid HP or level number format."), 400

    # Fetch the specific CharacterLevel record that the user is viewing and intending to update
    character_level_record = CharacterLevel.query.filter_by(
        character_id=character.id,
        level_number=level_number_for_update
    ).first()

    if not character_level_record:
        return jsonify(status="error", message="Character level data not found for the specified level."), 404

    if new_hp < 0:
        return jsonify(status="error", message="HP cannot be negative."), 400
    if new_hp > character_level_record.max_hp:
        return jsonify(status="error", message=f"HP cannot exceed Max HP ({character_level_record.max_hp})."), 400

    character_level_record.hp = new_hp

    # If the updated level is the character's current actual level, also update the main Character.hp
    # Fetch all level records for the character to determine current and achieved levels
    all_character_levels = CharacterLevel.query.filter_by(character_id=character.id).order_by(CharacterLevel.level_number).all()
    current_actual_level_number = 0
    if all_character_levels:
        current_actual_level_number = all_character_levels[-1].level_number

    if character_level_record.level_number == current_actual_level_number:
        character.hp = new_hp
        # character.max_hp is generally only updated on level up, not here.

    try:
        db.session.commit()
        return jsonify(
            status="success",
            message="HP updated!",
            new_hp=character_level_record.hp,
            max_hp=character_level_record.max_hp, # Return max_hp for consistency, though it doesn't change here
            level_updated=character_level_record.level_number
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating HP for char {character_id}, level {level_number_for_update}: {str(e)}")
        return jsonify(status="error", message="Database error updating HP."), 500

@bp.route('/character/<int:character_id>/update_notes', methods=['POST'])
@login_required
def update_notes(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        return jsonify(status="error", message="Unauthorized"), 403

    data = request.get_json()
    if data is None: # Check if data is None, which happens if request body is empty or not JSON
        return jsonify(status="error", message="No data provided or not JSON."), 400

    player_notes_from_request = data.get('player_notes')
    # Allow empty notes, so no specific check for empty string beyond what data.get provides (None if key missing)

    if player_notes_from_request is None and 'player_notes' not in data:
         # Key 'player_notes' was not in the request JSON at all
        return jsonify(status="error", message="Invalid request: 'player_notes' key missing."), 400

    character.player_notes = player_notes_from_request

    try:
        db.session.commit()
        current_app.logger.info(f"Player notes updated for character {character_id}.")
        return jsonify(status="success", message="Notes saved!")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving player notes for char {character_id}: {str(e)}")
        return jsonify(status="error", message="Database error while saving notes."), 500
