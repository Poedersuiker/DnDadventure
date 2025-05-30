import json
import re
from app import db
from app.models import Weapon

def parse_range_from_properties(properties_list, property_prefix):
    """
    Parses normal and long range from a property string like "thrown (range 20/60)"
    or "ammunition (range 80/320)".
    Returns (normal_range, long_range) or (None, None) if not found or unparseable.
    """
    for prop in properties_list:
        prop_lower = prop.lower()
        if prop_lower.startswith(property_prefix):
            match = re.search(r'range\s*(\d+)/(\d+)', prop_lower)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None, None

def populate_weapons_data():
    """
    Populates the database with a list of D&D 5e weapons.
    """
    weapons_data = [
        # Simple Melee Weapons
        {"name": "Club", "category": "Simple Melee", "cost": "1 sp", "damage_dice": "1d4", "damage_type": "Bludgeoning", "weight": "2 lb.", "properties": ["light"], "range": "5 ft."},
        {"name": "Dagger", "category": "Simple Melee", "cost": "2 gp", "damage_dice": "1d4", "damage_type": "Piercing", "weight": "1 lb.", "properties": ["finesse", "light", "thrown (range 20/60)"], "range": "5 ft."},
        {"name": "Greatclub", "category": "Simple Melee", "cost": "2 sp", "damage_dice": "1d8", "damage_type": "Bludgeoning", "weight": "10 lb.", "properties": ["two-handed"], "range": "5 ft."},
        {"name": "Handaxe", "category": "Simple Melee", "cost": "5 gp", "damage_dice": "1d6", "damage_type": "Slashing", "weight": "2 lb.", "properties": ["light", "thrown (range 20/60)"], "range": "5 ft."},
        {"name": "Javelin", "category": "Simple Melee", "cost": "5 sp", "damage_dice": "1d6", "damage_type": "Piercing", "weight": "2 lb.", "properties": ["thrown (range 30/120)"], "range": "5 ft."},
        {"name": "Light Hammer", "category": "Simple Melee", "cost": "2 gp", "damage_dice": "1d4", "damage_type": "Bludgeoning", "weight": "2 lb.", "properties": ["light", "thrown (range 20/60)"], "range": "5 ft."},
        {"name": "Mace", "category": "Simple Melee", "cost": "5 gp", "damage_dice": "1d6", "damage_type": "Bludgeoning", "weight": "4 lb.", "properties": [], "range": "5 ft."},
        {"name": "Quarterstaff", "category": "Simple Melee", "cost": "2 sp", "damage_dice": "1d6", "damage_type": "Bludgeoning", "weight": "4 lb.", "properties": ["versatile (1d8)"], "range": "5 ft."},
        {"name": "Sickle", "category": "Simple Melee", "cost": "1 gp", "damage_dice": "1d4", "damage_type": "Slashing", "weight": "2 lb.", "properties": ["light"], "range": "5 ft."},
        {"name": "Spear", "category": "Simple Melee", "cost": "1 gp", "damage_dice": "1d6", "damage_type": "Piercing", "weight": "3 lb.", "properties": ["thrown (range 20/60)", "versatile (1d8)"], "range": "5 ft."},

        # Simple Ranged Weapons
        {"name": "Crossbow, Light", "category": "Simple Ranged", "cost": "25 gp", "damage_dice": "1d8", "damage_type": "Piercing", "weight": "5 lb.", "properties": ["ammunition (range 80/320)", "loading", "two-handed"], "range": "80/320 ft."},
        {"name": "Dart", "category": "Simple Ranged", "cost": "5 cp", "damage_dice": "1d4", "damage_type": "Piercing", "weight": "1/4 lb.", "properties": ["finesse", "thrown (range 20/60)"], "range": "20/60 ft."},
        {"name": "Shortbow", "category": "Simple Ranged", "cost": "25 gp", "damage_dice": "1d6", "damage_type": "Piercing", "weight": "2 lb.", "properties": ["ammunition (range 80/320)", "two-handed"], "range": "80/320 ft."},
        {"name": "Sling", "category": "Simple Ranged", "cost": "1 sp", "damage_dice": "1d4", "damage_type": "Bludgeoning", "weight": "0 lb.", "properties": ["ammunition (range 30/120)"], "range": "30/120 ft."},

        # Martial Melee Weapons
        {"name": "Battleaxe", "category": "Martial Melee", "cost": "10 gp", "damage_dice": "1d8", "damage_type": "Slashing", "weight": "4 lb.", "properties": ["versatile (1d10)"], "range": "5 ft."},
        {"name": "Flail", "category": "Martial Melee", "cost": "10 gp", "damage_dice": "1d8", "damage_type": "Bludgeoning", "weight": "2 lb.", "properties": [], "range": "5 ft."},
        {"name": "Glaive", "category": "Martial Melee", "cost": "20 gp", "damage_dice": "1d10", "damage_type": "Slashing", "weight": "6 lb.", "properties": ["heavy", "reach", "two-handed"], "range": "10 ft."},
        {"name": "Greataxe", "category": "Martial Melee", "cost": "30 gp", "damage_dice": "1d12", "damage_type": "Slashing", "weight": "7 lb.", "properties": ["heavy", "two-handed"], "range": "5 ft."},
        {"name": "Greatsword", "category": "Martial Melee", "cost": "50 gp", "damage_dice": "2d6", "damage_type": "Slashing", "weight": "6 lb.", "properties": ["heavy", "two-handed"], "range": "5 ft."},
        {"name": "Halberd", "category": "Martial Melee", "cost": "20 gp", "damage_dice": "1d10", "damage_type": "Slashing", "weight": "6 lb.", "properties": ["heavy", "reach", "two-handed"], "range": "10 ft."},
        {"name": "Lance", "category": "Martial Melee", "cost": "10 gp", "damage_dice": "1d12", "damage_type": "Piercing", "weight": "6 lb.", "properties": ["reach", "special"], "range": "10 ft."}, # Special: Disadvantage to attack target within 5 feet. Need mount to wield with one hand.
        {"name": "Longsword", "category": "Martial Melee", "cost": "15 gp", "damage_dice": "1d8", "damage_type": "Slashing", "weight": "3 lb.", "properties": ["versatile (1d10)"], "range": "5 ft."},
        {"name": "Maul", "category": "Martial Melee", "cost": "10 gp", "damage_dice": "2d6", "damage_type": "Bludgeoning", "weight": "10 lb.", "properties": ["heavy", "two-handed"], "range": "5 ft."},
        {"name": "Morningstar", "category": "Martial Melee", "cost": "15 gp", "damage_dice": "1d8", "damage_type": "Piercing", "weight": "4 lb.", "properties": [], "range": "5 ft."},
        {"name": "Pike", "category": "Martial Melee", "cost": "5 gp", "damage_dice": "1d10", "damage_type": "Piercing", "weight": "18 lb.", "properties": ["heavy", "reach", "two-handed"], "range": "10 ft."},
        {"name": "Rapier", "category": "Martial Melee", "cost": "25 gp", "damage_dice": "1d8", "damage_type": "Piercing", "weight": "2 lb.", "properties": ["finesse"], "range": "5 ft."},
        {"name": "Scimitar", "category": "Martial Melee", "cost": "25 gp", "damage_dice": "1d6", "damage_type": "Slashing", "weight": "3 lb.", "properties": ["finesse", "light"], "range": "5 ft."},
        {"name": "Shortsword", "category": "Martial Melee", "cost": "10 gp", "damage_dice": "1d6", "damage_type": "Piercing", "weight": "2 lb.", "properties": ["finesse", "light"], "range": "5 ft."},
        {"name": "Trident", "category": "Martial Melee", "cost": "5 gp", "damage_dice": "1d6", "damage_type": "Piercing", "weight": "4 lb.", "properties": ["thrown (range 20/60)", "versatile (1d8)"], "range": "5 ft."},
        {"name": "War Pick", "category": "Martial Melee", "cost": "5 gp", "damage_dice": "1d8", "damage_type": "Piercing", "weight": "2 lb.", "properties": [], "range": "5 ft."},
        {"name": "Warhammer", "category": "Martial Melee", "cost": "15 gp", "damage_dice": "1d8", "damage_type": "Bludgeoning", "weight": "2 lb.", "properties": ["versatile (1d10)"], "range": "5 ft."},
        {"name": "Whip", "category": "Martial Melee", "cost": "2 gp", "damage_dice": "1d4", "damage_type": "Slashing", "weight": "3 lb.", "properties": ["finesse", "reach"], "range": "10 ft."},

        # Martial Ranged Weapons
        {"name": "Blowgun", "category": "Martial Ranged", "cost": "10 gp", "damage_dice": "1", "damage_type": "Piercing", "weight": "1 lb.", "properties": ["ammunition (range 25/100)", "loading"], "range": "25/100 ft."},
        {"name": "Crossbow, Hand", "category": "Martial Ranged", "cost": "75 gp", "damage_dice": "1d6", "damage_type": "Piercing", "weight": "3 lb.", "properties": ["ammunition (range 30/120)", "light", "loading"], "range": "30/120 ft."},
        {"name": "Crossbow, Heavy", "category": "Martial Ranged", "cost": "50 gp", "damage_dice": "1d10", "damage_type": "Piercing", "weight": "18 lb.", "properties": ["ammunition (range 100/400)", "heavy", "loading", "two-handed"], "range": "100/400 ft."},
        {"name": "Longbow", "category": "Martial Ranged", "cost": "50 gp", "damage_dice": "1d8", "damage_type": "Piercing", "weight": "2 lb.", "properties": ["ammunition (range 150/600)", "heavy", "two-handed"], "range": "150/600 ft."},
        {"name": "Net", "category": "Martial Ranged", "cost": "1 gp", "damage_dice": "-", "damage_type": "-", "weight": "3 lb.", "properties": ["special", "thrown (range 5/15)"], "range": "5/15 ft."} # Special: creature hit is Restrained.
    ]

    existing_weapons = {w.name for w in Weapon.query.all()}
    count_added = 0
    count_skipped = 0

    for data in weapons_data:
        if data["name"] in existing_weapons:
            # print(f"Skipping existing weapon: {data['name']}")
            count_skipped += 1
            continue

        is_martial_weapon = "martial" in data["category"].lower()

        normal_rng, long_rng = None, None
        throw_norm_rng, throw_long_rng = None, None

        # Parse range from "range" field first (for bows, crossbows, slings)
        if data.get("range") and "/" in data["range"]:
            range_parts = data["range"].split('/')
            try:
                normal_rng = int(range_parts[0].replace("ft.", "").strip())
                long_rng = int(range_parts[1].replace("ft.", "").strip())
            except ValueError:
                # print(f"Could not parse direct range for {data['name']}: {data['range']}")
                pass # Keep them None

        # Parse ranges from properties
        # For weapons like Dart, Javelin, Handaxe (thrown)
        tnr, tlr = parse_range_from_properties(data["properties"], "thrown (range")
        if tnr is not None:
            throw_norm_rng, throw_long_rng = tnr, tlr
            # If it's primarily a thrown weapon and normal_rng wasn't set from main range field (e.g. Dart)
            if normal_rng is None and data["category"] == "Simple Ranged": # Darts are simple ranged
                 normal_rng, long_rng = tnr, tlr


        # For weapons like bows, crossbows (ammunition)
        # This might overwrite normal_rng/long_rng if they were also set by direct range field, which is fine.
        anr, alr = parse_range_from_properties(data["properties"], "ammunition (range")
        if anr is not None:
            normal_rng, long_rng = anr, alr


        weapon = Weapon(
            name=data["name"],
            category=data["category"],
            cost=data.get("cost"),
            damage_dice=data["damage_dice"],
            damage_type=data["damage_type"],
            weight=data.get("weight"),
            properties=json.dumps(data.get("properties", [])),
            range=data.get("range"), # Store the original string range too
            normal_range=normal_rng,
            long_range=long_rng,
            throw_range_normal=throw_norm_rng,
            throw_range_long=throw_long_rng,
            is_martial=is_martial_weapon
        )
        db.session.add(weapon)
        count_added += 1
        # print(f"Adding weapon: {weapon.name}")

    try:
        db.session.commit()
        print(f"Successfully added {count_added} new weapons. Skipped {count_skipped} existing weapons.")
    except Exception as e:
        db.session.rollback()
        print(f"Error populating weapons: {e}")

if __name__ == '__main__':
    # This part is for running the script directly, e.g., via `python -m app.scripts.populate_weapons`
    # It requires the Flask app context to be set up.
    # from app import create_app # Assuming you have a create_app factory
    # app = create_app()
    # with app.app_context():
    #     populate_weapons_data()
    # However, the prompt suggests `flask shell < app/scripts/populate_weapons.py`
    # which implies the script content itself will be executed within an existing app context.
    # So, the direct call below is appropriate for that execution method.
    populate_weapons_data()
    print("Weapon population script finished.")

# To run this from flask shell:
# from app.scripts.populate_weapons import populate_weapons_data
# populate_weapons_data()
# exit()
# Or, if your Flask app is named `app.py` or `wsgi.py` in the root, and you have `db` and `Weapon` imported:
# flask shell
# >>> from app.scripts.populate_weapons import populate_weapons_data
# >>> populate_weapons_data()
# >>> exit()
# If running from command line directly (needs app context):
# export FLASK_APP=your_flask_app_entry_point.py  (e.g., run.py or wsgi.py)
# flask exec app/scripts/populate_weapons.py
# Or, if the script itself sets up the app context (as shown in the commented __main__ block)
# python app/scripts/populate_weapons.py
#
# For the specific request `flask shell < app/scripts/populate_weapons.py`:
# The script needs to directly call populate_weapons_data() at the end,
# and ensure `db` and `Weapon` are imported from `app` and `app.models` respectively.
# The imports `from app import db` and `from app.models import Weapon` at the top are key.
# The `if __name__ == '__main__':` block is less relevant for the pipe method but good for other execution ways.
# The final print statement confirms execution.
