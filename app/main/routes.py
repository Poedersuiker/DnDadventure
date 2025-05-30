import json
import os
import google.generativeai as genai
import re
from flask import render_template, redirect, url_for, flash, request, session, get_flashed_messages, jsonify, current_app
from flask_babel import _
from flask_login import login_required, current_user
from sqlalchemy.orm import aliased
from app import db
from app.models import User, Character, Race, Class, Spell, Setting, Item, Coinage, CharacterLevel, Weapon, CharacterWeaponAssociation # Updated import
from app.utils import roll_dice, parse_coinage, ALL_SKILLS_LIST, XP_THRESHOLDS, generate_character_sheet_text
from app.gemini import geminiai, GEMINI_DM_SYSTEM_RULES
from datetime import datetime
from app.main import bp

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

@bp.route('/create_character', methods=['GET'])
@login_required
def create_character():
    return redirect(url_for('main.creation_race'))

@bp.route('/delete_character/<int:character_id>', methods=['POST'])
@login_required
def delete_character(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id:
        flash('You do not have permission to delete this character.', 'error')
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

    character.adventure_log = json.dumps([])
    character.current_xp = 0
    character.dm_allowed_level = 1

    level_1_data = CharacterLevel.query.filter_by(character_id=character.id, level_number=1).first()
    if level_1_data:
        CharacterLevel.query.filter(CharacterLevel.character_id == character.id, CharacterLevel.level_number > 1).delete()
        current_app.logger.info(f"Character {character_id} progress cleared. Kept Level 1 data, removed other levels.")
    else:
        current_app.logger.warning(f"Character {character_id} progress cleared, but no Level 1 snapshot found. XP and DM level reset.")

    Item.query.filter_by(character_id=character.id).delete()
    Coinage.query.filter_by(character_id=character.id).delete()

    CharacterWeaponAssociation.query.filter_by(character_id=character_id).delete()

    db.session.commit()
    flash('Adventure progress cleared. Your character has been reset. Inventory, coinage, and weapons have been cleared.', 'success')
    return redirect(url_for('main.index'))

@bp.route('/creation/race', methods=['GET', 'POST'])
@login_required
def creation_race():
    if request.method == 'GET':
        session['new_character_data'] = {}
        races = Race.query.all()
        if not races: flash('No races found in the database. Please run the population script.', 'error')
        return render_template('create_character_race.html', races=races or [])
    race_id = request.form.get('race_id')
    selected_race = Race.query.get(int(race_id)) if race_id and race_id.isdigit() else None
    if selected_race:
        session['new_character_data'].update({'race_id': selected_race.id, 'race_name': selected_race.name})
        session.modified = True; flash(f'{selected_race.name} selected!', 'success')
        return redirect(url_for('main.creation_class'))
    flash('Please select a valid race.', 'error'); return render_template('create_character_race.html', races=Race.query.all())

@bp.route('/creation/class', methods=['GET', 'POST'])
@login_required
def creation_class():
    if not session.get('new_character_data', {}).get('race_id'): flash('Please select a race first.', 'error'); return redirect(url_for('main.creation_race'))
    if request.method == 'GET':
        classes = Class.query.all()
        if not classes: flash('No classes found. Run population script.', 'error')
        return render_template('create_character_class.html', classes=classes or [], race_name=session['new_character_data'].get('race_name'))
    class_id_str = request.form.get('class_id')
    selected_class = Class.query.get(int(class_id_str)) if class_id_str and class_id_str.isdigit() else None
    if selected_class:
        session['new_character_data'].update({'class_id': selected_class.id, 'class_name': selected_class.name})
        session.modified = True; flash(f'{selected_class.name} selected!', 'success')
        return redirect(url_for('main.creation_stats'))
    flash('Please select a valid class.', 'error'); return render_template('create_character_class.html', classes=Class.query.all(), race_name=session['new_character_data'].get('race_name'))

@bp.route('/creation/stats', methods=['GET', 'POST'])
@login_required
def creation_stats():
    char_data = session.get('new_character_data', {})
    if not char_data.get('race_id') or not char_data.get('class_id'):
        flash('Please select race and class first.', 'error'); return redirect(url_for('main.creation_class'))
    selected_race = Race.query.get(char_data['race_id'])
    selected_class = Class.query.get(char_data['class_id'])
    if not selected_race or not selected_class:
        flash('Race or class data missing.', 'error'); return redirect(url_for('main.creation_race'))

    racial_bonuses_list = json.loads(selected_race.ability_score_increases or '[]')
    primary_ability = selected_class.spellcasting_ability or "N/A"
    standard_array = [15, 14, 13, 12, 10, 8]
    racial_bonuses_dict = {bonus['name']: bonus['bonus'] for bonus in racial_bonuses_list}

    if request.method == 'POST' and request.form.get('action') != 'roll_stats':
        # ... (stat processing logic - assuming it's correct and leads to setting session data)
        # For brevity, direct jump to success if logic were here
        session['new_character_data']['ability_scores'] = {} # Placeholder for actual scores
        session.modified = True
        return redirect(url_for('main.creation_background'))

    return render_template('create_character_stats.html',
                           race_name=selected_race.name, class_name=selected_class.name,
                           racial_bonuses_dict=racial_bonuses_dict, primary_ability=primary_ability,
                           standard_array=standard_array, rolled_stats=session.get('rolled_stats'),
                           submitted_scores=request.form if request.method == 'POST' else None)


@bp.route('/creation/background', methods=['GET', 'POST'])
@login_required
def creation_background():
    if not session.get('new_character_data', {}).get('ability_scores'):
        flash('Please set ability scores first.', 'error'); return redirect(url_for('main.creation_stats'))
    # ... (background selection logic)
    if request.method == 'POST':
        # Example: session['new_character_data']['background_name'] = request.form.get('background_name')
        session.modified = True
        return redirect(url_for('main.creation_skills'))
    return render_template('create_character_background.html', backgrounds={}, race_name=session['new_character_data'].get('race_name'), class_name=session['new_character_data'].get('class_name'))

@bp.route('/creation/skills', methods=['GET', 'POST'])
@login_required
def creation_skills():
    if not session.get('new_character_data', {}).get('background_name'):
        flash('Please select a background first.', 'error'); return redirect(url_for('main.creation_background'))
    # ... (skill selection logic)
    if request.method == 'POST':
        # Example: session['new_character_data']['class_skill_proficiencies'] = request.form.getlist('chosen_skill')
        session.modified = True
        return redirect(url_for('main.creation_hp'))
    selected_class = Class.query.get(session['new_character_data']['class_id'])
    return render_template('create_character_skills.html', skill_options=json.loads(selected_class.skill_proficiencies_options or '[]'), num_to_choose=selected_class.skill_proficiencies_option_count, saving_throws=json.loads(selected_class.proficiency_saving_throws or '[]'), race_name=session['new_character_data'].get('race_name'), class_name=selected_class.name, background_name=session['new_character_data'].get('background_name'))

@bp.route('/creation/hp', methods=['GET'])
@login_required
def creation_hp():
    if not session.get('new_character_data', {}).get('class_skill_proficiencies'): # Example check
        flash('Please complete skills first.', 'error'); return redirect(url_for('main.creation_skills'))
    # ... (HP calculation logic)
    # Example: session['new_character_data']['max_hp'] = 10
    session.modified = True
    return render_template('create_character_hp.html', max_hp=session['new_character_data'].get('max_hp',0), ac_base=session['new_character_data'].get('armor_class_base',0), speed=session['new_character_data'].get('speed',0), race_name=session['new_character_data'].get('race_name'), class_name=session['new_character_data'].get('class_name'), background_name=session['new_character_data'].get('background_name'), ability_scores_summary=session['new_character_data'].get('ability_scores',{}))

@bp.route('/creation/equipment', methods=['GET', 'POST'])
@login_required
def creation_equipment():
    if not session.get('new_character_data', {}).get('max_hp'):
        flash('Please set HP first.', 'error'); return redirect(url_for('main.creation_hp'))
    selected_class = Class.query.get(session['new_character_data']['class_id'])
    # ... (equipment selection logic)
    if request.method == 'POST':
        # Example: session['new_character_data']['final_equipment'] = []
        session.modified = True
        if selected_class and selected_class.spellcasting_ability: return redirect(url_for('main.creation_spells'))
        return redirect(url_for('main.creation_review'))
    # ...
    return render_template('create_character_equipment.html', fixed_items=[], choice_groups=[], background_equipment_string="", race_name=session['new_character_data'].get('race_name'), class_name=selected_class.name, background_name=session['new_character_data'].get('background_name'))

@bp.route('/creation/spells', methods=['GET', 'POST'])
@login_required
def creation_spells():
    if not session.get('new_character_data', {}).get('final_equipment'):
        flash('Please select equipment first.', 'error'); return redirect(url_for('main.creation_equipment'))
    # ... (spell selection logic)
    if request.method == 'POST':
        # Example: session['new_character_data']['chosen_cantrip_ids'] = []
        session.modified = True
        return redirect(url_for('main.creation_review'))
    # ...
    return render_template('create_character_spells.html', available_cantrips=[], num_cantrips_to_select=0, available_level_1_spells=[], num_level_1_spells_to_select=0, race_name=session['new_character_data'].get('race_name'), class_name=Class.query.get(session['new_character_data']['class_id']).name, background_name=session['new_character_data'].get('background_name'))

@bp.route('/creation/review', methods=['GET', 'POST'])
@login_required
def creation_review():
    char_data = session.get('new_character_data', {})
    if not char_data.get('ability_scores'): # Basic check
        flash('Core data missing. Please restart creation.', 'error'); return redirect(url_for('main.creation_race'))

    race = Race.query.get(char_data.get('race_id'))
    char_class_obj = Class.query.get(char_data.get('class_id'))
    if not race or not char_class_obj:
        flash('Race or Class data invalid. Please restart.', 'error'); return redirect(url_for('main.creation_race'))

    # Consolidate details for display
    display_data = {**char_data} # Shallow copy
    display_data['race_name'] = race.name
    display_data['class_name'] = char_class_obj.name
    display_data['cantrips'] = Spell.query.filter(Spell.id.in_(char_data.get('chosen_cantrip_ids', []))).all()
    display_data['level_1_spells'] = Spell.query.filter(Spell.id.in_(char_data.get('chosen_level_1_spell_ids', []))).all()

    all_skill_proficiencies = set(char_data.get('background_skill_proficiencies', [])) | set(char_data.get('class_skill_proficiencies', []))
    display_data['all_skill_proficiencies'] = list(all_skill_proficiencies)
    # ... (similar for tools, languages)

    if request.method == 'POST':
        character_name = request.form.get('character_name')
        alignment = request.form.get('alignment')
        char_description = request.form.get('character_description')
        if not character_name:
            flash('Character name is required.', 'error')
            return render_template('create_character_review.html', data=display_data, race=race, char_class=char_class_obj, submitted_name=character_name, submitted_alignment=alignment, submitted_description=char_description)

        new_char = Character(
            name=character_name, description=char_description, user_id=current_user.id,
            race_id=char_data['race_id'], class_id=char_data['class_id'], alignment=alignment,
            background_name=char_data.get('background_name'),
            background_proficiencies=json.dumps(char_data.get('background_skill_proficiencies', []) + char_data.get('background_tool_proficiencies', []) + char_data.get('background_languages', [])),
            adventure_log=json.dumps([]), dm_allowed_level=1, current_xp=0, current_hit_dice=1, player_notes=""
        )
        db.session.add(new_char)
        db.session.flush() # Flush to get new_char.id for associations

        level_1_proficiencies = {
            'skills': list(all_skill_proficiencies),
            'tools': list(set(char_data.get('background_tool_proficiencies', [])) | set(char_data.get('tool_proficiencies_class_fixed', []))),
            'languages': list(set(char_data.get('background_languages', []))),
            'armor': char_data.get('armor_proficiencies', []),
            'weapons': char_data.get('weapon_proficiencies', []),
            'saving_throws': char_data.get('saving_throw_proficiencies', [])
        }
        # ... (spell slot calculation for level 1) ...
        spell_slots_L1 = {} # Placeholder

        new_char_level_1 = CharacterLevel(
            character_id=new_char.id, level_number=1, xp_at_level_up=0,
            strength=char_data['ability_scores'].get('STR', 10), dexterity=char_data['ability_scores'].get('DEX', 10),
            constitution=char_data['ability_scores'].get('CON', 10), intelligence=char_data['ability_scores'].get('INT', 10),
            wisdom=char_data['ability_scores'].get('WIS', 10), charisma=char_data['ability_scores'].get('CHA', 10),
            hp=char_data.get('max_hp', 0), max_hp=char_data.get('max_hp', 0),
            armor_class=char_data.get('armor_class_base'), hit_dice_rolled="Max HP at L1",
            proficiencies=json.dumps(level_1_proficiencies),
            features_gained=json.dumps(["Initial class features", "Initial race features"]), 
            spells_known_ids=json.dumps(char_data.get('chosen_cantrip_ids', []) + char_data.get('chosen_level_1_spell_ids', [])),
            spells_prepared_ids=json.dumps([]), spell_slots_snapshot=json.dumps(spell_slots_L1),
            created_at=datetime.utcnow()
        )
        db.session.add(new_char_level_1)

        # ... (equipment and coinage parsing/adding logic) ...

        # Assign default Dagger
        dagger = Weapon.query.filter_by(name="Dagger").first()
        if dagger:
            new_weapon_association = CharacterWeaponAssociation(
                character_id=new_char.id,
                weapon_id=dagger.id,
                quantity=1,
                is_equipped_main_hand=False,
                is_equipped_off_hand=False
            )
            db.session.add(new_weapon_association)
            current_app.logger.info(f"Assigned Dagger to new character {new_char.name}")
        else:
            current_app.logger.warning("Could not find 'Dagger' in Weapon table to assign to new character.")

        db.session.commit() 
        session.pop('new_character_data', None) 
        flash('Character created successfully!', 'success')
        return redirect(url_for('main.index'))

    return render_template('create_character_review.html', data=display_data, race=race, char_class=char_class_obj, submitted_name=char_data.get('character_name_draft',''), submitted_alignment=char_data.get('alignment_draft',''), submitted_description=char_data.get('description_draft',''))


@bp.route('/<int:character_id>/adventure', methods=['GET', 'POST'])
@login_required
def adventure(character_id):
    character = Character.query.get_or_404(character_id)

    if character.user_id != current_user.id:
        flash(_('This character does not belong to you.'))
        return redirect(url_for('main.index'))

    character_levels = CharacterLevel.query.filter_by(character_id=character.id).order_by(CharacterLevel.level_number).all()
    if not character_levels:
        flash(_("Character has no level data. Please contact support or try resetting the character."), 'error')
        return redirect(url_for('main.index'))

    achieved_levels_list = sorted(list(set(cl.level_number for cl in character_levels)))
    current_actual_level = achieved_levels_list[-1] if achieved_levels_list else 1
    viewed_level_number = current_actual_level 
    current_character_level_data = next((cl for cl in character_levels if cl.level_number == viewed_level_number), None)
    
    if not current_character_level_data:
        flash(_("Could not load level-specific data for your character's current level. Please contact support."), 'error')
        return redirect(url_for('main.index'))

    log_entries = json.loads(character.adventure_log or '[]') if isinstance(character.adventure_log, str) else []
    if not isinstance(log_entries, list): log_entries = []

    if not log_entries:
        # ... (initial DM message logic - condensed) ...
        pass


    proficiency_bonus = (viewed_level_number - 1) // 4 + 2

    character_owned_weapons_list = []
    equipped_weapons_details = []

    for assoc in character.weapon_associations:
        weapon_obj = assoc.weapon
        weapon_detail = {
            'association_id': f"{assoc.character_id}-{assoc.weapon_id}",
            'weapon_id': weapon_obj.id,
            'character_id': assoc.character_id,
            'name': weapon_obj.name,
            'damage_dice': weapon_obj.damage_dice,
            'damage_type': weapon_obj.damage_type,
            'properties': json.loads(weapon_obj.properties) if weapon_obj.properties else [],
            'range': weapon_obj.range,
            'normal_range': weapon_obj.normal_range,
            'long_range': weapon_obj.long_range,
            'throw_range_normal': weapon_obj.throw_range_normal,
            'throw_range_long': weapon_obj.throw_range_long,
            'category': weapon_obj.category,
            'is_martial': weapon_obj.is_martial,
            'quantity': assoc.quantity,
            'is_equipped_main_hand': assoc.is_equipped_main_hand,
            'is_equipped_off_hand': assoc.is_equipped_off_hand
        }
        character_owned_weapons_list.append(weapon_detail)
        if assoc.is_equipped_main_hand or assoc.is_equipped_off_hand:
            equipped_weapons_details.append(weapon_detail)

    proficiencies_data = json.loads(current_character_level_data.proficiencies or '{}') if isinstance(current_character_level_data.proficiencies, str) else {}
    if not isinstance(proficiencies_data, dict): proficiencies_data = {}
    
    # ... (rest of data preparation for template - condensed) ...
    # Example: proficient_skills = proficiencies_data.get('skills', [])

    return render_template('adventure.html', 
                           character=character,
                           current_character_level_data=current_character_level_data,
                           log_entries=log_entries,
                           proficiency_bonus=proficiency_bonus,
                           equipped_weapons=equipped_weapons_details,
                           character_owned_weapons_list=character_owned_weapons_list,
                           # Other necessary variables for the template...
                           all_skills_list=ALL_SKILLS_LIST, ability_names_full=ABILITY_NAMES_FULL,
                           proficient_skills=proficiencies_data.get('skills', []),
                           proficient_saving_throws=proficiencies_data.get('saving_throws', []),
                           proficient_tools=proficiencies_data.get('tools', []),
                           proficient_languages=proficiencies_data.get('languages', []),
                           proficient_armor=proficiencies_data.get('armor', []),
                           proficient_weapons=proficiencies_data.get('weapons', []),
                           character_items=character.items, character_coinage=character.coinage,
                           spells_by_level={}, spell_slots_data={}, # Placeholders
                           saving_throws_data=[], skills_data=[], abilities_data=[], # Placeholders
                           character_spellcasting_ability=character.char_class.spellcasting_ability if character.char_class else None,
                           current_actual_level=current_actual_level,
                           dm_allowed_level=character.dm_allowed_level,
                           achieved_levels_list=achieved_levels_list
                           )

@bp.route('/roll_dice_from_sheet', methods=['POST'])
@login_required
def roll_dice_from_sheet(): # Condensed
    # ... unchanged ...
    return jsonify({})


@bp.route('/get_all_weapons_for_inventory_modal', methods=['GET'])
@login_required
def get_all_weapons_for_inventory_modal():
    all_weapons = Weapon.query.order_by(Weapon.category, Weapon.name).all()
    weapons_data = [{
        "id": weapon.id, "name": weapon.name, "category": weapon.category,
        "damage_dice": weapon.damage_dice, "damage_type": weapon.damage_type,
        "properties": json.loads(weapon.properties) if weapon.properties else []
    } for weapon in all_weapons]
    return jsonify(weapons_data)

@bp.route('/character/<int:character_id>/inventory/add_weapon', methods=['POST'])
@login_required
def add_weapon_to_inventory_route(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id: return jsonify(status="error", message="Unauthorized"), 403
    data = request.json
    if not data: return jsonify(status="error", message="No data provided."), 400

    weapon_id = data.get('weapon_id')
    try: quantity_to_add = int(data.get('quantity', 1))
    except ValueError: return jsonify(status="error", message="Invalid quantity format."), 400

    if not weapon_id or quantity_to_add <= 0: return jsonify(status="error", message="Weapon ID and positive quantity are required."), 400

    weapon_master_record = Weapon.query.get(weapon_id)
    if not weapon_master_record: return jsonify(status="error", message="Weapon not found."), 404

    assoc = CharacterWeaponAssociation.query.filter_by(character_id=character_id, weapon_id=weapon_id).first()
    message = ""
    status_code = 200

    if assoc:
        assoc.quantity += quantity_to_add
        message = f"{quantity_to_add} {assoc.weapon.name}(s) added. You now have {assoc.quantity}."
    else:
        assoc = CharacterWeaponAssociation(
            character_id=character_id,
            weapon_id=weapon_id,
            quantity=quantity_to_add
        )
        db.session.add(assoc)
        message = f"{weapon_master_record.name} (x{quantity_to_add}) added to inventory."
        status_code = 201

    try:
        db.session.commit()
        item_for_response = {
            'weapon_id': assoc.weapon_id,
            'character_id': assoc.character_id,
            'name': assoc.weapon.name,
            'category': assoc.weapon.category,
            'damage_dice': assoc.weapon.damage_dice,
            'damage_type': assoc.weapon.damage_type,
            'properties': json.loads(assoc.weapon.properties) if assoc.weapon.properties else [],
            'quantity': assoc.quantity,
            'is_equipped_main_hand': assoc.is_equipped_main_hand,
            'is_equipped_off_hand': assoc.is_equipped_off_hand,
            'association_id': f"{assoc.character_id}-{assoc.weapon_id}"
        }
        return jsonify(status="success", message=message, weapon=item_for_response), status_code
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error adding weapon: {e}")
        return jsonify(status="error", message="Internal error saving weapon."), 500

@bp.route('/character/<int:character_id>/inventory/remove_weapon/<int:weapon_id_from_url>', methods=['POST'])
@login_required
def remove_weapon_from_inventory_route(character_id, weapon_id_from_url):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id: return jsonify(status="error", message="Unauthorized"), 403

    assoc_to_remove = CharacterWeaponAssociation.query.filter_by(
        character_id=character_id,
        weapon_id=weapon_id_from_url
    ).first()

    if not assoc_to_remove:
        return jsonify(status="error", message="Weapon inventory entry not found."), 404

    weapon_name = assoc_to_remove.weapon.name
    db.session.delete(assoc_to_remove)

    try:
        db.session.commit()
        return jsonify(status="success", message=f"'{weapon_name}' removed from inventory."), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error removing weapon: {e}")
        return jsonify(status="error", message="Internal error removing weapon."), 500

@bp.route('/character/<int:character_id>/inventory/equip_weapon', methods=['POST'])
@login_required
def equip_weapon_route(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id: return jsonify(status="error", message="Unauthorized"), 403
    data = request.json
    if not data: return jsonify(status="error", message="No data provided."), 400

    weapon_id_to_equip = data.get('weapon_id')
    equip_slot = data.get('equip_slot')

    if not weapon_id_to_equip or equip_slot not in ["main_hand", "off_hand"]:
        return jsonify(status="error", message="Valid weapon_id and equip_slot are required."), 400

    assoc_to_equip = CharacterWeaponAssociation.query.filter_by(
        character_id=character_id,
        weapon_id=weapon_id_to_equip
    ).first()

    if not assoc_to_equip: return jsonify(status="error", message="Weapon not found in inventory."), 404

    weapon_details = assoc_to_equip.weapon
    weapon_properties = json.loads(weapon_details.properties) if weapon_details.properties else []
    is_two_handed = any(prop.get("index") == "two-handed" for prop in weapon_properties)

    for assoc in character.weapon_associations:
        assoc.is_equipped_main_hand = False
        assoc.is_equipped_off_hand = False

    if equip_slot == "main_hand":
        assoc_to_equip.is_equipped_main_hand = True
        if is_two_handed: assoc_to_equip.is_equipped_off_hand = True
    elif equip_slot == "off_hand":
        if is_two_handed:
            return jsonify(status="error", message="Cannot equip a two-handed weapon primarily in off-hand."), 400
        assoc_to_equip.is_equipped_off_hand = True

    try:
        db.session.commit()
        equipped_weapons_after_change = []
        for assoc in character.weapon_associations.filter(db.or_(CharacterWeaponAssociation.is_equipped_main_hand == True, CharacterWeaponAssociation.is_equipped_off_hand == True)).all():
            weapon_obj = assoc.weapon
            equipped_weapons_after_change.append({
                'weapon_id': weapon_obj.id, 'name': weapon_obj.name,
                'is_equipped_main_hand': assoc.is_equipped_main_hand,
                'is_equipped_off_hand': assoc.is_equipped_off_hand,
                'damage_dice': weapon_obj.damage_dice, 'damage_type': weapon_obj.damage_type,
                'properties': json.loads(weapon_obj.properties) if weapon_obj.properties else []
            })
        return jsonify(status="success", message=f"{weapon_details.name} equipped.", equipped_weapons=equipped_weapons_after_change), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error equipping weapon: {e}")
        return jsonify(status="error", message="Internal error equipping weapon."), 500

@bp.route('/character/<int:character_id>/inventory/unequip_weapon', methods=['POST'])
@login_required
def unequip_weapon_route(character_id):
    character = Character.query.get_or_404(character_id)
    if character.user_id != current_user.id: return jsonify(status="error", message="Unauthorized"), 403
    data = request.json;
    if not data: return jsonify(status="error", message="No data provided."), 400

    weapon_id_to_unequip = data.get('weapon_id')

    if not weapon_id_to_unequip: return jsonify(status="error", message="Weapon ID required."), 400

    assoc_to_unequip = CharacterWeaponAssociation.query.filter_by(
        character_id=character_id,
        weapon_id=weapon_id_to_unequip
    ).first()

    if not assoc_to_unequip: return jsonify(status="error", message="Weapon not found in inventory."), 404

    weapon_name = assoc_to_unequip.weapon.name
    assoc_to_unequip.is_equipped_main_hand = False
    assoc_to_unequip.is_equipped_off_hand = False

    try:
        db.session.commit()
        equipped_weapons_after_change = []
        for assoc in character.weapon_associations.filter(db.or_(CharacterWeaponAssociation.is_equipped_main_hand == True, CharacterWeaponAssociation.is_equipped_off_hand == True)).all():
            weapon_obj = assoc.weapon
            equipped_weapons_after_change.append({
                'weapon_id': weapon_obj.id, 'name': weapon_obj.name,
                'is_equipped_main_hand': assoc.is_equipped_main_hand,
                'is_equipped_off_hand': assoc.is_equipped_off_hand,
                'damage_dice': weapon_obj.damage_dice, 'damage_type': weapon_obj.damage_type,
                'properties': json.loads(weapon_obj.properties) if weapon_obj.properties else []
            })
        return jsonify(status="success", message=f"{weapon_name} unequipped.", equipped_weapons=equipped_weapons_after_change), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error unequipping weapon: {e}")
        return jsonify(status="error", message="Internal error unequipping weapon."), 500

@bp.route('/send_chat_message/<int:character_id>', methods=['POST'])
@login_required
def send_chat_message(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/inventory/add_item', methods=['POST'])
@login_required
def add_item_to_inventory(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/inventory/remove_item/<int:item_id>', methods=['POST'])
@login_required
def remove_item_from_inventory(character_id, item_id): # Condensed
    # ... unchanged ...
    return redirect(url_for('main.adventure', character_id=character_id))

@bp.route('/character/<int:character_id>/inventory/update_coinage', methods=['POST'])
@login_required
def update_coinage_for_character(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/inventory/edit_item/<int:item_id>', methods=['POST'])
@login_required
def edit_item_in_inventory(character_id, item_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/spellslot/use/<int:spell_level>', methods=['POST'])
@login_required
def use_spell_slot(character_id, spell_level): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/spellslot/regain/<int:spell_level>/<int:count>', methods=['POST'])
@login_required
def regain_spell_slot(character_id, spell_level, count): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/rest/short', methods=['POST'])
@login_required
def short_rest(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/rest/long', methods=['POST'])
@login_required
def long_rest(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/get_level_data/<int:level_number>', methods=['GET'])
@login_required
def get_character_level_data(character_id, level_number): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/level_up/start', methods=['GET'])
@login_required
def level_up_start(character_id): # Condensed
    # ... unchanged ...
    return redirect(url_for('main.level_up_hp', character_id=character_id)) # Example

@bp.route('/character/<int:character_id>/level_up/hp', methods=['GET', 'POST'])
@login_required
def level_up_hp(character_id): # Condensed
    # ... unchanged ...
    if request.method == 'POST': return redirect(url_for('main.level_up_features_asi', character_id=character_id)) # Example
    return render_template('level_up/level_up_hp.html') # Example

@bp.route('/character/<int:character_id>/level_up/features_asi', methods=['GET', 'POST'])
@login_required
def level_up_features_asi(character_id): # Condensed
    # ... unchanged ...
    if request.method == 'POST': return redirect(url_for('main.level_up_spells', character_id=character_id)) # Example
    return render_template('level_up/level_up_features_asi.html') # Example

@bp.route('/character/<int:character_id>/level_up/spells', methods=['GET', 'POST'])
@login_required
def level_up_spells(character_id): # Condensed
    # ... unchanged ...
    if request.method == 'POST': return redirect(url_for('main.level_up_review', character_id=character_id)) # Example
    return render_template('level_up/level_up_spells.html') # Example

@bp.route('/character/<int:character_id>/level_up/review', methods=['GET'])
@login_required
def level_up_review(character_id): # Condensed
    # ... unchanged ...
    return render_template('level_up/level_up_review.html') # Example

@bp.route('/character/<int:character_id>/level_up/apply', methods=['POST']) 
@login_required
def level_up_apply(character_id): # Condensed
    # ... unchanged ...
    return redirect(url_for('main.adventure', character_id=character_id)) # Example

@bp.route('/character/<int:character_id>/update_hp', methods=['POST'])
@login_required
def update_hp(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})

@bp.route('/character/<int:character_id>/update_notes', methods=['POST'])
@login_required
def update_notes(character_id): # Condensed
    # ... unchanged ...
    return jsonify({})
