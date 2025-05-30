import requests
import json
from flask import current_app # Added current_app
from app import app, db
from app.models import Race

BASE_API_URL = "https://www.dnd5eapi.co"

def populate_races_data(task_id=None): # Added task_id parameter
    """
    Fetches race data from the D&D 5e API and populates the database.
    Optionally reports progress if task_id is provided.
    """
    print("Starting to populate races...")

    with app.app_context(): # Ensures app context for db operations
        if task_id:
            if 'population_tasks' not in current_app.extensions:
                current_app.extensions['population_tasks'] = {}
            current_app.extensions['population_tasks'][task_id] = {
                'progress': 0,
                'status': 'Starting race population...'
            }

        try:
            response = requests.get(BASE_API_URL + "/api/races")
            response.raise_for_status()
            races_summary = response.json().get('results', [])
            total_races = len(races_summary)
            print(f"Found {total_races} races in the API.")
            if task_id:
                current_app.extensions['population_tasks'][task_id]['status'] = f"Found {total_races} races. Starting processing..."
        except requests.exceptions.RequestException as e:
            print(f"Error fetching race list: {e}")
            if task_id:
                current_app.extensions['population_tasks'][task_id] = {
                    'progress': 0,
                    'status': f"Error fetching race list: {e}",
                    'error': True
                }
            return
        except json.JSONDecodeError:
            print("Error decoding JSON from race list response.")
            if task_id:
                current_app.extensions['population_tasks'][task_id] = {
                    'progress': 0,
                    'status': "Error decoding JSON from race list response.",
                    'error': True
                }
            return

        for i, race_summary in enumerate(races_summary):
            race_index = race_summary.get('index')
            if not race_index:
                print(f"Skipping race summary due to missing index: {race_summary.get('name')}")
                continue

            race_name_for_status = race_summary.get('name', race_index)
            print(f"\nProcessing race {i+1}/{total_races}: {race_name_for_status} ({race_index})")
            if task_id:
                percentage = int((i + 1) / total_races * 100)
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': percentage,
                    'status': f"Processing race {i+1}/{total_races}: {race_name_for_status}"
                })

            # Check if race already exists
            # The API uses 'index' for unique ID, but 'name' is also usually unique for races.
            # Model uses 'name' as unique, so we should query by name.
            # Fetch details first to get the canonical name
            try:
                race_detail_url = BASE_API_URL + race_summary.get('url')
                detail_response = requests.get(race_detail_url)
                detail_response.raise_for_status()
                race_data = detail_response.json()
            except requests.exceptions.RequestException as e:
                error_message = f"Error fetching details for {race_index} ({race_name_for_status}): {e}"
                print(error_message)
                if task_id:
                    # Update status, but don't mark as a fatal error for the whole task yet
                    current_app.extensions['population_tasks'][task_id]['status'] = error_message
                continue
            except json.JSONDecodeError as e:
                error_message = f"Error decoding JSON for {race_index} ({race_name_for_status}): {e}"
                print(error_message)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_message
                continue

            # Now check if race already exists using the canonical name from race_data
            canonical_name = race_data.get('name')
            if not canonical_name:
                error_message = f"Skipping race due to missing canonical name for index: {race_index}"
                print(error_message)
                if task_id: # Also update status if task_id is present
                    current_app.extensions['population_tasks'][task_id]['status'] = error_message
                continue
            
            existing_race = Race.query.filter_by(name=canonical_name).first()
            if existing_race:
                print(f"Race '{canonical_name}' already exists in the database. Skipping.")
                continue

            try:
                # Ability Score Increases
                ability_bonuses_transformed = []
                for bonus_info in race_data.get('ability_bonuses', []):
                    if bonus_info.get('ability_score') and 'name' in bonus_info['ability_score']:
                        ability_bonuses_transformed.append({
                            'name': bonus_info['ability_score']['name'],
                            'bonus': bonus_info.get('bonus', 0)
                        })
                
                # Languages
                languages_list = [lang.get('name') for lang in race_data.get('languages', []) if lang.get('name')]

                # Traits
                traits_list = [trait.get('name') for trait in race_data.get('traits', []) if trait.get('name')]

                # Skill Proficiencies (combining fixed and choices)
                all_skill_profs = []
                # Fixed proficiencies
                for prof in race_data.get('starting_proficiencies', []):
                    if prof.get('url', '').startswith('/api/proficiencies/skill-'): # Check if it's a skill
                        all_skill_profs.append(prof.get('name'))
                
                # Proficiency choices (like Half-Elf)
                # The structure is: "starting_proficiency_options": { "choose": N, "from": { "option_set_type": "options_array", "options": [ { "option_type": "reference", "item": { "index": "skill-arcana", ...}} ... ]}}
                proficiency_options = race_data.get('starting_proficiency_options')
                if proficiency_options and proficiency_options.get('from', {}).get('option_set_type') == 'options_array':
                    for option in proficiency_options.get('from', {}).get('options', []):
                        item = option.get('item', {})
                        if item and item.get('index','').startswith('skill-'): # Check if the item is a skill
                             # For races that get to CHOOSE skills, we list the options.
                             # The model field `skill_proficiencies` is a simple list of granted skills.
                             # For races like standard Human (all +1) or Mountain Dwarf (armor), this is fine.
                             # For Half-Elf (choose 2), listing all options might be too much for a simple field.
                             # The prompt asks for: json.dumps([prof['name'] for prof_choice in race_data.get('starting_proficiency_options', []) ...])
                             # This implies listing the *options* if skills are choosable.
                             # Let's stick to the prompt's structure for choosable skills.
                             # The prompt example: json.dumps([prof['name'] for prof_choice in race_data.get('starting_proficiency_options', []) for prof in prof_choice.get('from', {}).get('options', []) if 'skill-' in prof.get('item',{}).get('url','')])
                             # This structure of `starting_proficiency_options` in the API is usually a single object, not a list of prof_choices.
                             # Let's re-evaluate based on actual API structure for "half-elf" for example.
                             # Half-elf: "starting_proficiency_options": { "choose": 2, "desc": "Skills", "from": { "option_set_type": "options_array", "options": [ { "option_type": "reference", "item": {"index": "skill-acrobatics", ...}} ... ]}}
                             # So, we iterate options within the single 'from' object.
                            all_skill_profs.append(item.get('name')) # Add chosen/available skill name

                # Remove duplicates if any skill was listed as fixed and also an option (unlikely but good practice)
                final_skill_profs = list(set(all_skill_profs))


                new_race = Race(
                    name=canonical_name, # Use canonical_name which is validated
                    speed=race_data.get('speed'),
                    ability_score_increases=json.dumps(ability_bonuses_transformed),
                    age_description=race_data.get('age'),
                    alignment_description=race_data.get('alignment'),
                    size=race_data.get('size'),
                    size_description=race_data.get('size_description'),
                    languages=json.dumps(languages_list),
                    traits=json.dumps(traits_list),
                    skill_proficiencies=json.dumps(final_skill_profs) # Combined fixed and choosable skills
                )
                db.session.add(new_race)
                print(f"Added '{new_race.name}' to session.")

            except KeyError as e:
                error_message = f"Missing critical key for race {race_index} (Name: {race_data.get('name', 'N/A')}): {e}. Skipping this race."
                print(error_message)
                if task_id: # Update status for this specific race error
                    current_app.extensions['population_tasks'][task_id]['status'] = error_message
                continue
            except Exception as e:
                error_message = f"An unexpected error occurred processing {race_index} (Name: {race_data.get('name', 'N/A')}): {e}"
                print(error_message)
                if task_id: # Update status for this specific race error
                    current_app.extensions['population_tasks'][task_id]['status'] = error_message
                continue
        
        try:
            if task_id:
                # Update status before commit, progress is effectively 100% for processing part
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': 100, # Assuming all individual processing is done
                    'status': 'Committing new races to database...'
                })
            db.session.commit()
            print("\nAll new races processed and session committed to database.")
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': 100,
                    'status': 'Race population complete.'
                })
        except Exception as e:
            db.session.rollback()
            error_message = f"Error committing races to database: {e}"
            print(error_message)
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    # Keep previous progress or set to a specific value indicating commit error
                    'status': error_message,
                    'error': True
                })

if __name__ == '__main__':
    populate_races_data()
    print("Race population script finished.")
