import requests
import json
import time # Added for potential sleep
from flask import current_app # Added current_app
from app import app, db
from app.models import Class

BASE_API_URL = "https://www.dnd5eapi.co"

def get_proficiencies(prof_data_list, category_keywords):
    """Helper to extract and filter proficiencies by keywords in their URL or name."""
    extracted_profs = []
    for p in prof_data_list:
        name_match = any(keyword.lower() in p.get('name', '').lower() for keyword in category_keywords)
        url_match = 'url' in p and any(keyword in p['url'] for keyword in category_keywords)
        
        if name_match or url_match:
            extracted_profs.append(p.get('name'))
    return list(set(extracted_profs))

def populate_classes_data(task_id=None): # Added task_id
    """
    Fetches class data from the D&D 5e API and populates the database.
    Optionally reports progress if task_id is provided.
    """
    print("Starting to populate classes...")

    with app.app_context():
        if task_id:
            if 'population_tasks' not in current_app.extensions:
                current_app.extensions['population_tasks'] = {}
            current_app.extensions['population_tasks'][task_id] = {
                'progress': 0,
                'status': 'Starting class population...'
            }

        try:
            response = requests.get(BASE_API_URL + "/api/classes")
            response.raise_for_status()
            classes_summary = response.json().get('results', [])
            total_classes = len(classes_summary)
            print(f"Found {total_classes} classes in the API.")
            if task_id:
                current_app.extensions['population_tasks'][task_id]['status'] = f"Found {total_classes} classes. Starting processing..."
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching class list: {e}"
            print(error_msg)
            if task_id:
                current_app.extensions['population_tasks'][task_id] = {'progress': 0, 'status': error_msg, 'error': True}
            return
        except json.JSONDecodeError as e:
            error_msg = f"Error decoding JSON from class list response: {e}"
            print(error_msg)
            if task_id:
                current_app.extensions['population_tasks'][task_id] = {'progress': 0, 'status': error_msg, 'error': True}
            return

        for i, class_summary in enumerate(classes_summary):
            class_index = class_summary.get('index')
            if not class_index:
                print(f"Skipping class summary due to missing index: {class_summary.get('name')}")
                continue

            class_name_for_print = class_summary.get('name', class_index)
            print(f"Processing class {i+1}/{total_classes}: {class_name_for_print}")

            if task_id:
                percentage = int(((i + 1) / total_classes) * 100)
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': percentage,
                    'status': f"Processing class {i+1}/{total_classes}: {class_name_for_print}"
                })

            existing_class = Class.query.filter_by(name=class_name_for_print).first()
            if existing_class:
                status_update_msg = f"Class '{class_name_for_print}' already exists. Checking for level_specific_data..."
                print(status_update_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = status_update_msg

                if existing_class.level_specific_data and existing_class.level_specific_data != '{}':
                    status_update_msg = f"level_specific_data already populated for '{class_name_for_print}'. Skipping."
                    print(status_update_msg)
                    if task_id:
                         current_app.extensions['population_tasks'][task_id]['status'] = status_update_msg
                else:
                    status_update_msg = f"Attempting to populate level_specific_data for existing class '{class_name_for_print}'."
                    print(status_update_msg)
                    if task_id:
                        current_app.extensions['population_tasks'][task_id]['status'] = status_update_msg

                    all_levels_data_for_this_class = {}
                    class_levels_url = f"{BASE_API_URL}/api/classes/{class_index}/levels"
                    try:
                        levels_response = requests.get(class_levels_url)
                        levels_response.raise_for_status()
                        levels_api_data_existing = levels_response.json() # Renamed to avoid clash
                        for level_entry in levels_api_data_existing:
                            level_num_int = level_entry.get('level')
                            if not level_num_int: continue
                            current_level_features = [feature.get('name', 'Unknown Feature') for feature in level_entry.get('features', [])]
                            asi_this_level = sum(1 for feature_name in current_level_features if "Ability Score Improvement" in feature_name)
                            all_levels_data_for_this_class[str(level_num_int)] = {
                                "features": current_level_features,
                                "asi_count": asi_this_level
                            }
                        existing_class.level_specific_data = json.dumps(all_levels_data_for_this_class if all_levels_data_for_this_class else {})
                        status_update_msg = f"Populated level_specific_data for '{class_name_for_print}'."
                        print(status_update_msg)
                        if task_id:
                            current_app.extensions['population_tasks'][task_id]['status'] = status_update_msg
                    except requests.exceptions.RequestException as e_level:
                        error_msg = f"Error fetching level data for {class_index}: {e_level}"
                        print(error_msg)
                        if task_id:
                            current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                    except json.JSONDecodeError as e_json:
                        error_msg = f"Error decoding JSON for {class_index} levels: {e_json}"
                        print(error_msg)
                        if task_id:
                            current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                    except Exception as e_gen:
                        error_msg = f"An unexpected error occurred while processing levels for {class_index}: {e_gen}"
                        print(error_msg)
                        if task_id:
                            current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue # Move to next class


            try:
                class_detail_url = BASE_API_URL + class_summary.get('url')
                detail_response = requests.get(class_detail_url)
                detail_response.raise_for_status()
                class_data = detail_response.json()
            except requests.exceptions.RequestException as e:
                error_msg = f"Error fetching details for {class_index} ({class_name_for_print}): {e}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
            except json.JSONDecodeError as e:
                error_msg = f"Error decoding JSON for {class_index} ({class_name_for_print}): {e}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
            
            # Fetch and process level-specific data (features, ASIs)
            # This variable will store data for the NEW class being added
            all_levels_data_for_new_class = {} # Renamed to avoid confusion
            class_levels_url = f"{BASE_API_URL}/api/classes/{class_index}/levels"
            print(f"Fetching detailed level data for {class_name_for_print} from {class_levels_url}")
            levels_api_data = None # Initialize before try block
            try:
                levels_response = requests.get(class_levels_url)
                levels_response.raise_for_status()
                levels_api_data = levels_response.json() # This is a list of level objects

                for level_entry in levels_api_data:
                    level_num_int = level_entry.get('level')
                    if not level_num_int:
                        print(f"Skipping a level entry for {class_name_for_print} due to missing 'level' key.")
                        continue
                    
                    current_level_features = []
                    for feature_ref in level_entry.get('features', []): # 'features' is a list of refs
                        current_level_features.append(feature_ref.get('name', 'Unknown Feature'))
                        # No need to fetch feature details if only name is needed as per example

                    asi_this_level = sum(1 for feature_name in current_level_features if "Ability Score Improvement" in feature_name)
                    
                    all_levels_data_for_new_class[str(level_num_int)] = { # Use renamed variable
                        "features": current_level_features,
                        "asi_count": asi_this_level
                    }
                print(f"Successfully processed detailed level data for {class_name_for_print}.")
                # Optional: time.sleep(0.1) # Be respectful to the API
            except requests.exceptions.RequestException as e_level:
                error_msg = f"Error fetching detailed level data for {class_name_for_print}: {e_level}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
            except json.JSONDecodeError as e_json:
                error_msg = f"Error decoding JSON for {class_name_for_print} detailed levels: {e_json}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
            except Exception as e_gen: # Catch any other unexpected error during level processing
                error_msg = f"An unexpected error occurred while processing detailed levels for {class_name_for_print}: {e_gen}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg

            spellcasting_data = class_data.get('spellcasting', {})
            if not spellcasting_data and class_data.get('spellcasting_api'): # D&D API inconsistency
                try:
                    sc_response = requests.get(BASE_API_URL + class_data['spellcasting_api']['url'])
                    sc_response.raise_for_status()
                    spellcasting_data_specific = sc_response.json()
                    # Manually populate spellcasting_data for consistency
                    spellcasting_data['spellcasting_ability'] = spellcasting_data_specific.get('spellcasting_ability')
                    # Note: spell slots are per level, not globally on spellcasting object in dnd5eapi
                except requests.exceptions.RequestException as e:
                    error_msg = f"Error fetching specific spellcasting details for {class_index}: {e}"
                    print(error_msg)
                    if task_id:
                        current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                except json.JSONDecodeError as e_json:
                    error_msg = f"Error decoding specific spellcasting JSON for {class_index}: {e_json}"
                    print(error_msg)
                    if task_id:
                        current_app.extensions['population_tasks'][task_id]['status'] = error_msg

            # Process spell slots (already present in the original script, but ensure it uses levels_api_data)
            spell_slots_by_level_map = {}
            cantrips_known_map = {}
            spells_known_map = {}

            if levels_api_data: # Use the already fetched levels_api_data
                for level_entry in levels_api_data:
                    char_level = level_entry.get('level')
                    if char_level is None: continue

                    spellcasting_info_for_level = level_entry.get('spellcasting', {})
                    slots_at_this_char_level = [0] * 9 
                    for slot_idx in range(9):
                        slot_key = f'spell_slots_level_{slot_idx+1}'
                        slots_at_this_char_level[slot_idx] = spellcasting_info_for_level.get(slot_key, 0)
                    spell_slots_by_level_map[str(char_level)] = slots_at_this_char_level

                    # Cantrips known
                    cantrips_count = spellcasting_info_for_level.get('cantrips_known')
                    if cantrips_count is not None:
                        cantrips_known_map[str(char_level)] = cantrips_count
                    
                    # Spells known (for classes like Sorcerer, Bard, Ranger, Warlock)
                    spells_known_count = spellcasting_info_for_level.get('spells_known')
                    if spells_known_count is not None:
                        spells_known_map[str(char_level)] = spells_known_count
            else:
                print(f"Skipping spell slot/known processing for {class_name_for_print} as levels_api_data is missing.")


            all_proficiencies = class_data.get('proficiencies', [])
            proficiencies_armor = get_proficiencies(all_proficiencies, ['armor', 'shield'])
            proficiencies_weapons = get_proficiencies(all_proficiencies, ['weapon'])
            proficiencies_tools = get_proficiencies(all_proficiencies, ['artisans-tools', 'musical-instruments', 'kit', 'vehicle', 'tool'])

            skill_prof_options_list = []
            skill_prof_choose_count = 0
            for choice_group in class_data.get('proficiency_choices', []):
                if choice_group.get('desc','').lower().startswith('skills'): # Check description
                    skill_prof_choose_count = choice_group.get('choose', 0)
                    for option in choice_group.get('from', {}).get('options', []):
                        # Ensure it's a skill proficiency
                        if option.get('item', {}).get('index','').startswith('skill-'):
                                skill_prof_options_list.append(option['item'].get('name'))
                    break # Assuming only one such choice group for skills

            starting_equipment_json = json.dumps(class_data.get('starting_equipment', []))
            
            preparer_classes = ["Wizard", "Cleric", "Druid", "Paladin"] # Artificer might also fit here
            can_prepare = class_data.get('name') in preparer_classes

            try:
                new_class = Class(
                    name=class_data['name'],
                    hit_die="d" + str(class_data.get('hit_die', 0)),
                    proficiencies_armor=json.dumps(proficiencies_armor),
                    proficiencies_weapons=json.dumps(proficiencies_weapons),
                    proficiencies_tools=json.dumps(proficiencies_tools),
                    proficiency_saving_throws=json.dumps([st.get('name') for st in class_data.get('saving_throws', [])]),
                    skill_proficiencies_option_count=skill_prof_choose_count,
                    skill_proficiencies_options=json.dumps(skill_prof_options_list),
                    starting_equipment=starting_equipment_json,
                    spellcasting_ability=spellcasting_data.get('spellcasting_ability', {}).get('name') if spellcasting_data else None,
                    spell_slots_by_level=json.dumps(spell_slots_by_level_map if spell_slots_by_level_map else {}),
                    cantrips_known_by_level=json.dumps(cantrips_known_map if cantrips_known_map else {}),
                    spells_known_by_level=json.dumps(spells_known_map if spells_known_map else {}),
                    can_prepare_spells=can_prepare,
                    level_specific_data=json.dumps(all_levels_data_for_new_class if all_levels_data_for_new_class else {}) # Use renamed variable
                )
                db.session.add(new_class)
                print(f"Added '{new_class.name}' to session.")
            except KeyError as e:
                error_msg = f"Missing critical key for class {class_index} ({class_name_for_print}): {e}. Skipping this class."
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
            except Exception as e: # General exception during Class object creation
                error_msg = f"An unexpected error occurred creating Class object for {class_index} ({class_name_for_print}): {e}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
        
        # Moved commit outside the loop to commit all new classes at once
        try:
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': 100, # All processing presumed done
                    'status': 'Committing new classes to database...'
                })
            db.session.commit()
            print("All new classes processed and session committed to database.")
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': 100,
                    'status': 'Class population complete.'
                })
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error committing classes to database: {e}"
            print(error_msg)
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    # Keep progress as is or set to a specific error progress
                    'status': error_msg,
                    'error': True
                })

if __name__ == '__main__':
    populate_classes_data()
    print("Class population script finished.")
