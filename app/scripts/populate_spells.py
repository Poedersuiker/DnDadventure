import requests
import json
from app import app, db  # Import app and db from the app package
from app.models import Spell

BASE_API_URL = "https://www.dnd5eapi.co"

def populate_spells_data():
    """
    Fetches spell data from the D&D 5e API and populates the database.
    """
    print("Starting to populate spells...")
    
    # Push an application context
    with app.app_context():
        try:
            response = requests.get(BASE_API_URL + "/api/spells")
            response.raise_for_status()  # Raise an exception for HTTP errors
            spells_summary = response.json().get('results', [])
            print(f"Found {len(spells_summary)} spells in the API.")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching spell list: {e}")
            return
        except json.JSONDecodeError:
            print("Error decoding JSON from spell list response.")
            return

        for i, spell_summary in enumerate(spells_summary):
            spell_index = spell_summary.get('index')
            if not spell_index:
                print(f"Skipping spell summary due to missing index: {spell_summary.get('name')}")
                continue

            print(f"\nProcessing spell {i+1}/{len(spells_summary)}: {spell_summary.get('name')} ({spell_index})")

            # Check if spell already exists
            existing_spell = Spell.query.filter_by(index=spell_index).first()
            if existing_spell:
                print(f"Spell '{spell_summary.get('name')}' already exists in the database. Skipping.")
                continue

            try:
                spell_detail_url = BASE_API_URL + spell_summary.get('url')
                detail_response = requests.get(spell_detail_url)
                detail_response.raise_for_status()
                spell_data = detail_response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching details for {spell_index}: {e}")
                continue
            except json.JSONDecodeError:
                print(f"Error decoding JSON for {spell_index}.")
                continue

            try:
                new_spell = Spell(
                    index=spell_data['index'], # Must have index
                    name=spell_data.get('name', 'Unknown Spell Name'),
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
                    attack_type=spell_data.get('attack_type'),
                    damage_type=spell_data.get('damage', {}).get('damage_type', {}).get('name'),
                    damage_at_slot_level=json.dumps(spell_data.get('damage', {}).get('damage_at_slot_level', {})),
                    school=spell_data.get('school', {}).get('name'),
                    classes_that_can_use=json.dumps([c.get('name') for c in spell_data.get('classes', []) if c.get('name')]),
                    subclasses_that_can_use=json.dumps([sc.get('name') for sc in spell_data.get('subclasses', []) if sc.get('name')])
                )
                db.session.add(new_spell)
                print(f"Added '{new_spell.name}' to session.")

            except KeyError as e:
                print(f"Missing critical key for spell {spell_index}: {e}. Skipping this spell.")
                # No db.session.rollback() needed here as the object wasn't added yet or will be skipped.
                continue # Skip to next spell
            except Exception as e:
                print(f"An unexpected error occurred processing {spell_index}: {e}")
                continue # Skip to next spell
        
        try:
            db.session.commit()
            print("\nAll new spells processed and session committed to database.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing spells to database: {e}")

if __name__ == '__main__':
    populate_spells_data()
    print("Spell population script finished.")
