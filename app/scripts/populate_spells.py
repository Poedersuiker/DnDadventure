import requests
import json
from flask import current_app # Added current_app
from app import app, db  # Import app and db from the app package
from app.models import Spell

BASE_API_URL = "https://www.dnd5eapi.co"

def populate_spells_data(task_id=None): # Added task_id
    """
    Fetches spell data from the D&D 5e API and populates the database.
    Optionally reports progress if task_id is provided.
    """
    print("Starting to populate spells...")
    
    with app.app_context():
        if task_id:
            if 'population_tasks' not in current_app.extensions:
                current_app.extensions['population_tasks'] = {}
            current_app.extensions['population_tasks'][task_id] = {
                'progress': 0,
                'status': 'Starting spell population...'
            }

        try:
            response = requests.get(BASE_API_URL + "/api/spells")
            response.raise_for_status()  # Raise an exception for HTTP errors
            spells_summary = response.json().get('results', [])
            total_spells = len(spells_summary)
            print(f"Found {total_spells} spells in the API.")
            if task_id:
                current_app.extensions['population_tasks'][task_id]['status'] = f"Found {total_spells} spells. Starting processing..."
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching spell list: {e}"
            print(error_msg)
            if task_id:
                current_app.extensions['population_tasks'][task_id] = {'progress': 0, 'status': error_msg, 'error': True}
            return
        except json.JSONDecodeError as e:
            error_msg = f"Error decoding JSON from spell list response: {e}"
            print(error_msg)
            if task_id:
                current_app.extensions['population_tasks'][task_id] = {'progress': 0, 'status': error_msg, 'error': True}
            return

        for i, spell_summary in enumerate(spells_summary):
            spell_index = spell_summary.get('index')
            spell_name_for_status = spell_summary.get('name', spell_index)
            if not spell_index:
                print(f"Skipping spell summary due to missing index: {spell_name_for_status}")
                continue

            print(f"\nProcessing spell {i+1}/{total_spells}: {spell_name_for_status} ({spell_index})")
            if task_id:
                percentage = int(((i + 1) / total_spells) * 100)
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': percentage,
                    'status': f"Processing spell {i+1}/{total_spells}: {spell_name_for_status}"
                })

            # Check if spell already exists
            existing_spell = Spell.query.filter_by(index=spell_index).first()
            if existing_spell:
                print(f"Spell '{spell_name_for_status}' already exists in the database. Skipping.")
                continue

            try:
                spell_detail_url = BASE_API_URL + spell_summary.get('url')
                detail_response = requests.get(spell_detail_url)
                detail_response.raise_for_status()
                spell_data = detail_response.json()
            except requests.exceptions.RequestException as e:
                error_msg = f"Error fetching details for {spell_index} ({spell_name_for_status}): {e}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
            except json.JSONDecodeError as e:
                error_msg = f"Error decoding JSON for {spell_index} ({spell_name_for_status}): {e}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue

            try:
                new_spell = Spell(
                    index=spell_data['index'], # Must have index
                    name=spell_data.get('name', spell_name_for_status), # Use already fetched name as fallback
                    description=json.dumps(spell_data.get('desc', [])),
                    higher_level=json.dumps(spell_data.get('higher_level', [])),
                    range=spell_data.get('range'), # Model uses 'range'
                    components=", ".join(spell_data.get('components', [])),
                    material=spell_data.get('material'),
                    ritual=spell_data.get('ritual', False),
                    duration=spell_data.get('duration'),
                    concentration=spell_data.get('concentration', False),
                    casting_time=spell_data.get('casting_time'),
                    level=spell_data.get('level', 0),
                    attack_type=spell_data.get('attack_type'), # e.g., "ranged", "melee"
                    damage_type=spell_data.get('damage', {}).get('damage_type', {}).get('name'),
                    damage_at_slot_level=json.dumps(spell_data.get('damage', {}).get('damage_at_slot_level', {})),
                    school=spell_data.get('school', {}).get('name'),
                    classes_that_can_use=json.dumps([c.get('name') for c in spell_data.get('classes', []) if c.get('name')]),
                    subclasses_that_can_use=json.dumps([sc.get('name') for sc in spell_data.get('subclasses', []) if sc.get('name')]),
                    # New fields
                    requires_attack_roll=bool(spell_data.get('attack_type')), # True if attack_type exists
                    spell_attack_ability="spellcasting" if spell_data.get('attack_type') else None # Default to spellcasting if it's an attack
                )
                db.session.add(new_spell)
                print(f"Added '{new_spell.name}' to session. Attack roll: {new_spell.requires_attack_roll}, Ability: {new_spell.spell_attack_ability}")

            except KeyError as e:
                error_msg = f"Missing critical key for spell {spell_index} ({spell_name_for_status}): {e}. Skipping this spell."
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
            except Exception as e:
                error_msg = f"An unexpected error occurred processing {spell_index} ({spell_name_for_status}): {e}"
                print(error_msg)
                if task_id:
                    current_app.extensions['population_tasks'][task_id]['status'] = error_msg
                continue
        
        try:
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': 100, # All processing presumed done
                    'status': 'Committing new spells to database...'
                })
            db.session.commit()
            print("\nAll new spells processed and session committed to database.")
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    'progress': 100,
                    'status': 'Spell population complete.'
                })
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error committing spells to database: {e}"
            print(error_msg)
            if task_id:
                current_app.extensions['population_tasks'][task_id].update({
                    # Keep progress as is or set to specific error progress
                    'status': error_msg,
                    'error': True
                })

if __name__ == '__main__':
    populate_spells_data()
    print("Spell population script finished.")
