import os
from app import app, db  # Import app and db directly
from app.models import User, Character, Race, Class, CharacterLevel, Item, Coinage, Weapon, CharacterWeaponAssociation
from app.utils import parse_coinage
import json
from datetime import datetime

# Configuration for the Flask app (e.g., testing database)
# Ensure your Flask app configuration points to a test database if necessary
# For this script, we'll use the default app configuration.

# app = create_app() # No longer needed, app is imported directly
app_context = app.app_context()
app_context.push()

print("Flask app context pushed.")

# --- Test Data ---
user_id_for_test = 1
race_id_for_test = 1
class_id_for_test = 1

final_equipment_for_test = [
    {'name': 'A holy symbol (a gift to you when you entered the priesthood)', 'quantity': 1},
    {'name': 'A prayer book or prayer wheel', 'quantity': 1},
    {'name': '5 sticks of incense', 'quantity': 1},
    {'name': 'Vestments', 'quantity': 1},
    {'name': 'A set of common clothes', 'quantity': 1},
    {'name': '15 gp', 'quantity': 1},
    {'name': 'Chain Mail', 'quantity': 1},
    {'name': 'Longsword', 'quantity': 1},
    {'name': 'Shield', 'quantity': 1},
    {'name': 'Dagger', 'quantity': 2},
    {'name': "Explorer's Pack", 'quantity': 1}
]

char_data_for_session = {
    'race_id': race_id_for_test, 'class_id': class_id_for_test, 'race_name': 'Human', 'class_name': 'Fighter',
    'ability_scores': {'STR': 15, 'DEX': 14, 'CON': 13, 'INT': 12, 'WIS': 10, 'CHA': 8},
    'background_name': 'Acolyte',
    'background_skill_proficiencies': ['Insight', 'Religion'],
    'background_tool_proficiencies': [],
    'background_languages': ['Two of your choice'],
    'class_skill_proficiencies': ['Athletics', 'Perception'],
    'max_hp': 10, 'armor_class_base': 18, 'speed': 30,
    'final_equipment': final_equipment_for_test,
    'saving_throw_proficiencies': ['STR', 'CON'], # Example, adjust if needed by CharacterLevel
    'armor_proficiencies': ['Light', 'Medium', 'Heavy', 'Shields'], # Example
    'weapon_proficiencies': ['Simple', 'Martial'], # Example
}

character_name_test = "TestEquipHero"
alignment_test = "Lawful Good"
char_description_test = "A hero for testing equipment."
new_char_id_to_clean_up = None

def run_test():
    global new_char_id_to_clean_up
    try:
        # --- Ensure Test User, Race, Class exist ---
        test_user = User.query.get(user_id_for_test)
        if not test_user:
            print(f"Test User {user_id_for_test} not found. Creating one.")
            test_user = User(id=user_id_for_test,
                             google_id=f"testgoogleid{user_id_for_test}",
                             email=f"testuser{user_id_for_test}@example.com")
            # test_user.set_password("password") # User model does not have username or password fields
            db.session.add(test_user)
            # db.session.commit() # Commit separately or as part of main commit
            print(f"Created test user {user_id_for_test}.")

        # --- Ensure Prerequisite Master Data (Race, Class, Weapons) ---
        race_1 = Race.query.get(race_id_for_test)
        if not race_1:
            print(f"Race ID {race_id_for_test} not found. Creating a dummy 'Human' race.")
            race_1 = Race(id=race_id_for_test, name="Human_Test", speed=30, ability_score_increases=json.dumps([{"name": "ALL", "bonus": 1}]), languages=json.dumps(["Common"]))
            db.session.add(race_1)

        class_1 = Class.query.get(class_id_for_test)
        if not class_1:
            print(f"Class ID {class_id_for_test} not found. Creating a dummy 'Fighter' class.")
            class_1 = Class(id=class_id_for_test, name="Fighter_Test", hit_die="d10",
                              proficiency_saving_throws=json.dumps(["STR", "CON"]),
                              skill_proficiencies_option_count=2,
                              skill_proficiencies_options=json.dumps(["Athletics", "Acrobatics", "Perception", "Survival"]),
                              starting_equipment=json.dumps([])) # Empty equipment for test simplicity
            db.session.add(class_1)

        required_weapons_data = {
            "Longsword": {"category": "Martial Melee", "damage_dice": "1d8", "damage_type": "Slashing"},
            "Shield": {"category": "Armor", "damage_dice": "N/A", "damage_type": "N/A"}, # Shields are often categorized differently, adjust if needed
            "Dagger": {"category": "Simple Melee", "damage_dice": "1d4", "damage_type": "Piercing"}
        }
        for weapon_name, data in required_weapons_data.items():
            if not Weapon.query.filter(db.func.lower(Weapon.name) == db.func.lower(weapon_name)).first():
                print(f"Master weapon '{weapon_name}' not found. Creating it.")
                new_master_weapon = Weapon(name=weapon_name, category=data["category"],
                                           damage_dice=data["damage_dice"], damage_type=data["damage_type"],
                                           cost="0 gp", weight="0 lb") # Simplified cost/weight
                db.session.add(new_master_weapon)

        # Commit any newly added master data before proceeding
        if db.session.new: # Check if there's anything to commit
            db.session.commit()
            print("Committed prerequisite master data (User/Race/Class/Weapons if any were created).")


        # --- Character Creation (Core Logic) ---
        print(f"Attempting to create character: {character_name_test}")
        new_char = Character(
            name=character_name_test, description=char_description_test, user_id=user_id_for_test,
            race_id=char_data_for_session['race_id'], class_id=char_data_for_session['class_id'], alignment=alignment_test,
            speed=char_data_for_session.get('speed', 30),
            background_name=char_data_for_session.get('background_name'),
            background_proficiencies=json.dumps(
                char_data_for_session.get('background_skill_proficiencies', []) +
                char_data_for_session.get('background_tool_proficiencies', []) +
                char_data_for_session.get('background_languages', [])
            ),
            adventure_log=json.dumps([]), dm_allowed_level=1, current_xp=0, current_hit_dice=1, player_notes=""
        )
        db.session.add(new_char)
        db.session.flush() # Get new_char.id
        new_char_id_to_clean_up = new_char.id # Store for cleanup
        print(f"Created character '{new_char.name}' with ID {new_char.id}")

        all_skill_proficiencies = set(char_data_for_session.get('background_skill_proficiencies', [])) | set(char_data_for_session.get('class_skill_proficiencies', []))
        level_1_proficiencies = {
            'skills': list(all_skill_proficiencies),
            'tools': list(set(char_data_for_session.get('background_tool_proficiencies', []))), # Add class tool profs if any
            'languages': list(set(char_data_for_session.get('background_languages', []))),
            'armor': char_data_for_session.get('armor_proficiencies', []),
            'weapons': char_data_for_session.get('weapon_proficiencies', []),
            'saving_throws': char_data_for_session.get('saving_throw_proficiencies', [])
        }

        new_char_level_1 = CharacterLevel(
            character_id=new_char.id, level_number=1, xp_at_level_up=0,
            strength=char_data_for_session['ability_scores'].get('STR', 10),
            dexterity=char_data_for_session['ability_scores'].get('DEX', 10),
            constitution=char_data_for_session['ability_scores'].get('CON', 10),
            intelligence=char_data_for_session['ability_scores'].get('INT', 10),
            wisdom=char_data_for_session['ability_scores'].get('WIS', 10),
            charisma=char_data_for_session['ability_scores'].get('CHA', 10),
            hp=char_data_for_session.get('max_hp', 0),
            max_hp=char_data_for_session.get('max_hp', 0),
            armor_class=char_data_for_session.get('armor_class_base'),
            hit_dice_rolled="Max HP at L1",
            proficiencies=json.dumps(level_1_proficiencies),
            features_gained=json.dumps(["Initial class features", "Initial race features"]),
            spells_known_ids=json.dumps([]), spells_prepared_ids=json.dumps([]), spell_slots_snapshot=json.dumps({}),
            created_at=datetime.utcnow()
        )
        db.session.add(new_char_level_1)
        print(f"Created CharacterLevel 1 for character ID {new_char.id}")

        # --- Start of copied/adapted equipment logic from creation_review ---
        print("Processing equipment...")
        final_equipment = char_data_for_session.get('final_equipment', [])
        if final_equipment:
            for item_entry in final_equipment:
                item_name = item_entry.get('name')
                item_quantity = item_entry.get('quantity', 1)

                if not item_name:
                    app.logger.warning(f"Skipping item with no name in final_equipment: {item_entry}")
                    print(f"Skipping item with no name: {item_entry}")
                    continue

                parsed_coins = parse_coinage(item_name)
                is_coinage = False
                for coin_type, amount in parsed_coins.items():
                    if amount > 0:
                        is_coinage = True
                        existing_coinage = Coinage.query.filter_by(character_id=new_char.id, name=coin_type).first()
                        if existing_coinage:
                            existing_coinage.quantity += amount
                        else:
                            new_coinage_entry = Coinage(character_id=new_char.id, name=coin_type, quantity=amount)
                            db.session.add(new_coinage_entry)
                        app.logger.info(f"Processed {amount} {coin_type} for character {new_char.id}")
                        print(f"Processed {amount} {coin_type} for character {new_char.id}")

                if is_coinage:
                    continue

                weapon = Weapon.query.filter(db.func.lower(Weapon.name) == db.func.lower(item_name)).first()
                if weapon:
                    existing_association = CharacterWeaponAssociation.query.filter_by(
                        character_id=new_char.id, weapon_id=weapon.id
                    ).first()
                    if existing_association:
                        existing_association.quantity += item_quantity
                        app.logger.info(f"Updated quantity for weapon {weapon.name} for char {new_char.id}")
                    else:
                        new_weapon_association = CharacterWeaponAssociation(
                            character_id=new_char.id, weapon_id=weapon.id, quantity=item_quantity,
                            is_equipped_main_hand=False, is_equipped_off_hand=False
                        )
                        db.session.add(new_weapon_association)
                        app.logger.info(f"Added weapon {weapon.name} to char {new_char.id}")
                    print(f"Processed weapon {weapon.name} (qty {item_quantity}) for char {new_char.id}")
                else:
                    existing_item = Item.query.filter_by(character_id=new_char.id, name=item_name).first()
                    if existing_item:
                        existing_item.quantity += item_quantity
                        app.logger.info(f"Updated quantity for item {item_name} for char {new_char.id}")
                    else:
                        new_item = Item(character_id=new_char.id, name=item_name, quantity=item_quantity, description=f"{item_name} from starting equipment.")
                        db.session.add(new_item)
                        app.logger.info(f"Added item {item_name} to char {new_char.id}")
                    print(f"Processed item {item_name} (qty {item_quantity}) for char {new_char.id}")
        else:
            app.logger.info(f"No final_equipment found in char_data_for_session for character {new_char.name}")
            print(f"No final_equipment found in char_data_for_session for character {new_char.name}")
        # --- End of copied/adapted equipment logic ---

        db.session.commit()
        print("Committed equipment and character data to DB.")

        # --- Verification ---
        print("\n--- Verification ---")
        created_char_from_db = Character.query.get(new_char.id)
        if not created_char_from_db:
            print(f"ERROR: Character {new_char.id} not found in DB after commit.")
            raise AssertionError(f"Character {new_char.id} not found post-commit.")

        # Coinage
        gp_entry = Coinage.query.filter_by(character_id=new_char.id, name="Gold").first()
        assert gp_entry is not None and gp_entry.quantity == 15, f"Gold Pcs Error: Expected 15, got {gp_entry.quantity if gp_entry else 'None'}"
        print(f"Verified: Gold Pieces = {gp_entry.quantity if gp_entry else 'None'}")

        # Items
        expected_items = {
            "A holy symbol (a gift to you when you entered the priesthood)": 1,
            "A prayer book or prayer wheel": 1,
            "5 sticks of incense": 1,
            "Vestments": 1,
            "A set of common clothes": 1,
            "Chain Mail": 1,
            "Explorer's Pack": 1
        }
        for item_name, qty in expected_items.items():
            item_entry = Item.query.filter_by(character_id=new_char.id, name=item_name).first()
            assert item_entry is not None and item_entry.quantity == qty, f"Item Error: '{item_name}' - Expected {qty}, got {item_entry.quantity if item_entry else 'None'}"
            print(f"Verified: Item '{item_name}' quantity = {item_entry.quantity if item_entry else 'None'}")

        # Weapons
        expected_weapons = {"Longsword": 1, "Shield": 1, "Dagger": 2}
        for weapon_name, qty in expected_weapons.items():
            weapon_master = Weapon.query.filter(db.func.lower(Weapon.name) == db.func.lower(weapon_name)).first()
            assert weapon_master is not None, f"Master weapon '{weapon_name}' not found in DB for test setup. This indicates a setup issue for the test."
            weapon_assoc = CharacterWeaponAssociation.query.filter_by(character_id=new_char.id, weapon_id=weapon_master.id).first()
            assert weapon_assoc is not None and weapon_assoc.quantity == qty, f"Weapon Assoc Error: '{weapon_name}' - Expected {qty}, got {weapon_assoc.quantity if weapon_assoc else 'None'}"
            print(f"Verified: Weapon '{weapon_name}' quantity = {weapon_assoc.quantity if weapon_assoc else 'None'}")

        print("\nTest script completed assertions successfully.")

    except Exception as e:
        db.session.rollback()
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # --- Cleanup ---
        if new_char_id_to_clean_up:
            print("\n--- Cleanup ---")
            try:
                char_to_delete = Character.query.get(new_char_id_to_clean_up)
                if char_to_delete:
                    Coinage.query.filter_by(character_id=new_char_id_to_clean_up).delete()
                    Item.query.filter_by(character_id=new_char_id_to_clean_up).delete()
                    CharacterWeaponAssociation.query.filter_by(character_id=new_char_id_to_clean_up).delete()
                    CharacterLevel.query.filter_by(character_id=new_char_id_to_clean_up).delete()
                    db.session.delete(char_to_delete)
                    db.session.commit()
                    print(f"Cleaned up test character ID {new_char_id_to_clean_up} and related data.")
                else:
                    print(f"Character ID {new_char_id_to_clean_up} already deleted or not found for cleanup.")
            except Exception as e:
                db.session.rollback()
                print(f"Error during cleanup: {e}")
                import traceback
                traceback.print_exc()

        app_context.pop()
        print("Flask app context popped.")

if __name__ == '__main__':
    run_test()
