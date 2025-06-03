import json
import random
import re # For _parse_gold and new character sheet
from flask import current_app
import google.generativeai as genai
import logging # For logging errors/warnings

# Constants for character sheet generation and other utils
ALL_SKILLS_LIST = [
    ("Acrobatics", "DEX"), ("Animal Handling", "WIS"), ("Arcana", "INT"),
    ("Athletics", "STR"), ("Deception", "CHA"), ("History", "INT"),
    ("Insight", "WIS"), ("Intimidation", "CHA"), ("Investigation", "INT"),
    ("Medicine", "WIS"), ("Nature", "INT"), ("Perception", "WIS"),
    ("Performance", "CHA"), ("Persuasion", "CHA"), ("Religion", "INT"),
    ("Sleight of Hand", "DEX"), ("Stealth", "DEX"), ("Survival", "WIS")
]

# Mapping for ability score names (used in character sheet generation)
ABILITY_NAMES_FULL = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']
ABILITY_SHORT_TO_FULL = {
    'STR': 'Strength', 'DEX': 'Dexterity', 'CON': 'Constitution',
    'INT': 'Intelligence', 'WIS': 'Wisdom', 'CHA': 'Charisma'
}
# And the reverse, if needed, though character_level stores full names lowercase
ABILITY_FULL_TO_SHORT = {v: k for k,v in ABILITY_SHORT_TO_FULL.items()}


XP_THRESHOLDS = {
    1: 300, 2: 900, 3: 2700, 4: 6500, 5: 14000, 6: 23000, 7: 34000,
    8: 48000, 9: 64000, 10: 85000, 11: 100000, 12: 120000, 13: 140000,
    14: 165000, 15: 195000, 16: 225000, 17: 265000, 18: 305000, 19: 355000
}


def roll_dice(num_dice: int, num_sides: int, drop_lowest: int = 0) -> tuple[int, list[int]]:
    '''
    Rolls a specified number of dice with a given number of sides,
    optionally dropping a specified number of the lowest rolls.

    Args:
        num_dice (int): The number of dice to roll.
        num_sides (int): The number of sides on each die.
        drop_lowest (int): The number of lowest dice rolls to drop. Default is 0.

    Returns:
        tuple[int, list[int]]: A tuple containing the sum of the final rolls
                               and a list of all dice rolls made.
    '''
    if num_dice <= 0 or num_sides <= 0:
        raise ValueError("Number of dice and sides must be positive.")
    if drop_lowest < 0 or drop_lowest >= num_dice:
        raise ValueError("Number of dice to drop must be non-negative and less than the number of dice.")

    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    
    if drop_lowest > 0:
        # To get the sum of the highest rolls, we sort and then slice off the lowest ones.
        # The 'rolls' list itself is not modified for the return value if drop_lowest is used.
        sorted_rolls_for_sum = sorted(rolls)
        final_rolls_for_sum = sorted_rolls_for_sum[drop_lowest:]
        sum_of_rolls = sum(final_rolls_for_sum)
    else:
        sum_of_rolls = sum(rolls)
    
    return sum_of_rolls, rolls # Return original rolls for transparency

def list_gemini_models():
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key or api_key == 'YOUR_GEMINI_API_KEY_HERE':
        logging.warning("GEMINI_API_KEY is not configured or is set to the placeholder.")
        return []

    try:
        genai.configure(api_key=api_key)
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                models.append(m.name)
        return models
    except Exception as e:
        logging.error(f"Error listing Gemini models: {e}")
        return []

def parse_coinage(text_content: str) -> dict:
    """
    Parses a string to find and return amounts of gold (gp), silver (sp), and copper (cp).
    Returns a dictionary with keys 'Gold', 'Silver', 'Copper' and their respective amounts.
    Amounts default to 0 if not found.
    """
    coins = {'Gold': 0, 'Silver': 0, 'Copper': 0}
    if not text_content or not isinstance(text_content, str):
        return coins

    # Regex for gold: number followed by "gp", "gold pieces", or "g" (case insensitive)
    gold_match = re.search(r'(\d+)\s*(gp|gold\s*pieces?|g)\b', text_content, re.IGNORECASE)
    if gold_match:
        coins['Gold'] = int(gold_match.group(1))

    # Regex for silver: number followed by "sp" or "silver pieces" (case insensitive)
    silver_match = re.search(r'(\d+)\s*(sp|silver\s*pieces?)\b', text_content, re.IGNORECASE)
    if silver_match:
        coins['Silver'] = int(silver_match.group(1))

    # Regex for copper: number followed by "cp" or "copper pieces" (case insensitive)
    copper_match = re.search(r'(\d+)\s*(cp|copper\s*pieces?)\b', text_content, re.IGNORECASE)
    if copper_match:
        coins['Copper'] = int(copper_match.group(1))
        
    return coins

def generate_character_sheet_text(character, character_level, char_class_obj, spell_objects_known=None):
    """
    Generates a string representation of a character sheet.
    - character: The Character model instance.
    - character_level: The specific CharacterLevel model instance for the desired level.
    - char_class_obj: The Class model instance for the character.
    - spell_objects_known: Optional list of Spell model instances known by the character at this level.
                           If None, spell names won't be listed, only counts.
    """
    sheet_lines = []
    separator = "-" * 30

    # Basic Information
    sheet_lines.append(f"Name: {character.name}")
    # sheet_lines.append(f"Race: {character.race.name if character.race else 'N/A'}") # character.race no longer exists
    sheet_lines.append(f"Race: N/A") # Placeholder
    sheet_lines.append(f"Class: {char_class_obj.name if char_class_obj else 'N/A'}") # Keep as is, will show N/A if char_class_obj is None
    sheet_lines.append(f"Level: {character_level.level_number}")
    sheet_lines.append(f"Background: {character.background_name or 'N/A'}")
    sheet_lines.append(f"Alignment: {character.alignment or 'N/A'}")
    sheet_lines.append(separator)

    # Ability Scores & Modifiers
    sheet_lines.append("Ability Scores:")
    abilities = {
        'STR': character_level.strength, 'DEX': character_level.dexterity,
        'CON': character_level.constitution, 'INT': character_level.intelligence,
        'WIS': character_level.wisdom, 'CHA': character_level.charisma
    }
    ability_modifiers = {name: (score - 10) // 2 for name, score in abilities.items()}
    for ability_short_upper in ABILITY_SHORT_TO_FULL.keys(): # Iterate in defined order STR, DEX...
        score = abilities.get(ability_short_upper, 10)
        modifier = ability_modifiers.get(ability_short_upper, 0)
        sheet_lines.append(f"  {ABILITY_SHORT_TO_FULL[ability_short_upper]}: {score} ({'+' if modifier >= 0 else ''}{modifier})")
    sheet_lines.append(separator)

    # Combat Stats
    sheet_lines.append("Combat Stats:")
    sheet_lines.append(f"  HP: {character_level.hp}/{character_level.max_hp}")
    sheet_lines.append(f"  AC: {character_level.armor_class or 'N/A'}")
    # sheet_lines.append(f"  Speed: {character.race.speed if character.race else 'N/A'} ft.") # character.race no longer exists
    sheet_lines.append(f"  Speed: {character.speed if hasattr(character, 'speed') else 'N/A'} ft.") # Use character.speed if available
    prof_bonus = (character_level.level_number - 1) // 4 + 2
    sheet_lines.append(f"  Proficiency Bonus: +{prof_bonus}")
    sheet_lines.append(f"  Hit Dice: {character.current_hit_dice}/{character_level.level_number} ({char_class_obj.hit_die if char_class_obj and hasattr(char_class_obj, 'hit_die') else 'N/A'})")
    sheet_lines.append(separator)

    # Proficiencies
    sheet_lines.append("Proficiencies:")
    try:
        prof_data = json.loads(character_level.proficiencies or '{}')
    except json.JSONDecodeError:
        prof_data = {}

    # Saving Throws
    sheet_lines.append("  Saving Throws:")
    prof_saving_throws = prof_data.get('saving_throws', []) # Expected: list of "STR", "DEX"
    for ability_short_upper in ABILITY_SHORT_TO_FULL.keys():
        modifier = ability_modifiers[ability_short_upper]
        is_proficient = ability_short_upper in prof_saving_throws
        final_save_modifier = modifier + (prof_bonus if is_proficient else 0)
        prefix = "* " if is_proficient else "  "
        sheet_lines.append(f"    {prefix}{ABILITY_SHORT_TO_FULL[ability_short_upper]}: {'+' if final_save_modifier >= 0 else ''}{final_save_modifier}")

    # Skills
    sheet_lines.append("  Skills:")
    prof_skills = prof_data.get('skills', [])
    for skill_name, skill_ability_abbr_upper in ALL_SKILLS_LIST: # skill_ability_abbr is "DEX", "STR" etc.
        base_ability_modifier = ability_modifiers[skill_ability_abbr_upper]
        is_proficient = skill_name in prof_skills
        final_skill_modifier = base_ability_modifier + (prof_bonus if is_proficient else 0)
        prefix = "* " if is_proficient else "  "
        sheet_lines.append(f"    {prefix}{skill_name} ({skill_ability_abbr_upper}): {'+' if final_skill_modifier >= 0 else ''}{final_skill_modifier}")

    for prof_type_key in ['armor', 'weapons', 'tools', 'languages']:
        items = prof_data.get(prof_type_key, [])
        sheet_lines.append(f"  {prof_type_key.capitalize()}: {', '.join(items) if items else 'None'}")
    sheet_lines.append(separator)

    # Spells
    if char_class_obj and hasattr(char_class_obj, 'spellcasting_ability') and char_class_obj.spellcasting_ability:
        sheet_lines.append("Spells:")
        known_spell_ids_json = character_level.spells_known_ids or '[]'
        known_spell_ids_list = []
        try:
            known_spell_ids_list = json.loads(known_spell_ids_json)
        except json.JSONDecodeError:
            logging.warning(f"Could not parse spells_known_ids for char_level {character_level.id}: {known_spell_ids_json}")

        if spell_objects_known: # If full spell objects are provided (which will be [] if Spell model is gone)
            cantrips = sorted([sp.name for sp in spell_objects_known if hasattr(sp, 'level') and sp.level == 0])
            other_spells = sorted([sp.name for sp in spell_objects_known if hasattr(sp, 'level') and sp.level > 0])
            sheet_lines.append(f"  Known Cantrips ({len(cantrips)}): {', '.join(cantrips) or 'None'}")
            sheet_lines.append(f"  Known Spells ({len(other_spells)}): {', '.join(other_spells) or 'None'}")
        else: # Fallback to just count if full objects aren't available
            sheet_lines.append(f"  Known Spell IDs Count: {len(known_spell_ids_list)}")

        # Display raw known spell IDs if spell_objects_known is empty but IDs exist
        if not spell_objects_known and known_spell_ids_list:
            sheet_lines.append(f"  Known Spell IDs (raw): {', '.join(map(str, known_spell_ids_list))}")


        slots_summary_parts = []
        if character_level.spell_slots_snapshot:
            try:
                # Expected format: {"1": 2, "2": 3} (spell_level_str: count)
                slots_snapshot_dict = json.loads(character_level.spell_slots_snapshot)
                for spell_lvl_str, num_slots in sorted(slots_snapshot_dict.items(), key=lambda x: int(x[0])):
                    slots_summary_parts.append(f"L{spell_lvl_str}: {num_slots}")
            except json.JSONDecodeError:
                slots_summary_parts.append("Error parsing slots data")
        sheet_lines.append(f"  Spell Slots Available: {', '.join(slots_summary_parts) if slots_summary_parts else 'None (or Non-caster)'}")
        sheet_lines.append(separator)
    else: # char_class_obj is None or not a spellcaster
        sheet_lines.append("Spells: N/A (Character class not specified or is not a spellcaster)")
        sheet_lines.append(separator)


    # Experience
    sheet_lines.append("Experience:")
    sheet_lines.append(f"  Current XP: {character.current_xp}")
    xp_for_next = XP_THRESHOLDS.get(character_level.level_number, "Max level")
    if xp_for_next != "Max level":
        sheet_lines.append(f"  XP for Level {character_level.level_number + 1}: {xp_for_next}")
    else:
        sheet_lines.append(f"  XP for Next Level: Max level reached")
    sheet_lines.append(separator)

    # Equipment (from Character.items)
    sheet_lines.append("Equipment:")
    if character.items: # Assuming character.items is a list of Item objects
        for item in character.items:
            desc_part = f" - {item.description}" if item.description and item.description.strip() else ""
            sheet_lines.append(f"  - {item.name} (x{item.quantity}){desc_part}")
    else:
        sheet_lines.append("  None")

    sheet_lines.append("Coinage:")
    if character.coinage: # Assuming character.coinage is a list of Coinage objects
        coins_str_parts = [f"{coin.quantity} {coin.name}" for coin in character.coinage if coin.quantity > 0]
        sheet_lines.append(f"  {', '.join(coins_str_parts) if coins_str_parts else 'None'}")
    else:
        sheet_lines.append("  None")

    return "\n".join(sheet_lines)


def inject_build_info():
    """Injects build-time information into the template context."""
    return dict(
        GIT_BRANCH=current_app.config.get('GIT_BRANCH', 'unknown'),
        DEPLOYMENT_TIME=current_app.config.get('DEPLOYMENT_TIME', 'N/A')
    )
