# Example for app/character/spell_data.py
SPELL_DATA = {
    "Wizard": {
        "cantrips": [
            {"name": "Fire Bolt", "roll20_stub": "Fire%20Bolt"},
            {"name": "Light", "roll20_stub": "Light"},
            {"name": "Mage Hand", "roll20_stub": "Mage%20Hand"},
            {"name": "Ray of Frost", "roll20_stub": "Ray%20of%20Frost"},
            {"name": "Prestidigitation", "roll20_stub": "Prestidigitation"},
        ],
        "level1": [
            {"name": "Magic Missile", "roll20_stub": "Magic%20Missile"},
            {"name": "Shield", "roll20_stub": "Shield"},
            {"name": "Sleep", "roll20_stub": "Sleep"},
            {"name": "Thunderwave", "roll20_stub": "Thunderwave"},
            {"name": "Chromatic Orb", "roll20_stub": "Chromatic%20Orb"},
            {"name": "Detect Magic", "roll20_stub": "Detect%20Magic"},
        ]
    },
    "Cleric": {
        "cantrips": [
            {"name": "Guidance", "roll20_stub": "Guidance"},
            {"name": "Light", "roll20_stub": "Light"}, # Can be shared
            {"name": "Sacred Flame", "roll20_stub": "Sacred%20Flame"},
            {"name": "Thaumaturgy", "roll20_stub": "Thaumaturgy"},
            {"name": "Mending", "roll20_stub": "Mending"},
        ],
        "level1": [
            {"name": "Bless", "roll20_stub": "Bless"},
            {"name": "Cure Wounds", "roll20_stub": "Cure%20Wounds"},
            {"name": "Healing Word", "roll20_stub": "Healing%20Word"},
            {"name": "Guiding Bolt", "roll20_stub": "Guiding%20Bolt"},
            {"name": "Sanctuary", "roll20_stub": "Sanctuary"},
        ]
    },
    "Bard": {
        "cantrips": [
            {"name": "Vicious Mockery", "roll20_stub": "Vicious%20Mockery"},
            {"name": "Light", "roll20_stub": "Light"},
            {"name": "Mage Hand", "roll20_stub": "Mage%20Hand"},
        ],
        "level1": [
            {"name": "Healing Word", "roll20_stub": "Healing%20Word"},
            {"name": "Charm Person", "roll20_stub": "Charm%20Person"},
            {"name": "Dissonant Whispers", "roll20_stub": "Dissonant%20Whispers"},
            {"name": "Sleep", "roll20_stub": "Sleep"},
        ]
    },
    "Sorcerer": {
        "cantrips": [
            {"name": "Fire Bolt", "roll20_stub": "Fire%20Bolt"},
            {"name": "Chill Touch", "roll20_stub": "Chill%20Touch"},
            {"name": "Light", "roll20_stub": "Light"},
            {"name": "Prestidigitation", "roll20_stub": "Prestidigitation"},
            {"name": "Acid Splash", "roll20_stub": "Acid%20Splash"},
        ],
        "level1": [
            {"name": "Magic Missile", "roll20_stub": "Magic%20Missile"},
            {"name": "Shield", "roll20_stub": "Shield"},
            {"name": "Chromatic Orb", "roll20_stub": "Chromatic%20Orb"},
            {"name": "Burning Hands", "roll20_stub": "Burning%20Hands"},
        ]
    }
    # Fighter, Rogue, Barbarian, Monk, Paladin, Ranger typically don't get spells at L1,
    # or have very specific lists if they are a subclass (which is beyond current scope).
}

CLASS_SPELLCASTING_INFO = {
    # For level 1 characters - simplified selection rules for the wizard
    # "level1_spells_known" for Bard/Sorcerer is how many they know.
    # "spellbook_initial" for Wizard is how many they have in spellbook.
    # "level1_spells_prepared" for Cleric is based on WIS_mod + cleric_level.

    # For this wizard step, we'll simplify:
    # X_selection defines how many they pick in THIS UI step.
    "Wizard_selection": {"cantrips_to_select": 3, "level1_to_select": 2, "source_list_l1": "Wizard"}, # Pick 2 L1 to "know" for this simple step
    "Cleric_selection": {"cantrips_to_select": 3, "level1_to_select": 2, "source_list_l1": "Cleric"}, # Simplified: "prepare" 2 L1 spells
    "Bard_selection": {"cantrips_to_select": 2, "level1_to_select": 4, "source_list_l1": "Bard"},
    "Sorcerer_selection": {"cantrips_to_select": 4, "level1_to_select": 2, "source_list_l1": "Sorcerer"},
}

# Helper to get full spell details if needed later, e.g. for descriptions
# For now, just names and stubs are fine.
# def get_spell_details(class_name, spell_name):
#     # ... logic to find spell ...
#     pass
