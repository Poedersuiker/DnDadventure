import requests
import json
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

            print(f"Processing class {i+1}/{len(classes_summary)}: {class_summary.get('name')} ({class_index})")

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
            
            spellcasting_data = class_data.get('spellcasting', {})
            
            if not spellcasting_data and class_data.get('spellcasting_api'):
                try:
                    sc_response = requests.get(BASE_API_URL + class_data['spellcasting_api']['url'])
                    sc_response.raise_for_status()
                    spellcasting_data_specific = sc_response.json()
                    spellcasting_data['spellcasting_ability'] = spellcasting_data_specific.get('spellcasting_ability')
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching specific spellcasting details for {class_index}: {e}")
                except json.JSONDecodeError:
                    print(f"Error decoding specific spellcasting JSON for {class_index}.")

            spell_slots_by_level_map = {}
            levels_url = BASE_API_URL + f"/api/classes/{class_index}/levels"
            print(f"Fetching levels data from: {levels_url}")
            try:
                levels_response = requests.get(levels_url)
                levels_response.raise_for_status()
                levels_data = levels_response.json()

                for level_specific_data in levels_data:
                    char_level = level_specific_data.get('level')
                    if char_level is None:
                        print(f"Skipping level data for {class_index} due to missing 'level' key: {level_specific_data}")
                        continue

                    spellcasting_info_for_level = level_specific_data.get('spellcasting', {})
                    slots_at_this_char_level = [0] * 9 

                    for slot_idx in range(9):
                        slot_key = f'spell_slots_level_{slot_idx+1}'
                        slots_at_this_char_level[slot_idx] = spellcasting_info_for_level.get(slot_key, 0)
                    
                    spell_slots_by_level_map[str(char_level)] = slots_at_this_char_level
                
                print(f"Successfully processed levels data for {class_index}. Map has {len(spell_slots_by_level_map)} entries.")

            except requests.exceptions.RequestException as e:
                print(f"Error fetching levels data for {class_index} from {levels_url}: {e}")
            except json.JSONDecodeError:
                print(f"Error decoding JSON from levels data for {class_index} from {levels_url}.")
            except Exception as e:
                print(f"An unexpected error occurred while processing levels data for {class_index}: {e}")

            all_proficiencies = class_data.get('proficiencies', [])
            proficiencies_armor = get_proficiencies(all_proficiencies, ['armor', 'shield'])
            proficiencies_weapons = get_proficiencies(all_proficiencies, ['weapon'])
            proficiencies_tools = get_proficiencies(all_proficiencies, ['artisans-tools', 'musical-instruments', 'kit', 'vehicle', 'tool'])

            skill_prof_options_list = []
            skill_prof_choose_count = 0
            for choice_group in class_data.get('proficiency_choices', []):
                if choice_group.get('desc','').lower().startswith('skills'):
                    skill_prof_choose_count = choice_group.get('choose', 0)
                    for option in choice_group.get('from', {}).get('options', []):
                        if option.get('item', {}).get('index','').startswith('skill-'):
                                skill_prof_options_list.append(option['item'].get('name'))
                    break

            starting_equipment_json = json.dumps(class_data.get('starting_equipment', []))
            
            preparer_classes = ["Wizard", "Cleric", "Druid", "Paladin"]
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
                    spell_slots_by_level=json.dumps(spell_slots_by_level_map),
                    cantrips_known_by_level=json.dumps({}),
                    spells_known_by_level=json.dumps({}),
                    can_prepare_spells=can_prepare
                )
                db.session.add(new_class)
                print(f"Added '{new_class.name}' to session.")
            except KeyError as e:
                print(f"Missing critical key for class {class_index}: {e}. Skipping this class.")
                continue
            except Exception as e:
                print(f"An unexpected error occurred processing {class_index}: {e}")
                continue # This is the corrected position of the continue

        try:
            db.session.commit()
            print("All new classes processed and session committed to database.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing classes to database: {e}")

if __name__ == '__main__':
    populate_classes_data()
    print("Class population script finished.")
