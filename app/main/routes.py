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
from app.models import User, Character, Setting, Item, Coinage, CharacterLevel
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

@bp.route('/create_character', methods=['GET']) # New main entry point
@login_required
def create_character():
    # Redirect to the new character creation wizard
    session.pop('new_character_data', None) # Clear any old session data before starting fresh
    session.modified = True
    return redirect(url_for('main.creation_wizard'))

# CHARACTER CREATION WIZARD ROUTES START
# ##############################################################################

@bp.route('/creation_wizard', methods=['GET', 'POST'])
@login_required
def creation_wizard():
    if request.method == 'GET':
        # Initialize or retrieve character creation data from the session
        if 'new_character_data' not in session:
            session['new_character_data'] = {}
            session.modified = True
            current_app.logger.info("Initialized new_character_data in session for wizard.")
        else:
            current_app.logger.info(f"Found existing new_character_data in session: {session['new_character_data']}")

        # This data is primarily for the overall page structure if needed,
        # individual steps will fetch their specific data via AJAX to step_data route.
        wizard_shell_data = {
            'current_wizard_data': session.get('new_character_data', {})
            # We could pass initial data for step 1 here if desired,
            # but current design is for JS to fetch it.
        }
        return render_template('character_creation_wizard.html', wizard_shell_data=wizard_shell_data)

    if request.method == 'POST':
        # This POST is intended for the final submission from the wizard's "Finish" button
        char_data = session.get('new_character_data', {})
        current_app.logger.info(f"Finalizing character with data: {char_data}")

        # --- Begin Character Finalization (adapted from old creation_review POST) ---
        character_name = char_data.get('character_name', 'Unnamed Hero')
        alignment = char_data.get('alignment', 'True Neutral')
        char_description = char_data.get('character_description', '')

        # Essential data checks
        # Removed 'race_id', 'class_id' from required_fields
        required_fields = ['ability_scores', 'background_name', 'max_hp', 'armor_class_base', 'speed']
        missing_fields = [field for field in required_fields if field not in char_data]
        if missing_fields:
            flash(f'Critical data missing: {", ".join(missing_fields)}. Cannot finalize character.', 'error')
            current_app.logger.error(f"Character finalization failed. Missing fields: {missing_fields}. Data: {char_data}")
            # Client-side should prevent this. Respond with error for AJAX or redirect if it's a direct form post.
            return jsonify(status="error", message=f"Missing data: {', '.join(missing_fields)}"), 400

        # race = Race.query.get(char_data.get('race_id')) # Removed
        # char_class_obj = Class.query.get(char_data.get('class_id')) # Removed

        # if not race or not char_class_obj: # Adjusted: This check might be removed or always pass
        #     flash('Race or Class data invalid. Cannot finalize character.', 'error')
        #     current_app.logger.error(f"Race or Class object not found. Race ID: {char_data.get('race_id')}, Class ID: {char_data.get('class_id')}")
        #     return jsonify(status="error", message="Invalid Race or Class ID"), 400

        # Aggregate proficiencies
        all_skill_proficiencies = set()

        # Race skills
        race_skills = char_data.get('race_skill_proficiencies_from_traits', [])
        if isinstance(race_skills, list):
            for skill in race_skills:
                if isinstance(skill, str) and skill.strip():
                    all_skill_proficiencies.add(skill.strip().title())

        # Chosen Class skills
        chosen_class_skills_list = char_data.get('chosen_class_skills', [])
        if isinstance(chosen_class_skills_list, list):
            for skill in chosen_class_skills_list:
                if isinstance(skill, str) and skill.strip():
                    all_skill_proficiencies.add(skill.strip().title())

        # Background skills:
        # Fixed background skills (extracted from the original background_skill_proficiencies list)
        # raw_bg_skills = char_data.get('background_skill_proficiencies', [])
        # if isinstance(raw_bg_skills, list):
        #     for item in raw_bg_skills:
        #         if isinstance(item, str) and not item.lower().startswith('choose ') and not ' or ' in item.lower():
        #             # This is a simple check; assumes fixed skills don't use "choose" or "or"
        #             # Multiple fixed skills in one string e.g. "Skill1, Skill2"
        #             fixed_in_item = [s.strip().title() for s in item.split(',') if s.strip()]
        #             for s_fixed in fixed_in_item:
        #                 all_skill_proficiencies.add(s_fixed)

        # Chosen background skills (from dropdowns/radio selections in Step 5)
        # chosen_bg_skills_list = char_data.get('chosen_background_skills', [])
        # if isinstance(chosen_bg_skills_list, list):
        #     for skill in chosen_bg_skills_list:
        #         if isinstance(skill, str) and skill.strip():
        #             all_skill_proficiencies.add(skill.strip().title())

        current_app.logger.info(f"Final aggregated skills before saving: {all_skill_proficiencies}")

        all_tool_proficiencies = set(char_data.get('background_tool_proficiencies', [])) # From BG definition
        all_tool_proficiencies.update(char_data.get('tool_proficiencies_class_fixed', [])) # From class definition
        all_tool_proficiencies.update(char_data.get('chosen_tool_proficiencies_from_bg', [])) # Chosen for BG
        all_tool_proficiencies.update(char_data.get('race_tool_proficiencies_from_traits', [])) # Added race tool profs from traits

        all_language_proficiencies = set(char_data.get('languages_from_race', [])) # From Race
        all_language_proficiencies.update(char_data.get('background_languages_fixed', [])) # Fixed from BG
        all_language_proficiencies.update(char_data.get('chosen_languages_from_bg', [])) # Chosen for BG


        new_char = Character(
            name=character_name,
            description=char_description,
            user_id=current_user.id,
            # race_id=race.id, # Removed
            # class_id=char_class_obj.id, # Removed
            alignment=alignment,
            background_name=char_data.get('background_name'),
            background_proficiencies=json.dumps({ # Store only the profs granted directly by background definition
                "skills": char_data.get('background_skill_proficiencies', []),
                "tools": char_data.get('background_tool_proficiencies', []),
                "languages": char_data.get('background_languages_fixed', [])
            }),
            adventure_log=json.dumps([]),
            dm_allowed_level=1,
            current_xp=0,
            current_hit_dice=1, # Level 1 characters have 1 hit die (equal to their level)
            player_notes=char_data.get('player_notes', "") # Added from wizard data
        )
        db.session.add(new_char)
        db.session.flush() # Flush to get new_char.id for CharacterLevel and Items/Coinage

        class_armor_prof = set(char_data.get('armor_proficiencies', [])) # Assuming this key holds class armor profs
        race_armor_prof = set(char_data.get('race_armor_proficiencies_from_traits', []))
        all_armor_proficiencies = sorted(list(class_armor_prof.union(race_armor_prof)))

        class_weapon_prof = set(char_data.get('weapon_proficiencies', [])) # Assuming this key holds class weapon profs
        race_weapon_prof = set(char_data.get('race_weapon_proficiencies_from_traits', []))
        all_weapon_proficiencies = sorted(list(class_weapon_prof.union(race_weapon_prof)))

        level_1_proficiencies_snapshot = {
            'skills': sorted(list(all_skill_proficiencies)),
            'tools': sorted(list(all_tool_proficiencies)),
            'languages': sorted(list(all_language_proficiencies)),
            'armor': all_armor_proficiencies,
            'weapons': all_weapon_proficiencies,
            'saving_throws': sorted(list(char_data.get('saving_throw_proficiencies', [])))
        }

        spell_slots_L1 = {} # Default to empty dict as char_class_obj is removed
        # if char_class_obj.spell_slots_by_level: # Removed
        #     try:
        #         all_class_level_slots = json.loads(char_class_obj.spell_slots_by_level)
        #         slots_for_char_level_1_list = all_class_level_slots.get("1")
        #         if slots_for_char_level_1_list:
        #             for spell_lvl_idx, num_slots in enumerate(slots_for_char_level_1_list):
        #                 if num_slots > 0:
        #                     spell_slots_L1[str(spell_lvl_idx + 1)] = num_slots
        #     except json.JSONDecodeError:
        #         current_app.logger.error(f"Failed to parse spell_slots_by_level for class {char_class_obj.name}")

        ability_scores_final = char_data.get('ability_scores', {})
        new_char_level_1 = CharacterLevel(
            character_id=new_char.id,
            level_number=1,
            xp_at_level_up=0,
            strength=ability_scores_final.get('STR', 10),
            dexterity=ability_scores_final.get('DEX', 10),
            constitution=ability_scores_final.get('CON', 10),
            intelligence=ability_scores_final.get('INT', 10),
            wisdom=ability_scores_final.get('WIS', 10),
            charisma=ability_scores_final.get('CHA', 10),
            hp=char_data.get('max_hp', 1), # Ensure HP is at least 1
            max_hp=char_data.get('max_hp', 1),
            armor_class=char_data.get('armor_class_base'),
            hit_dice_rolled="Max HP at L1", # Or actual roll if that was an option
            proficiencies=json.dumps(level_1_proficiencies_snapshot),
            features_gained=json.dumps(
                char_data.get('class_features_list', ["Initial Class Features"]) + \
                char_data.get('race_trait_names', []) or \
                ["Basic racial and class features"] # Fallback if both class_features_list and race_trait_names are empty or missing
            ),
            spells_known_ids=json.dumps(char_data.get('chosen_cantrip_ids', []) + char_data.get('chosen_level_1_spell_ids', [])),
            spells_prepared_ids=json.dumps([]), # Initial state for prepared casters
            spell_slots_snapshot=json.dumps(spell_slots_L1),
            created_at=datetime.utcnow()
        )

        # HP and AC calculation using final ability scores
        con_score = ability_scores_final.get('CON', 10)
        con_mod = (con_score - 10) // 2
        hit_die_str = char_data.get('hit_die', 'd8') # From class selection step
        try:
            hit_die_val = int(hit_die_str[1:])
        except (ValueError, TypeError, IndexError):
            current_app.logger.error(f"Invalid hit_die format '{hit_die_str}' during final save. Defaulting to 8.")
            hit_die_val = 8

        max_hp_at_level_1 = hit_die_val + con_mod
        new_char_level_1.max_hp = max_hp_at_level_1 # Set calculated max_hp
        new_char_level_1.hp = max_hp_at_level_1 # Set current hp to max_hp for L1

        dex_score = ability_scores_final.get('DEX', 10)
        dex_mod = (dex_score - 10) // 2
        base_ac_calculated = 10 + dex_mod # This doesn't account for armor from equipment yet

        # Allow armor_class_base from session (e.g. if calculated in a later step with armor)
        # to override this basic calculation. If 'armor_class_base' is not in char_data, use the calculated one.
        new_char_level_1.armor_class = char_data.get('armor_class_base', base_ac_calculated)


        db.session.add(new_char_level_1)

        # Process Equipment and Coinage from 'final_equipment_objects'
        final_equipment_objects = char_data.get('final_equipment_objects', [])

        # Handle coinage (often part of background equipment string but should be separated if possible)
        # For simplicity, assuming 'final_equipment_objects' might contain coin-like entries or a dedicated 'coinage' field in char_data

        # Example: if char_data contains a specific 'coinage_gp' field:
        if 'coinage_gp' in char_data and char_data['coinage_gp'] > 0:
             db.session.add(Coinage(name="Gold Pieces", quantity=char_data['coinage_gp'], character_id=new_char.id))
        # Similar for SP, CP etc. Or parse from a general equipment string if necessary.

        # Simplified item processing:
        for item_obj in final_equipment_objects:
            if item_obj.get('name') and item_obj.get('quantity', 0) > 0:
                # Basic parsing for gold from item name string (if not handled separately)
                if "gp" in item_obj['name'].lower() or "gold piece" in item_obj['name'].lower():
                    # This is a basic example. A more robust parser for "15 gp" etc. would be needed.
                    # For now, let's assume specific coinage fields or that items are distinct from raw currency.
                    pass # Skip adding raw gold string as an "item" if handled by dedicated coinage fields
                else:
                    db.session.add(Item(
                        name=item_obj['name'].strip().title(),
                        quantity=item_obj['quantity'],
                        description=item_obj.get('description', "Starting equipment"),
                        character_id=new_char.id
                    ))

        db.session.commit()
        session.pop('new_character_data', None)
        session.modified = True
        flash('Character created successfully!', 'success')
        # Return JSON for AJAX, or redirect if it was a full form post
        return jsonify(status="success", message="Character created!", character_id=new_char.id, redirect_url=url_for('main.index'))

    # Fallthrough for GET if POST logic doesn't redirect earlier (should not happen for final POST)
    # Or if it's a GET request, this is already handled above.
    # This return is a safeguard.
    return redirect(url_for('main.creation_wizard'))

# sample_backgrounds_data is used by creation_wizard_step_data, so it's kept above the wizard routes.
sample_backgrounds_data = {
    "Acolyte": {"name": "Acolyte", "skill_proficiencies": ["Insight", "Religion"], "tool_proficiencies": [], "languages": ["Two of your choice"], "equipment": "A holy symbol (a gift to you when you entered the priesthood), a prayer book or prayer wheel, 5 sticks of incense, vestments, a set of common clothes, and a pouch containing 15 gp."},
    "Criminal": {"name": "Criminal (Spy)", "skill_proficiencies": ["Deception", "Stealth"], "tool_proficiencies": ["One type of gaming set", "Thieves' tools"], "languages": [], "equipment": "A crowbar, a set of dark common clothes including a hood, and a pouch containing 15 gp."},
    "Sage": {"name": "Sage", "skill_proficiencies": ["Arcana", "History"], "tool_proficiencies": [], "languages": ["Two of your choice"], "equipment": "A bottle of black ink, a quill, a small knife, a letter from a dead colleague posing a question you have not yet been able to answer, a set of common clothes, and a pouch containing 10 gp."},
    "Soldier": {"name": "Soldier", "skill_proficiencies": ["Athletics", "Intimidation"], "tool_proficiencies": ["One type of gaming set", "Vehicles (land)"], "languages": [], "equipment": "An insignia of rank, a trophy taken from a fallen enemy, a set of bone dice or deck of cards, a set of common clothes, and a pouch containing 10 gp."},
    "Entertainer": {"name": "Entertainer", "skill_proficiencies": ["Acrobatics", "Performance"], "tool_proficiencies": ["Disguise kit", "One type of musical instrument"], "languages": [], "equipment": "A musical instrument (one of your choice), the favor of an admirer (love letter, lock of hair, or trinket), a costume, and a pouch containing 15 gp."}
}

# parse_starting_equipment is used by creation_wizard_step_data, so it's kept.
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

def parse_one_background_skill_desc(desc_string, choice_group_id_prefix="bg_choice_"):
    """
    Parses a single skill proficiency description string from a background benefit.
    Returns a tuple: (list_of_fixed_skills, list_of_choice_groups)
    Each choice_group is a dict: {id, description, options, num_to_pick}
    """
    fixed_skills = set()
    choice_groups = []
    # ALL_SKILLS_LIST should be imported in the module this function resides in.
    all_skill_names = [skill_tuple[0] for skill_tuple in ALL_SKILLS_LIST]

    original_desc_for_choice_description = desc_string # Keep for choice group descriptions

    desc_string = desc_string.strip()

    # Normalize common phrasing variations for "N of your choice"
    # "Choose any two skills" -> "Two of your choice"
    # Important: Apply these normalizations carefully to avoid unintended changes to specific skill names or other patterns.
    temp_desc_string = re.sub(r"choose any (\w+) skills?", r"\1 of your choice", desc_string, flags=re.IGNORECASE)
    temp_desc_string = re.sub(r"proficiency in (\w+) skills? of your choice", r"\1 of your choice", temp_desc_string, flags=re.IGNORECASE)
    # Remove leading "Skill Proficiencies: " or "Skills: "
    temp_desc_string = re.sub(r"^(Skill Proficiencies|Skills):\s*", "", temp_desc_string, flags=re.IGNORECASE).strip()


    # 1. Handle "N of your choice" (covers "Two of your choice", "One skill of your choice")
    # Use temp_desc_string for this match
    general_choice_match = re.fullmatch(r"(one|two|three|four) of your choice", temp_desc_string, re.IGNORECASE)
    if general_choice_match:
        num_word = general_choice_match.group(1).lower()
        num_map = {"one": 1, "two": 2, "three": 3, "four": 4}
        num_to_pick = num_map.get(num_word, 1)

        choice_groups.append({
            "id": f"{choice_group_id_prefix}any_{num_to_pick}",
            "description": original_desc_for_choice_description, # Use original for UI clarity
            "options": all_skill_names,
            "num_to_pick": num_to_pick
        })
        return list(fixed_skills), choice_groups # This type of string usually stands alone

    # 2. Handle complex strings:
    # Back to using the original desc_string (or the prefix-stripped one if that's preferred) for more specific parsing.
    # Let's use the prefix-stripped one:
    desc_to_parse_clauses = temp_desc_string

    clauses = []
    # Split by ", and " first, then try " and " if the first yields only one part (or no split)
    # This handles cases like "A, B, and C" vs "A and B"
    # Regex split by ", and " or " and " (case insensitive for "and")
    # A simple approach: replace ", and " with a unique delimiter, then " and " with it, then split.
    delimiter = "&&&SPLIT&&&"
    temp_for_split = re.sub(r",\s+and\s+", delimiter, desc_to_parse_clauses, flags=re.IGNORECASE)
    temp_for_split = re.sub(r"\s+and\s+", delimiter, temp_for_split, flags=re.IGNORECASE) # For cases without comma before 'and'

    if delimiter in temp_for_split:
        clauses = [c.strip() for c in temp_for_split.split(delimiter)]
    else:
        clauses = [desc_to_parse_clauses.strip()] # Treat as a single clause if no "and"

    processed_clauses_for_fixed_skills = []
    next_choice_idx = 0 # To make choice group IDs unique within this desc_string parse

    for clause in clauses:
        clause = clause.strip().rstrip(',') # Clean each clause

        # Check for "either X or Y"
        either_or_match = re.fullmatch(r"either (.+) or (.+)", clause, re.IGNORECASE)
        if either_or_match:
            opt1 = either_or_match.group(1).strip().title()
            opt2 = either_or_match.group(2).strip().title()
            choice_groups.append({
                "id": f"{choice_group_id_prefix}eo_{next_choice_idx}",
                "description": f"Choose one: {opt1} or {opt2}", # Original clause might be better: clause
                "options": [opt1, opt2],
                "num_to_pick": 1
            })
            next_choice_idx += 1
            continue

        # Check for "X or Y" (without "either")
        simple_or_match = re.fullmatch(r"(.+) or (.+)", clause, re.IGNORECASE)
        if simple_or_match:
            opt1 = simple_or_match.group(1).strip().title()
            opt2 = simple_or_match.group(2).strip().title()
            choice_groups.append({
                "id": f"{choice_group_id_prefix}so_{next_choice_idx}",
                "description": f"Choose one: {opt1} or {opt2}", # Original clause might be better: clause
                "options": [opt1, opt2],
                "num_to_pick": 1
            })
            next_choice_idx += 1
            continue

        # Check for "Choose N from X, Y, Z" (specifically "Choose one from..." for now)
        choose_from_match = re.fullmatch(r"choose (one) from (.+)", clause, re.IGNORECASE)
        if choose_from_match:
            num_word = choose_from_match.group(1).lower() # Should be "one"
            options_str = choose_from_match.group(2)

            raw_options_list = options_str.split(',')
            cleaned_options = []
            for opt_part in raw_options_list:
                processed_opt_part = re.sub(r"^(and|or)\s+", "", opt_part.strip(), flags=re.IGNORECASE)
                if processed_opt_part:
                    cleaned_options.append(processed_opt_part.title())

            options = [opt for opt in cleaned_options if opt]
            num_to_pick = 1

            if options:
                choice_groups.append({
                    "id": f"{choice_group_id_prefix}cf_{next_choice_idx}",
                    "description": clause, # Use original clause for description
                    "options": options,
                    "num_to_pick": num_to_pick
                })
            next_choice_idx += 1
            continue

        # If none of the choice patterns matched this clause, it's treated as containing fixed skills
        processed_clauses_for_fixed_skills.append(clause)

    if processed_clauses_for_fixed_skills:
        full_fixed_skill_string = ", ".join(processed_clauses_for_fixed_skills)
        # Split by comma, but also handle cases where a fixed skill might be inadvertently split by previous "and" logic
        # The goal here is that `full_fixed_skill_string` contains only comma separated fixed skills.
        found_fixed = [skill.strip().title() for skill in full_fixed_skill_string.split(',') if skill.strip()]
        for fs in found_fixed:
            if fs and fs.lower() not in ["either", "choose one from"]: # Basic filter against keywords
                fixed_skills.add(fs)

    return list(fixed_skills), choice_groups

@bp.route('/creation_wizard/step_data/<step_name>', methods=['GET'])
@login_required
def creation_wizard_step_data(step_name):
    data = {}
    char_data_session = session.get('new_character_data', {})

    if step_name == 'race':
        # races = Race.query.all() # Removed
        data = {'races': []} # Changed
    elif step_name == 'class':
        # classes = Class.query.all() # Removed
        data = {'classes': []} # Changed
    elif step_name == 'stats':
        data = {'standard_array': [15, 14, 13, 12, 10, 8]}
        # race_id = char_data_session.get('race_id') # Removed
        # if race_id: # Removed
        #     race = Race.query.get(race_id) # Removed
        #     if race: # Removed
        #         # ability_score_increases should be JSON string like '{"STR": 1, "DEX": 2}' in model
        #         # to_dict() should handle json.loads for this field.
        #         data['racial_bonuses'] = race.to_dict().get('ability_score_increases', {}) # Removed
        #     else: data['racial_bonuses'] = {} # Removed
        # else: data['racial_bonuses'] = {} # Removed
        # data['racial_bonuses'] = {} # Changed: Set directly - This line is now part of the new structure below
        data = {
            'standard_array': [15, 14, 13, 12, 10, 8], # Standard array might be an alternative method in future
            'racial_bonuses': {}, # Client-side handles this primarily from effectiveRaceDetailsForSession
            'class_ability_suggestions': {} # Placeholder for future server-side class tips
        }
    elif step_name == 'background':
        data = {'backgrounds': sample_backgrounds_data} # Predefined dict
    elif step_name == 'skills':
        # Default structure
        data = {
            'racial_skills': [],
            'class_fixed_skills': [], # Fixed skills directly from class definition (rare for 5e)
            'class_skill_options': [],
            'num_class_skills_to_choose': 0,
            'background_fixed_skills': [],
            'background_skill_choices': [] # List of choice groups {id, description, options, num_to_pick}
        }

        # 1. Racial Skills (these are typically fixed)
        #    session['new_character_data']['race_skill_proficiencies_from_traits'] is expected to be a list of skill names.
        racial_skills_from_session = char_data_session.get('race_skill_proficiencies_from_traits', [])
        if isinstance(racial_skills_from_session, list):
            data['racial_skills'] = [str(skill).strip().title() for skill in racial_skills_from_session if str(skill).strip()]
        else:
            current_app.logger.warning(f"race_skill_proficiencies_from_traits was not a list: {racial_skills_from_session}")


        # 2. Class Skills
        #    session['new_character_data']['skill_proficiencies_options_raw'] (e.g., "Choose two from A, B, C")
        #    session['new_character_data']['skill_proficiencies_option_count'] (e.g., 2)
        class_options_raw = char_data_session.get('skill_proficiencies_options_raw')
        class_num_to_choose = char_data_session.get('skill_proficiencies_option_count', 0)

        if isinstance(class_num_to_choose, str): # Ensure it's an int
            try:
                class_num_to_choose = int(class_num_to_choose)
            except ValueError:
                current_app.logger.warning(f"Could not convert class_num_to_choose '{class_num_to_choose}' to int. Defaulting to 0.")
                class_num_to_choose = 0

        data['num_class_skills_to_choose'] = class_num_to_choose

        if class_options_raw and isinstance(class_options_raw, str) and class_num_to_choose > 0:
            options_text_segment = class_options_raw

            # Remove "Choose X from " prefix if it exists
            # Using a more general regex to catch variations like "Choose any two from" etc.
            prefix_match = re.match(r"choose (any )?\w+ from\s+", options_text_segment, re.IGNORECASE)
            if prefix_match:
                options_text_segment = options_text_segment[len(prefix_match.group(0)):].strip()

            # Split by comma, then further process each part to remove "and " and handle potential empty strings
            raw_options = options_text_segment.split(',')
            cleaned_skill_options = []
            for opt in raw_options:
                # Remove "and " prefix from individual options if present (e.g., ", and Survival")
                processed_opt = re.sub(r"^and\s+", "", opt.strip(), flags=re.IGNORECASE)
                if processed_opt: # Ensure option is not empty after stripping
                    cleaned_skill_options.append(processed_opt.title())

            data['class_skill_options'] = [s for s in cleaned_skill_options if s] # Ensure no empty strings in the final list

        elif isinstance(class_options_raw, list) and class_num_to_choose > 0: # If already a list (less likely from API but good fallback)
             data['class_skill_options'] = [str(opt).strip().title() for opt in class_options_raw if str(opt).strip()]

        # Ensure that if num_class_skills_to_choose is 0, class_skill_options is also empty
        if data['num_class_skills_to_choose'] == 0:
            data['class_skill_options'] = []

        # 3. Background Skills - REMOVED
        # No longer processing background skills for selection in the wizard.
        data['background_fixed_skills'] = []
        data['background_skill_choices'] = []

        # Log the data being sent for the skills step
        current_app.logger.info(f"Data prepared for skills step (5): {data}")
    elif step_name == 'hp':
        # race_id = char_data_session.get('race_id') # Removed
        # class_id = char_data_session.get('class_id') # Removed
        # ability_scores = char_data_session.get('ability_scores') # Removed
        # if race_id and class_id and ability_scores: # Removed
        #     race = Race.query.get(race_id) # Removed
        #     s_class = Class.query.get(class_id) # Removed
        #     if race and s_class: # Removed
        #         con_score = ability_scores.get('CON', 10) # Removed
        #         con_mod = (con_score - 10) // 2 # Removed
        #         try: # Removed
        #             hit_die_val = int(s_class.hit_die[1:]) # Assumes "dX" format # Removed
        #         except: hit_die_val = 8 # Default # Removed
        #         max_hp = hit_die_val + con_mod # Removed

        #         dex_score = ability_scores.get('DEX', 10) # Removed
        #         dex_mod = (dex_score - 10) // 2 # Removed
        #         ac_base = 10 + dex_mod # Removed
        #         data = {'max_hp': max_hp, 'ac_base': ac_base, 'speed': race.speed} # Removed
        #     else: data = {'error': 'Race or Class not found for HP calc'} # Removed
        # else: data = {'error': 'Missing data for HP calc (race, class, or scores)'} # Removed
        data = {'max_hp': 10, 'ac_base': 10, 'speed': 30} # Changed
    elif step_name == 'equipment':
        # class_id = char_data_session.get('class_id') # Removed
        background_name = char_data_session.get('background_name') # Kept background_name for now
        # if class_id and background_name: # Removed
        #     selected_class = Class.query.get(class_id) # Removed
        #     background_details = sample_backgrounds_data.get(background_name) # Kept
        #     if selected_class and background_details: # Removed selected_class
        #         fixed_items, choice_groups = parse_starting_equipment(selected_class.starting_equipment or '[]') # Removed
        #         data = { # Removed
        #             'fixed_items': fixed_items, # Removed
        #             'choice_groups': choice_groups, # Removed
        #             'background_equipment_string': background_details.get('equipment', '') # Kept
        #         } # Removed
        #     else: data = {'error': 'Class or Background details not found for equipment'} # Removed
        # else: data = {'error': 'Class ID or Background name not in session for equipment'} # Removed
        # Simplified data for equipment, assuming background_details might still be used if available
        background_details = sample_backgrounds_data.get(background_name) if background_name else {}
        data = {'fixed_items': [], 'choice_groups': [], 'background_equipment_string': background_details.get('equipment', '')} # Changed
    elif step_name == 'spells':
        # class_id = char_data_session.get('class_id') # Removed
        # if class_id: # Removed
        #     s_class = Class.query.get(class_id) # Removed
        #     if s_class and s_class.spellcasting_ability: # Removed
        #         s_class_dict = s_class.to_dict() # Removed
        #         # Determine number of cantrips/spells to pick at L1
        #         # This logic is simplified; actual numbers depend on class rules (Wizard, Sorc, etc.)
        #         # For L1, cantrips_known_by_level/spells_known_by_level map for key "1"
        #         cantrips_known_map = s_class_dict.get('cantrips_known_by_level', {}) # Removed
        #         spells_known_map = s_class_dict.get('spells_known_by_level', {}) # Removed

        #         num_cantrips = int(cantrips_known_map.get("1", 0)) # Removed
        #         num_level_1_spells = int(spells_known_map.get("1", 0)) # Removed

        #         # Special case for Wizard L1 spells
        #         if s_class.name == "Wizard": num_level_1_spells = 6 # Removed

        #         search_pattern = f'%"{s_class.name}"%' # For Spell.classes_that_can_use # Removed
        #         cantrips = Spell.query.filter(Spell.level == 0, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all() # Removed
        #         level_1_spells = Spell.query.filter(Spell.level == 1, Spell.classes_that_can_use.like(search_pattern)).order_by(Spell.name).all() # Removed
        #         data = { # Removed
        #             'num_cantrips_to_select': num_cantrips, # Removed
        #             'num_level_1_spells_to_select': num_level_1_spells, # Removed
        #             'available_cantrips': [{'id': sp.id, 'name': sp.name, 'description': sp.description} for sp in cantrips], # Removed
        #             'available_level_1_spells': [{'id': sp.id, 'name': sp.name, 'description': sp.description} for sp in level_1_spells], # Removed
        #             'can_prepare_spells': s_class_dict.get('can_prepare_spells', False) # Removed
        #         } # Removed
        #     else: data = {'no_spells_or_class_issue': True} # No spellcasting ability or class not found # Removed
        # else: data = {'error': 'Class ID not in session for spells'} # Removed
        data = {'num_cantrips_to_select': 0, 'num_level_1_spells_to_select': 0, 'available_cantrips': [], 'available_level_1_spells': [], 'can_prepare_spells': False} # Changed
    elif step_name == 'review':
        # Review step primarily uses data already in session. This can confirm/load full objects.
        data = {'current_character_summary': char_data_session} # Send all accumulated data
        # if char_data_session.get('race_id'): # Removed
        #     race = Race.query.get(char_data_session.get('race_id')) # Removed
        #     if race: data['race_details'] = race.to_dict() # Removed
        # if char_data_session.get('class_id'): # Removed
        #     s_class = Class.query.get(char_data_session.get('class_id')) # Removed
        #     if s_class: data['class_details'] = s_class.to_dict() # Removed
        # Add more details as needed for review page, e.g., spell names
    else:
        return jsonify(error="Invalid step name"), 404
    return jsonify(data)

@bp.route('/creation_wizard/update_session', methods=['POST'])
@login_required
def creation_wizard_update_session():
    if 'new_character_data' not in session: # Should be initialized by GET /creation_wizard
        session['new_character_data'] = {}
        session.modified = True

    update_data = request.get_json()
    if not update_data:
        return jsonify(status="error", message="No data provided"), 400

    # `step_key` could be 'race', 'class', 'ability_scores', etc.
    # `step_payload` is the data for that step, e.g. {'race_id': 5}
    step_key = update_data.get('step_key')
    step_payload = update_data.get('payload', {})

    if not step_key:
         return jsonify(status="error", message="Step key identifier missing"), 400

    # Merge new payload into the session data for the character
    # Example: if session['new_character_data'] = {'race_id': 1}, and payload is {'class_id': 2}
    # it becomes {'race_id': 1, 'class_id': 2}
    # session['new_character_data'].update(step_payload) # This will be handled more selectively

    # Perform server-side logic based on the step and payload
    if step_key == 'race': # Broader check, specific slug/details check inside
        # payload_data = step_payload # The payload from JS is step_payload.payload # Corrected: step_payload *is* the payload

        race_slug_to_lookup = step_payload.get('race_slug')
        effective_details = step_payload.get('effective_race_details')

        if not race_slug_to_lookup:
            current_app.logger.warning("race_slug missing from payload for 'race' step.")
            return jsonify(status="error", message="Race slug is missing."), 400

        # Always look up the race by slug to get its database ID and for fallback
        # This assumes slugs in DB match names after hyphen-to-space and title case,
        # which is how they were populated by populate_races.py from Open5e slugs.
        # race_name_candidate = race_slug_to_lookup.replace('-', ' ').title() # Removed
        # race = Race.query.filter_by(name=race_name_candidate).first() # Removed

        # if not race: # This means the slug sent from frontend didn't match any race name # Removed
        #     current_app.logger.warning(f"Race not found for name candidate: '{race_name_candidate}' (from slug: '{race_slug_to_lookup}')") # Removed
        #     return jsonify(status="error", message=f"Invalid Race Slug: {race_slug_to_lookup}"), 400 # Removed

        # Store the fundamental race_id and the original slug from the selected race/subrace
        # session['new_character_data']['race_id'] = race.id # Removed
        session['new_character_data']['selected_race_slug'] = race_slug_to_lookup # Kept slug for now, though race_id is gone

        if effective_details:
            current_app.logger.info(f"Using effective_race_details for race: {effective_details.get('name')}")
            session['new_character_data']['race_name'] = effective_details.get('name')
            session['new_character_data']['speed'] = effective_details.get('speed')
            session['new_character_data']['languages_from_race'] = effective_details.get('languages', [])
            session['new_character_data']['ability_score_increases_details'] = effective_details.get('asi') # This is just data now

            # Updated to use new keys from effective_details for traits and proficiencies
            session['new_character_data']['race_trait_names'] = effective_details.get('trait_names', [])
            session['new_character_data']['race_skill_proficiencies_from_traits'] = effective_details.get('skill_proficiencies_from_traits', [])
            session['new_character_data']['race_tool_proficiencies_from_traits'] = effective_details.get('tool_proficiencies_from_traits', [])
            session['new_character_data']['race_weapon_proficiencies_from_traits'] = effective_details.get('weapon_proficiencies_from_traits', [])
            session['new_character_data']['race_armor_proficiencies_from_traits'] = effective_details.get('armor_proficiencies_from_traits', [])

            session['new_character_data']['is_subrace'] = effective_details.get('is_subrace', False)
            if effective_details.get('is_subrace'):
                session['new_character_data']['parent_race_slug'] = effective_details.get('parent_slug')

            # The old 'race_skill_proficiencies' placeholder is removed as new specific keys are used.
            # session['new_character_data']['race_skill_proficiencies'] = [] # This line is now removed.

            # Ensure 'race_document__slug' is still handled (though its origin might change if not from a direct race model object)
            # For now, assuming it might not be in effective_details, so keep default.
            session['new_character_data'].setdefault('race_document__slug', None)


        else:
            # Fallback to old logic if effective_race_details is not provided
            # current_app.logger.info(f"Using race.to_dict() for race: {race.name} as no effective_details provided.") # Removed
            # race_dict = race.to_dict() # Removed
            session['new_character_data']['race_name'] = "Default Race" # Default
            session['new_character_data']['speed'] = 30 # Default
            session['new_character_data']['languages_from_race'] = [] # Default
            session['new_character_data']['race_skill_proficiencies'] = [] # Default
            session['new_character_data']['ability_score_increases_details'] = {} # Default
            session['new_character_data']['is_subrace'] = False # Default
            session['new_character_data']['race_trait_names'] = [] # Default
            session['new_character_data'].setdefault('race_document__slug', None) # Default


        current_app.logger.info(f"Session updated for race. Name: {session['new_character_data'].get('race_name', 'N/A')}")

    # If not 'race' step, or if 'race' step didn't have specific payload fields like 'race_slug',
    # we might still want the generic update for other step types.
    # However, for 'race', we've handled it. For other steps, the generic update is fine.
    # This logic needs adjustment as 'race' step should now also fall into generic update for most fields
    # session['new_character_data'].update(step_payload) # Apply generic update for all steps initially
    # The specific 'race' logic above now mostly populates defaults if race object is not available.

    # Let's refine: Apply step_payload generally, then override with specific logic if needed.
    session['new_character_data'].update(step_payload) # Apply general update first

    # Specific handling for 'class' step, replacing the old logic
    if step_key == 'class':
        class_slug = step_payload.get('class_slug')
        class_name = step_payload.get('class_name')
        hit_die = step_payload.get('hit_die')
        proficiencies_armor = step_payload.get('proficiencies_armor', [])
        proficiencies_weapons = step_payload.get('proficiencies_weapons', [])
        # Map proficiencies_tools from payload to tool_proficiencies_class_fixed in session
        proficiencies_tools_raw = step_payload.get('proficiencies_tools', [])
        saving_throw_proficiencies = step_payload.get('saving_throw_proficiencies', [])
        spellcasting_ability = step_payload.get('spellcasting_ability', "")
        class_features_list = step_payload.get('class_features_list', []) # Placeholder from JS
        skill_proficiencies_options_raw = step_payload.get('skill_proficiencies_options')
        skill_proficiencies_option_count = step_payload.get('skill_proficiencies_option_count')

        if not class_slug or not class_name:
            current_app.logger.error(f"Class slug or name missing in payload for 'class' step. Payload: {step_payload}")
            return jsonify(status="error", message="Class slug or name is missing."), 400

        # Store extracted values into session['new_character_data']
        session['new_character_data']['class_slug'] = class_slug
        session['new_character_data']['class_name'] = class_name
        session['new_character_data']['hit_die'] = hit_die
        session['new_character_data']['armor_proficiencies'] = proficiencies_armor
        session['new_character_data']['weapon_proficiencies'] = proficiencies_weapons
        session['new_character_data']['tool_proficiencies_class_fixed'] = proficiencies_tools_raw
        session['new_character_data']['saving_throw_proficiencies'] = saving_throw_proficiencies
        session['new_character_data']['spellcasting_ability'] = spellcasting_ability
        session['new_character_data']['class_features_list'] = class_features_list
        session['new_character_data']['skill_proficiencies_options_raw'] = skill_proficiencies_options_raw
        session['new_character_data']['skill_proficiencies_option_count'] = skill_proficiencies_option_count

        current_app.logger.info(f"Session updated for class selection: {class_name} ({class_slug})")

    elif step_key == 'ability_scores':
        assigned_scores_raw = step_payload.get('assigned_scores')
        final_scores_breakdown = step_payload.get('final_ability_scores')
        racial_asi_details = step_payload.get('racial_asi_details_applied')

        if not final_scores_breakdown or not isinstance(final_scores_breakdown, dict) or \
           not all(k in final_scores_breakdown for k in ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']):
            current_app.logger.error(f"Invalid or incomplete final_ability_scores payload: {final_scores_breakdown}")
            return jsonify(status="error", message="Invalid final ability scores data."), 400

        session['new_character_data']['ability_scores_assigned_raw'] = assigned_scores_raw
        session['new_character_data']['ability_scores_final_breakdown'] = final_scores_breakdown
        session['new_character_data']['ability_scores_racial_asi_details'] = racial_asi_details

        simple_final_scores = {k: v.get('total', 10) for k, v in final_scores_breakdown.items()}
        session['new_character_data']['ability_scores'] = simple_final_scores

        current_app.logger.info(f"Session updated for ability scores. Final simple scores: {simple_final_scores}")

    elif step_key == 'background' and 'background_slug' in step_payload:
        # Frontend now sends all necessary details, so we directly use them.
        session['new_character_data']['background_slug'] = step_payload.get('background_slug')
        session['new_character_data']['background_name'] = step_payload.get('background_name')
        session['new_character_data']['background_skill_proficiencies'] = step_payload.get('background_skill_proficiencies', [])
        session['new_character_data']['background_tool_proficiencies'] = step_payload.get('background_tool_proficiencies', [])
        session['new_character_data']['background_languages_fixed'] = step_payload.get('background_languages_fixed', [])
        session['new_character_data']['background_equipment_string'] = step_payload.get('background_equipment_string', '')
        session['new_character_data']['background_feature_name'] = step_payload.get('feature_name', '')
        session['new_character_data']['background_feature_desc'] = step_payload.get('feature_desc', '')

        current_app.logger.info(f"Session updated for background selection: {step_payload.get('background_name')} (Slug: {step_payload.get('background_slug')})")

    elif step_key == "skills":
        chosen_class_skills = step_payload.get('chosen_class_skills', [])

        if not isinstance(chosen_class_skills, list):
            current_app.logger.warning(f"Received non-list for chosen_class_skills: {chosen_class_skills}")
            # Optionally return an error or try to recover if possible, for now, log and use empty
            chosen_class_skills = []

        session['new_character_data']['chosen_class_skills'] = chosen_class_skills
        current_app.logger.info(f"Session updated for skills step. Chosen class skills: {chosen_class_skills}")

    elif step_key == "hp": # When HP is calculated
        # Payload contains max_hp, ac_base. Speed is already from race.
        pass

    elif step_key == "equipment":
        # Payload contains 'final_equipment_objects' which is a list of {name, quantity, description}
        # And potentially 'coinage_gp', 'coinage_sp', 'coinage_cp'
        pass

    elif step_key == "spells":
        # Payload contains 'chosen_cantrip_ids', 'chosen_level_1_spell_ids'
        pass

    elif step_key == "review":
        # Payload contains 'character_name', 'alignment', 'character_description', 'player_notes'
        pass


    session.modified = True
    current_app.logger.info(f"Session updated via wizard for step '{step_key}'. Current session data: {session['new_character_data']}")
    return jsonify(status="success", message="Session updated", current_character_data=session['new_character_data'])

# CHARACTER CREATION WIZARD ROUTES END
# ##############################################################################


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

# ALL_SKILLS_LIST and XP_THRESHOLDS are used in adventure route and utils.
# generate_character_sheet_text is used in level_up_apply.
# parse_coinage is used by the new creation_wizard POST route.

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
                # f"Race: {character.race.name if character.race else 'N/A'}\n" # Removed
                # f"Class: {character.char_class.name if character.char_class else 'N/A'}\n" # Removed
                f"Race: N/A\n"  # Placeholder
                f"Class: N/A\n" # Placeholder
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
        # known_spells_objects = Spell.query.filter(Spell.id.in_(known_spell_ids)).all() # Removed
        # for spell in known_spells_objects: # Removed
        #     if spell.level not in spells_by_level: # Removed
        #         spells_by_level[spell.level] = [] # Removed
        #     spells_by_level[spell.level].append(spell) # Removed
        # for level in spells_by_level: # Removed
        #     spells_by_level[level].sort(key=lambda s: s.name) # Removed
        spells_by_level = {} # Set to empty dict

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
        # 'speed': character.race.speed if character.race else 30 # Removed
        'speed': 30 # Default speed
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
    
    # level_data_dict['character_class_name'] = character.char_class.name if character.char_class else "Unknown" # Removed
    level_data_dict['character_class_name'] = "Unknown" # Default

    # if raw_spell_ids and isinstance(raw_spell_ids, list): # Removed block
    #     try:
    #         known_spells_objects = Spell.query.filter(Spell.id.in_(raw_spell_ids)).all()
    #         spells_details_list = []
    #         for spell_obj in known_spells_objects:
    #             spells_details_list.append({
    #                 'id': spell_obj.id, 'index': spell_obj.index, 'name': spell_obj.name,
    #                 'level': spell_obj.level, 'school': spell_obj.school,
    #                 'casting_time': spell_obj.casting_time, 'range': spell_obj.range,
    #                 'components': spell_obj.components, 'material': spell_obj.material,
    #                 'duration': spell_obj.duration, 'concentration': spell_obj.concentration,
    #                 'description': spell_obj.description, # Already JSON string of paragraphs
    #                 'higher_level': spell_obj.higher_level # Already JSON string of paragraphs
    #             })
    #         level_data_dict['spells_known_details'] = spells_details_list
    #     except Exception as e:
    #         current_app.logger.error(f"Error processing spells_known_details for CLID {character_level_record.id}: {str(e)}")
    level_data_dict['spells_known_details'] = [] # Set to empty list

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
        # 'class_id': character.class_id, # Removed
        # 'class_name': character.char_class.name, # Removed
        # 'hit_die': character.char_class.hit_die, # Removed
        'class_name': "Unknown Class", # Default
        'hit_die': "d8", # Default
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

    # char_class_id = level_up_data.get('class_id') # Removed
    # char_class = Class.query.get(char_class_id) # Removed
    # if not char_class: # Removed
    #     flash("Could not retrieve class data. Aborting level up.", "error") # Removed
    #     session.pop('level_up_data', None) # Removed
    #     return redirect(url_for('main.adventure', character_id=character_id)) # Removed

    new_level_number = level_up_data.get('new_level_number')
    # These are for GET request display, might be overwritten by POST
    new_features_at_this_level_names = level_up_data.get('new_features_list', []) # Renamed for clarity
    asi_count_at_this_level = level_up_data.get('asi_count_available', 0)
    gained_proficiencies_from_features = level_up_data.get('gained_proficiencies', {'skills': [], 'tools': [], 'languages': [], 'armor': [], 'weapons': [], 'saving_throws': []})


    if request.method == 'GET': 
        # if char_class.level_specific_data: # Removed
        #     try:
        #         level_specific_progression = json.loads(char_class.level_specific_data)
        #         current_level_prog_data = level_specific_progression.get(str(new_level_number))
        #         if current_level_prog_data:
        #             new_features_at_this_level_names = current_level_prog_data.get('features', [])
        #             asi_count_at_this_level = current_level_prog_data.get('asi_count', 0)

        #             # Parse features for proficiencies
        #             # This is a simplified approach. A robust solution needs structured feature data.
        #             gained_proficiencies_from_features = {'skills': [], 'tools': [], 'languages': [], 'armor': [], 'weapons': [], 'saving_throws': []}
        #             for feature_name in new_features_at_this_level_names:
        #                 if feature_name.startswith("Skill Proficiency:"):
        #                     prof_name = feature_name.replace("Skill Proficiency:", "").strip()
        #                     if prof_name: gained_proficiencies_from_features['skills'].append(prof_name)
        #                 elif feature_name.startswith("Tool Proficiency:"):
        #                     prof_name = feature_name.replace("Tool Proficiency:", "").strip()
        #                     if prof_name: gained_proficiencies_from_features['tools'].append(prof_name)
        #                 elif feature_name.startswith("Language Proficiency:"):
        #                     prof_name = feature_name.replace("Language Proficiency:", "").strip()
        #                     if prof_name: gained_proficiencies_from_features['languages'].append(prof_name)
        #                 elif feature_name.startswith("Armor Proficiency:"):
        #                     prof_name = feature_name.replace("Armor Proficiency:", "").strip()
        #                     if prof_name: gained_proficiencies_from_features['armor'].append(prof_name)
        #                 elif feature_name.startswith("Weapon Proficiency:"):
        #                     prof_name = feature_name.replace("Weapon Proficiency:", "").strip()
        #                     if prof_name: gained_proficiencies_from_features['weapons'].append(prof_name)
        #                 elif feature_name.startswith("Saving Throw Proficiency:"):
        #                     prof_name = feature_name.replace("Saving Throw Proficiency:", "").strip()
        #                     if prof_name: gained_proficiencies_from_features['saving_throws'].append(prof_name)

        #     except json.JSONDecodeError:
        #         current_app.logger.error(f"Could not parse level_specific_data for class {char_class.name}") # char_class removed
        #         flash("Error reading class progression data.", "error")
        
        # Defaulting features and ASI count
        new_features_at_this_level_names = []
        asi_count_at_this_level = 0
        gained_proficiencies_from_features = {'skills': [], 'tools': [], 'languages': [], 'armor': [], 'weapons': [], 'saving_throws': []}

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
        # if char_class.spellcasting_ability: # Removed char_class
            # cantrips_known_map = json.loads(char_class.cantrips_known_by_level or '{}') # Removed
            # spells_known_map = json.loads(char_class.spells_known_by_level or '{}') # Removed
            
            # cantrips_now = int(cantrips_known_map.get(str(new_level_number), 0)) # Removed
            # cantrips_before = int(cantrips_known_map.get(str(level_up_data['current_level_number']), 0)) # Removed
            
            # spells_now = int(spells_known_map.get(str(new_level_number), 0)) # Removed
            # spells_before = int(spells_known_map.get(str(level_up_data['current_level_number']), 0)) # Removed

            # learns_new_cantrips = cantrips_now > cantrips_before # Removed
            # learns_new_spells = spells_now > spells_before # Removed
            # if char_class.name == "Wizard": # Wizards always get to add 2 spells # Removed
            #     learns_new_spells = True # Removed

            # if learns_new_cantrips or learns_new_spells or char_class.can_prepare_spells: # Removed
            #      return redirect(url_for('main.level_up_spells', character_id=character_id)) # Removed
        # Defaulting to not redirecting to spells
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

    # char_class_id = level_up_data.get('class_id') # Removed
    # char_class = Class.query.get(char_class_id) # Removed
    # new_level_number_str = str(level_up_data.get('new_level_number')) # Kept for potential use, though class logic is gone
    # current_level_number_str = str(level_up_data.get('current_level_number')) # Kept for potential use

    # if not char_class or not char_class.spellcasting_ability: # Adjusted: Assume no spellcasting ability
    level_up_data['selected_new_cantrip_ids'] = []
    level_up_data['selected_new_spell_ids'] = []
    # session['level_up_data'] = level_up_data # This will be set later if we proceed
    # session.modified = True # This will be set later if we proceed
    # return redirect(url_for('main.level_up_review', character_id=character_id)) # Logic changed, this path might not be hit directly

    num_new_cantrips_to_choose = 0 # Default
    num_new_spells_to_choose = 0 # Default

    # try: # Removed try-except block as char_class logic is gone
        # cantrips_known_map = json.loads(char_class.cantrips_known_by_level or '{}')
        # spells_known_map = json.loads(char_class.spells_known_by_level or '{}')

        # cantrips_at_new_level = int(cantrips_known_map.get(new_level_number_str, 0))
        # cantrips_at_current_level = int(cantrips_known_map.get(current_level_number_str, 0))
        # num_new_cantrips_to_choose = max(0, cantrips_at_new_level - cantrips_at_current_level)

        # spells_at_new_level = int(spells_known_map.get(new_level_number_str, 0))
        # spells_at_current_level = int(spells_known_map.get(current_level_number_str, 0))
        
        # if char_class.name == "Wizard":
        #     num_new_spells_to_choose = 2
        # else:
        #     num_new_spells_to_choose = max(0, spells_at_new_level - spells_at_current_level)

    # except (json.JSONDecodeError, ValueError) as e:
    #     current_app.logger.error(f"Could not parse cantrips/spells known for class {char_class.name}: {e}") # char_class removed
    #     flash("Error reading class spell progression data.", "error")
    #     return redirect(url_for('main.level_up_review', character_id=character_id))

    # if num_new_cantrips_to_choose == 0 and num_new_spells_to_choose == 0 and not char_class.can_prepare_spells: # char_class removed
    if num_new_cantrips_to_choose == 0 and num_new_spells_to_choose == 0: # Simplified condition
        level_up_data['selected_new_cantrip_ids'] = []
        level_up_data['selected_new_spell_ids'] = []
        session['level_up_data'] = level_up_data
        session.modified = True
        flash("No new spells to learn or choose at this level (based on current simplified logic).", "info")
        return redirect(url_for('main.level_up_review', character_id=character_id))
    
    previous_spells_known_ids = set(level_up_data.get('previous_spells_known_ids', []))
    
    max_spell_level_castable = 0 # Default
    # if char_class.spell_slots_by_level: # Removed
    #     try:
    #         slots_by_char_level = json.loads(char_class.spell_slots_by_level)
    #         slots_for_new_level = slots_by_char_level.get(new_level_number_str, [])
    #         for i, num_slots in reversed(list(enumerate(slots_for_new_level))):
    #             if num_slots > 0:
    #                 max_spell_level_castable = i + 1
    #                 break
    #     except json.JSONDecodeError:
    #         current_app.logger.error(f"Could not parse spell_slots_by_level for class {char_class.name}") # char_class removed


    # available_cantrips_query = Spell.query.filter( # Removed
    #     Spell.level == 0, # Removed
    #     Spell.classes_that_can_use.like(f'%"{char_class.name}"%') # Removed
    # ) # Removed
    # if previous_spells_known_ids: # Removed
    #     available_cantrips_query = available_cantrips_query.filter(~Spell.id.in_(previous_spells_known_ids)) # Removed
    # available_cantrips = available_cantrips_query.order_by(Spell.name).all() # Removed
    available_cantrips = [] # Default
    
    # available_spells_query = Spell.query.filter( # Removed
    #     Spell.level > 0, # Removed
    #     Spell.level <= max_spell_level_castable, # Removed
    #     Spell.classes_that_can_use.like(f'%"{char_class.name}"%') # Removed
    # ) # Removed
    # if previous_spells_known_ids: # Removed
    #     available_spells_query = available_spells_query.filter(~Spell.id.in_(previous_spells_known_ids)) # Removed
    # available_spells = available_spells_query.order_by(Spell.level, Spell.name).all() # Removed
    available_spells = [] # Default


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
        # 'selected_new_cantrips': Spell.query.filter(Spell.id.in_(level_up_data.get('selected_new_cantrip_ids', []))).all(), # Removed
        # 'selected_new_spells': Spell.query.filter(Spell.id.in_(level_up_data.get('selected_new_spell_ids', []))).all() # Removed
        'selected_new_cantrips': [], # Default to empty list
        'selected_new_spells': []  # Default to empty list
    }
    
    # Fetch the Class object to pass to the template
    # char_class = Class.query.get(level_up_data.get('class_id')) # Removed
    # if char_class: # Removed
    #     review_data['char_class'] = char_class # Removed
    # else: # Removed
        # Handle case where class_id might be invalid or not found, though session should be reliable.
        # Setting to None or a default object, or flashing an error might be options.
        # For now, if not found, it won't be in review_data, template needs to handle potential absence.
        # current_app.logger.warning(f"Could not find class with ID {level_up_data.get('class_id')} during level_up_review for char {character_id}.") # Removed
        # review_data['char_class'] = None # Explicitly set to None if not found # Removed
    review_data['char_class'] = None # Default to None

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
    new_spell_slots_snapshot_dict = {} # Default to empty
    # char_class = Class.query.get(level_up_data['class_id']) # Removed
    # if char_class and char_class.spell_slots_by_level: # Removed
    #     try:
    #         all_slots_data = json.loads(char_class.spell_slots_by_level)
    #         slots_for_new_level_list = all_slots_data.get(str(level_up_data['new_level_number'])) # list like [4,2,0,0...]
    #         if slots_for_new_level_list:
    #             for i, num_slots in enumerate(slots_for_new_level_list):
    #                 if num_slots > 0:
    #                     new_spell_slots_snapshot_dict[str(i + 1)] = num_slots # Store as {"1": count, "2": count}
    #     except json.JSONDecodeError:
    #         current_app.logger.error(f"Could not parse spell_slots_by_level for class {char_class.name} during level up apply.") # char_class removed
    #         # Fallback to previous level's snapshot if parsing fails
    #         new_spell_slots_snapshot_dict = json.loads(current_level_entry.spell_slots_snapshot or '{}')


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
        # char_class = Class.query.get(character.class_id) # Fetch class object # Removed
        # known_spell_ids_list = json.loads(new_level_data.spells_known_ids or '[]') # Removed
        # known_spell_objects = Spell.query.filter(Spell.id.in_(known_spell_ids_list)).all() if known_spell_ids_list else [] # Removed

        # generate_character_sheet_text will need to be updated or this call will fail.
        # For now, passing None for char_class and empty list for known_spell_objects
        sheet_text = generate_character_sheet_text(character, new_level_data, None, [])
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
