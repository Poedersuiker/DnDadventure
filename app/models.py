from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db # Import db from extensions
from datetime import datetime
import math # For calculating average HP gain

# XP thresholds for leveling up (index i is for level i+1)
# e.g., XP_THRESHOLDS[0] is XP for level 1 (0), XP_THRESHOLDS[1] is XP for level 2 (300)
XP_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000
] # Max level 20

# Simplified Class Data for Model Logic (HP gain, hit dice type)
# Average HP gain = (Hit Die / 2) + 1
CLASS_DATA_MODEL = {
    "Artificer": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5}, # (8/2)+1 = 5
    "Barbarian": {"hit_dice_type": 12, "avg_hp_gain_per_level": 7}, # (12/2)+1 = 7
    "Bard": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5},
    "Cleric": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5},
    "Druid": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5},
    "Fighter": {"hit_dice_type": 10, "avg_hp_gain_per_level": 6}, # (10/2)+1 = 6
    "Monk": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5},
    "Paladin": {"hit_dice_type": 10, "avg_hp_gain_per_level": 6},
    "Ranger": {"hit_dice_type": 10, "avg_hp_gain_per_level": 6},
    "Rogue": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5},
    "Sorcerer": {"hit_dice_type": 6, "avg_hp_gain_per_level": 4}, # (6/2)+1 = 4
    "Warlock": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5},
    "Wizard": {"hit_dice_type": 6, "avg_hp_gain_per_level": 4},
    "Default": {"hit_dice_type": 8, "avg_hp_gain_per_level": 5} # Fallback
}


class User(UserMixin, db.Model): # type: ignore
    __tablename__ = 'user' # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    characters = db.relationship('Character', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Character(db.Model): # type: ignore
    __tablename__ = 'character' # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    race = db.Column(db.String(50))
    character_class = db.Column(db.String(50)) # "class" is reserved
    level = db.Column(db.Integer, default=1)
    strength = db.Column(db.Integer, default=10)
    dexterity = db.Column(db.Integer, default=10)
    constitution = db.Column(db.Integer, default=10)
    intelligence = db.Column(db.Integer, default=10)
    wisdom = db.Column(db.Integer, default=10)
    charisma = db.Column(db.Integer, default=10)
    max_hp = db.Column(db.Integer, default=10)
    current_hp = db.Column(db.Integer, default=10) # Should default to max_hp
    temporary_hp = db.Column(db.Integer, default=0)
    armor_class = db.Column(db.Integer, default=10)
    # initiative_bonus will be a property method
    speed = db.Column(db.Integer, default=30) # Standard speed
    hit_dice_type = db.Column(db.Integer, default=8) # e.g., d8 for a common class
    hit_dice_current = db.Column(db.Integer, default=1) # Should default to level
    hit_dice_max = db.Column(db.Integer, default=1) # Should default to level

    # Proficiency Bonus - Will be calculated by a method based on level
    # proficiency_bonus = db.Column(db.Integer, default=2) # Default for level 1
    
    alignment = db.Column(db.String(50))
    background = db.Column(db.String(100))
    experience_points = db.Column(db.Integer, default=0)
    
    # Skill Proficiencies
    prof_athletics = db.Column(db.Boolean, default=False)
    prof_acrobatics = db.Column(db.Boolean, default=False)
    prof_sleight_of_hand = db.Column(db.Boolean, default=False)
    prof_stealth = db.Column(db.Boolean, default=False)
    prof_arcana = db.Column(db.Boolean, default=False)
    prof_history = db.Column(db.Boolean, default=False)
    prof_investigation = db.Column(db.Boolean, default=False)
    prof_nature = db.Column(db.Boolean, default=False)
    prof_religion = db.Column(db.Boolean, default=False)
    prof_animal_handling = db.Column(db.Boolean, default=False)
    prof_insight = db.Column(db.Boolean, default=False)
    prof_medicine = db.Column(db.Boolean, default=False)
    prof_perception = db.Column(db.Boolean, default=False)
    prof_survival = db.Column(db.Boolean, default=False)
    prof_deception = db.Column(db.Boolean, default=False)
    prof_intimidation = db.Column(db.Boolean, default=False)
    prof_performance = db.Column(db.Boolean, default=False)
    prof_persuasion = db.Column(db.Boolean, default=False)

    # Saving Throw Proficiencies
    prof_strength_save = db.Column(db.Boolean, default=False)
    prof_dexterity_save = db.Column(db.Boolean, default=False)
    prof_constitution_save = db.Column(db.Boolean, default=False)
    prof_intelligence_save = db.Column(db.Boolean, default=False)
    prof_wisdom_save = db.Column(db.Boolean, default=False)
    prof_charisma_save = db.Column(db.Boolean, default=False)

    # Combat states
    death_saves_successes = db.Column(db.Integer, default=0)
    death_saves_failures = db.Column(db.Integer, default=0)

    inventory = db.Column(db.Text) # Can store JSON or delimited text
    proficiencies_armor_weapons_tools = db.Column(db.Text) # For armor, weapon, and tool proficiencies
    spells_known = db.Column(db.Text, nullable=True) # For spells known by the character
    notes = db.Column(db.Text)
    adventure_log = db.relationship('AdventureLogEntry', backref='character_owner', lazy='dynamic', order_by='AdventureLogEntry.timestamp.asc()') # type: ignore

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_hp = self.max_hp
        self.hit_dice_current = self.level # Assuming hit_dice_max is also level
        self.hit_dice_max = self.level


    def get_ability_modifier_value(self, ability_score_value: int) -> int:
        """Helper to calculate modifier from a raw score value."""
        return (ability_score_value - 10) // 2

    def get_modifier_for_ability(self, ability_name: str) -> int:
        """Calculates the modifier for a given ability score name e.g. 'strength'."""
        score = getattr(self, ability_name.lower(), 10) # Defaults to 10 if attr not found
        if score is None: # Explicitly handle if the attribute exists but is None
            score = 10
        return self.get_ability_modifier_value(score)

    # Proficiency Bonus
    def get_proficiency_bonus(self) -> int:
        """Calculates proficiency bonus based on character level according to D&D 5e rules."""
        if 1 <= self.level <= 4:
            return 2
        elif 5 <= self.level <= 8:
            return 3
        elif 9 <= self.level <= 12:
            return 4
        elif 13 <= self.level <= 16:
            return 5
        elif 17 <= self.level <= 20:
            return 6
        else:
            return 2 # Default for out-of-range levels

    @property
    def initiative_bonus(self) -> int:
        """Calculates initiative bonus from Dexterity modifier."""
        return self.get_modifier_for_ability('dexterity')

    # Skill Bonus Calculation
    _skill_to_ability_map = {
        'athletics': 'strength',
        'acrobatics': 'dexterity',
        'sleight_of_hand': 'dexterity',
        'stealth': 'dexterity',
        'arcana': 'intelligence',
        'history': 'intelligence',
        'investigation': 'intelligence',
        'nature': 'intelligence',
        'religion': 'intelligence',
        'animal_handling': 'wisdom',
        'insight': 'wisdom',
        'medicine': 'wisdom',
        'perception': 'wisdom',
        'survival': 'wisdom',
        'deception': 'charisma',
        'intimidation': 'charisma',
        'performance': 'charisma',
        'persuasion': 'charisma'
    }

    def get_skill_bonus(self, skill_name: str) -> int:
        """Calculates the total bonus for a given skill."""
        skill_name_lower = skill_name.lower().replace(" ", "_")
        if skill_name_lower not in self._skill_to_ability_map:
            raise ValueError(f"Unknown skill: {skill_name}")

        ability_name = self._skill_to_ability_map[skill_name_lower]
        ability_modifier = self.get_modifier_for_ability(ability_name)
        
        proficiency_field_name = f"prof_{skill_name_lower}"
        is_proficient = getattr(self, proficiency_field_name, False)
        
        bonus = ability_modifier
        if is_proficient:
            bonus += self.get_proficiency_bonus()
        return bonus

    # Saving Throw Bonus Calculation
    def get_saving_throw_bonus(self, ability_name: str) -> int:
        """Calculates the total bonus for a saving throw of a given ability."""
        ability_name_lower = ability_name.lower()
        if ability_name_lower not in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
            raise ValueError(f"Unknown ability for saving throw: {ability_name}")

        ability_modifier = self.get_modifier_for_ability(ability_name_lower)
        
        proficiency_field_name = f"prof_{ability_name_lower}_save"
        is_proficient = getattr(self, proficiency_field_name, False)
        
        bonus = ability_modifier
        if is_proficient:
            bonus += self.get_proficiency_bonus()
        return bonus

    # Passive Perception
    def get_passive_perception(self) -> int:
        """Calculates passive perception."""
        wisdom_modifier = self.get_modifier_for_ability('wisdom')
        perception_bonus = wisdom_modifier
        if self.prof_perception:
            perception_bonus += self.get_proficiency_bonus()
        return 10 + perception_bonus

    # Leveling Up Logic
    def can_level_up(self) -> bool:
        """Checks if the character has enough XP to level up and is not max level."""
        if self.level >= 20: # Max level
            return False
        next_level_xp_needed = XP_THRESHOLDS[self.level] # XP needed for current_level + 1
        return self.experience_points >= next_level_xp_needed

    def level_up(self) -> bool:
        """Levels up the character if they are eligible."""
        if not self.can_level_up():
            return False

        self.level += 1
        
        # Update Max HP
        class_info = CLASS_DATA_MODEL.get(self.character_class, CLASS_DATA_MODEL["Default"])
        avg_hp_gain = class_info["avg_hp_gain_per_level"]
        con_modifier = self.get_modifier_for_ability('constitution')
        hp_increase = avg_hp_gain + con_modifier
        self.max_hp += hp_increase
        
        # Restore HP to new max and add 1 hit die
        self.current_hp = self.max_hp 
        self.hit_dice_max += 1
        self.hit_dice_current +=1 # Typically gain one hit die to spend

        # Proficiency bonus is automatically updated by get_proficiency_bonus() based on new level.

        # Placeholder for Ability Score Improvements (ASIs)
        # Typical ASI levels: 4, 8, 12, 16, 19
        # if self.level in [4, 8, 12, 16, 19]:
        #     # Implement ASI logic here (e.g., allow user to choose stat increases)
        #     pass 

        # Placeholder for new class/subclass features
        # This would involve complex logic based on class and level.
        # E.g., new spells for casters, new class features.
        # if self.character_class == "Fighter" and self.level == 3:
        #     # Choose Martial Archetype
        #     pass
            
        # db.session.add(self) # No need to add, it's already in session. Caller should commit.
        return True
        
    def __repr__(self):
        return f'<Character {self.name}>'

class AdventureLogEntry(db.Model): # type: ignore
    __tablename__ = 'adventure_log_entry'
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    entry_type = db.Column(db.String(50), nullable=False) # e.g., "user_message", "gemini_response", "action_roll", "system_message"
    message = db.Column(db.Text, nullable=False)
    actor_name = db.Column(db.String(100), nullable=True) # Character name or "DM"
    roll_details = db.Column(db.Text, nullable=True) # JSON string for roll results

    def __repr__(self):
        return f'<AdventureLogEntry {self.id} for Character {self.character_id} at {self.timestamp}>'
