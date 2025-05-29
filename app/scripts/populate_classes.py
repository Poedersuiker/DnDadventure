import requests
import json
from app import app, db
from app.models import Class

BASE_API_URL = "https://www.dnd5eapi.co"

def get_proficiencies(prof_data_list, category_keywords):
    """Helper to extract and filter proficiencies by keywords in their URL or name."""
    extracted_profs = []
    for p in prof_data_list:
        # Check if any keyword is in the proficiency's name or URL (if URL exists)
        # Some proficiencies (like "All armor") might not have a URL but are still valid
        name_match = any(keyword.lower() in p.get('name', '').lower() for keyword in category_keywords)
        url_match = 'url' in p and any(keyword in p['url'] for keyword in category_keywords)
        
        if name_match or url_match:
            extracted_profs.append(p.get('name'))
    return list(set(extracted_profs)) # Use set to remove duplicates, then convert to list

def populate_classes_data():
    """
    Fetches class data from the D&D 5e API and populates the database.
    """
    print("Starting to populate classes...")

    with app.app_context():
        try:
            response = requests.get(BASE_API_URL + "/api/classes")
            response.raise_for_status()
            classes_summary = response.json().get('results', [])
            print(f"Found {len(classes_summary)} classes in the API.")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching class list: {e}")
            return
        except json.JSONDecodeError:
            print("Error decoding JSON from class list response.")
            return

        for i, class_summary in enumerate(classes_summary):
            class_index = class_summary.get('index')
            if not class_index:
                print(f"Skipping class summary due to missing index: {class_summary.get('name')}")
                continue

            print(f"\nProcessing class {i+1}/{len(classes_summary)}: {class_summary.get('name')} ({class_index})")

            existing_class = Class.query.filter_by(name=class_summary.get('name')).first()
            if existing_class:
                print(f"Class '{class_summary.get('name')}' already exists in the database. Skipping.")
                continue

            try:
                class_detail_url = BASE_API_URL + class_summary.get('url')
                detail_response = requests.get(class_detail_url)
                detail_response.raise_for_status()
                class_data = detail_response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching details for {class_index}: {e}")
                continue
            except json.JSONDecodeError:
                print(f"Error decoding JSON for {class_index}.")
                continue
            
            # Spellcasting details might be in a separate endpoint or under a 'spellcasting' key
            # For simplicity, we first try the main class_data.
            # A more robust solution might query /api/classes/{index}/spellcasting or /levels
            spellcasting_data = class_data.get('spellcasting', {})
            
            # If spellcasting_data is empty, try fetching from /spellcasting endpoint
            if not spellcasting_data and class_data.get('spellcasting_api'): # D&D API specific for spellcasting info
                try:
                    sc_response = requests.get(BASE_API_URL + class_data['spellcasting_api']['url'])
                    sc_response.raise_for_status()
                    spellcasting_data_specific = sc_response.json()
                    # Merge or prioritize specific spellcasting data
                    # For now, let's assume the specific endpoint is more detailed for spellcasting ability
                    spellcasting_data['spellcasting_ability'] = spellcasting_data_specific.get('spellcasting_ability')
                    # The levels endpoint is usually better for slots, cantrips known, spells known per level
                    # This part is complex as it requires fetching /levels and parsing per-level data.
                    # For this script, we'll keep it simpler and rely on what's in the main class or direct spellcasting object.
                    # The model fields spell_slots_by_level etc. expect a JSON of {level: value}
                    # This typically comes from the /levels endpoint which is not fetched here to keep it simple.
                    # print(f"Fetched additional spellcasting data for {class_index}") # Original print
                except requests.exceptions.RequestException as e: # Correctly indented
                    print(f"Error fetching specific spellcasting details for {class_index}: {e}")
                except json.JSONDecodeError: # Correctly indented
                    print(f"Error decoding specific spellcasting JSON for {class_index}.")

        # --- Fetch and process levels data for spell_slots_by_level ---
        spell_slots_by_level_map = {}
        levels_url = BASE_API_URL + f"/api/classes/{class_index}/levels"
        print(f"Fetching levels data from: {levels_url}")
        try:
            levels_response = requests.get(levels_url)
            levels_response.raise_for_status() # Raise an exception for HTTP errors
            levels_data = levels_response.json()

            for level_specific_data in levels_data:
                char_level = level_specific_data.get('level')
                if char_level is None:
                    print(f"Skipping level data for {class_index} due to missing 'level' key: {level_specific_data}")
                    continue

                spellcasting_info_for_level = level_specific_data.get('spellcasting', {})
                slots_at_this_char_level = [0] * 9 # Index 0 for spell_level_1, ..., Index 8 for spell_level_9

                for i in range(9): # Spell levels 1 to 9
                    slot_key = f'spell_slots_level_{i+1}'
                    slots_at_this_char_level[i] = spellcasting_info_for_level.get(slot_key, 0)
                
                spell_slots_by_level_map[str(char_level)] = slots_at_this_char_level
            
            print(f"Successfully processed levels data for {class_index}. Map has {len(spell_slots_by_level_map)} entries.")

        except requests.exceptions.RequestException as e:
            print(f"Error fetching levels data for {class_index} from {levels_url}: {e}")
            # spell_slots_by_level_map remains {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from levels data for {class_index} from {levels_url}.")
            # spell_slots_by_level_map remains {}
        except Exception as e: # Catch any other unexpected errors during levels processing
            print(f"An unexpected error occurred while processing levels data for {class_index}: {e}")
            # spell_slots_by_level_map remains {}
        # --- End of levels data processing ---

            # Proficiencies
            all_proficiencies = class_data.get('proficiencies', [])
            proficiencies_armor = get_proficiencies(all_proficiencies, ['armor', 'shield'])
            proficiencies_weapons = get_proficiencies(all_proficiencies, ['weapon']) # General term 'weapon'
            proficiencies_tools = get_proficiencies(all_proficiencies, ['artisans-tools', 'musical-instruments', 'kit', 'vehicle', 'tool'])


            # Skill proficiency choices
            # This requires careful parsing of 'proficiency_choices'
            skill_prof_options_list = []
            skill_prof_choose_count = 0
            for choice_group in class_data.get('proficiency_choices', []):
                if choice_group.get('desc','').lower().startswith('skills'): # Check description or type
                    skill_prof_choose_count = choice_group.get('choose', 0)
                    for option in choice_group.get('from', {}).get('options', []):
                        if option.get('item', {}).get('index','').startswith('skill-'):
                             skill_prof_options_list.append(option['item'].get('name'))
                    break # Assuming one main skill choice group

            # Starting Equipment - already a list of objects, can be directly JSON dumped
            starting_equipment_json = json.dumps(class_data.get('starting_equipment', []))
            # Also consider starting_equipment_options for more complex choices
            # For now, sticking to the simpler `starting_equipment` field.

            # can_prepare_spells
            preparer_classes = ["Wizard", "Cleric", "Druid", "Paladin"]
            can_prepare = class_data.get('name') in preparer_classes

            try:
                new_class = Class(
                    name=class_data['name'],
                    hit_die="d" + str(class_data.get('hit_die', 0)), # API gives number, model expects "d8"
                    proficiencies_armor=json.dumps(proficiencies_armor),
                    proficiencies_weapons=json.dumps(proficiencies_weapons),
                    proficiencies_tools=json.dumps(proficiencies_tools),
                    proficiency_saving_throws=json.dumps([st.get('name') for st in class_data.get('saving_throws', [])]),
                    skill_proficiencies_option_count=skill_prof_choose_count,
                    skill_proficiencies_options=json.dumps(skill_prof_options_list),
                    starting_equipment=starting_equipment_json, # Storing the direct equipment list
                    spellcasting_ability=spellcasting_data.get('spellcasting_ability', {}).get('name') if spellcasting_data else None,
                    spell_slots_by_level=json.dumps(spell_slots_by_level_map), # Updated
                    # Placeholders for cantrips and spells known per level, as per instructions
                    cantrips_known_by_level=json.dumps({}), # Placeholder
                    spells_known_by_level=json.dumps({}), # Placeholder
                    can_prepare_spells=can_prepare
                )
                db.session.add(new_class)
                print(f"Added '{new_class.name}' to session.")
            except KeyError as e:
                print(f"Missing critical key for class {class_index}: {e}. Skipping this class.")
                continue
            except Exception as e:
                print(f"An unexpected error occurred processing {class_index}: {e}")
                continue
        
        try:
            db.session.commit()
            print("\nAll new classes processed and session committed to database.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing classes to database: {e}")

if __name__ == '__main__':
    populate_classes_data()
    print("Class population script finished.")
