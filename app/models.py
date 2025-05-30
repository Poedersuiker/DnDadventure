from flask_login import UserMixin
from app import db  # Assuming db will be initialized in app/__init__.py
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'user'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    
    # Relationship to Character model
    characters = db.relationship('Character', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email or self.google_id}>'

class Character(db.Model):
    __tablename__ = 'character'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)  # General character description
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    speed = db.Column(db.Integer, default=30, nullable=False) 
    alignment = db.Column(db.String(100), nullable=True)
    dm_allowed_level = db.Column(db.Integer, default=1, nullable=False)
    current_xp = db.Column(db.Integer, default=0, nullable=False)
    background_name = db.Column(db.String(100), nullable=True)
    background_proficiencies = db.Column(db.Text, nullable=True)  # JSON
    adventure_log = db.Column(db.Text, nullable=True) # JSON chat history
    current_hit_dice = db.Column(db.Integer, default=1, nullable=False) # Added for short rest
    player_notes = db.Column(db.Text, nullable=True) # Added for player notes

    items = db.relationship('Item', back_populates='character', lazy=True)
    coinage = db.relationship('Coinage', back_populates='character', lazy=True)

    race = db.relationship('Race', backref='characters')
    char_class = db.relationship('Class', backref='characters')

    levels = db.relationship('CharacterLevel', backref='parent_character', lazy='dynamic', 
                             order_by='CharacterLevel.level_number', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Character {self.name}>'

# New CharacterLevel Model
class CharacterLevel(db.Model):
    __tablename__ = 'character_level'
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    level_number = db.Column(db.Integer, nullable=False)
    xp_at_level_up = db.Column(db.Integer, nullable=True)
    strength = db.Column(db.Integer, nullable=False)
    dexterity = db.Column(db.Integer, nullable=False)
    constitution = db.Column(db.Integer, nullable=False)
    intelligence = db.Column(db.Integer, nullable=False)
    wisdom = db.Column(db.Integer, nullable=False)
    charisma = db.Column(db.Integer, nullable=False)
    hp = db.Column(db.Integer, nullable=False)
    max_hp = db.Column(db.Integer, nullable=False)
    hit_dice_rolled = db.Column(db.String(255), nullable=True)
    armor_class = db.Column(db.Integer, nullable=True)
    proficiencies = db.Column(db.Text, nullable=True)  # JSON
    features_gained = db.Column(db.Text, nullable=True) # JSON or Text
    spells_known_ids = db.Column(db.Text, nullable=True) # JSON list of Spell IDs
    spells_prepared_ids = db.Column(db.Text, nullable=True) # JSON list of Spell IDs
    spell_slots_snapshot = db.Column(db.Text, nullable=True) # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # The relationship back to Character is implicitly created by backref='parent_character' in Character.levels
    # If explicit definition is needed:
    # character = db.relationship('Character', backref=db.backref('level_details', lazy='joined'))

    def __repr__(self):
        return f'<CharacterLevel {self.level_number} for Character ID {self.character_id}>'

# Removed character_known_spells table
# Removed character_prepared_spells table
# Removed CharacterSpellSlot model

# Association table for Character and Weapon (Many-to-Many)
character_weapon_association = db.Table('character_weapon_association',
    db.Column('id', db.Integer, primary_key=True, autoincrement=True), # Added primary key for easier referencing if needed
    db.Column('character_id', db.Integer, db.ForeignKey('character.id'), nullable=False),
    db.Column('weapon_id', db.Integer, db.ForeignKey('weapon.id'), nullable=False),
    db.Column('quantity', db.Integer, default=1),
    db.Column('is_equipped_main_hand', db.Boolean, default=False),
    db.Column('is_equipped_off_hand', db.Boolean, default=False),
    db.UniqueConstraint('character_id', 'weapon_id', name='uq_character_weapon') # Ensure a character doesn't have multiple stacks of the exact same weapon type; they should increment quantity.
)

class Weapon(db.Model):
    __tablename__ = 'weapon'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False)  # e.g., "Simple Melee", "Martial Ranged"
    cost = db.Column(db.String(50), nullable=True)  # e.g., "5 gp"
    damage_dice = db.Column(db.String(20), nullable=False)  # e.g., "1d8", "2d6"
    damage_type = db.Column(db.String(50), nullable=False)  # e.g., "Slashing", "Piercing"
    weight = db.Column(db.String(20), nullable=True)  # e.g., "2 lb."
    properties = db.Column(db.Text, nullable=True)  # JSON string list, e.g., ["light", "finesse"]
    range = db.Column(db.String(50), nullable=True) # e.g., "5 ft." for melee, or "80/320 ft." for ranged.
    normal_range = db.Column(db.Integer, nullable=True) # Parsed normal range for ranged weapons.
    long_range = db.Column(db.Integer, nullable=True) # Parsed long range for ranged weapons.
    throw_range_normal = db.Column(db.Integer, nullable=True) # Parsed normal throw range.
    throw_range_long = db.Column(db.Integer, nullable=True) # Parsed long throw range.
    is_martial = db.Column(db.Boolean, default=False)

    # Relationship for Character-Weapon association
    # characters = db.relationship('Character', secondary=character_weapon_association, backref=db.backref('weapons', lazy='dynamic'))
    # The above is one way; another is to have it on Character model if preferred.
    # Let's define it on Character model for more direct access like character.weapons.

    def __repr__(self):
        return f'<Weapon {self.name}>'

# Add the relationship to Character model (if not already there in this form)
Character.weapons = db.relationship(
    'Weapon',
    secondary=character_weapon_association,
    back_populates='characters_associated', # New backref name for Weapon side
    lazy='dynamic' # Or 'select', 'joined' as needed
)

# Add a backref to Weapon model for the association
Weapon.characters_associated = db.relationship(
    'Character',
    secondary=character_weapon_association,
    back_populates='weapons', # Matches the relationship name in Character
    lazy='dynamic'
)


class Spell(db.Model):
    __tablename__ = 'spell'
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.String(100), unique=True, nullable=False) # from dnd5eapi
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)  # JSON list as string
    higher_level = db.Column(db.Text, nullable=True)  # JSON list as string
    range = db.Column(db.String(100))
    components = db.Column(db.String(50))  # e.g., "V, S, M"
    material = db.Column(db.Text, nullable=True)
    ritual = db.Column(db.Boolean, default=False)
    duration = db.Column(db.String(100))
    concentration = db.Column(db.Boolean, default=False)
    casting_time = db.Column(db.String(100))
    level = db.Column(db.Integer, nullable=False) # Spell level, 0 for cantrips
    attack_type = db.Column(db.String(100), nullable=True) # e.g., "melee", "ranged"
    damage_type = db.Column(db.String(50), nullable=True) # e.g., "Fire", "Cold"
    damage_at_slot_level = db.Column(db.Text, nullable=True)  # JSON dict as string
    school = db.Column(db.String(50), nullable=False) # e.g., "Evocation"
    classes_that_can_use = db.Column(db.Text, nullable=False) # JSON list of class names
    subclasses_that_can_use = db.Column(db.Text, nullable=True) # JSON list of subclass names
    requires_attack_roll = db.Column(db.Boolean, default=False)
    spell_attack_ability = db.Column(db.String(20), nullable=True) # e.g., "spellcasting", "dex", "str"


    def __repr__(self):
        return f'<Spell {self.name}>'


class Class(db.Model):
    __tablename__ = 'class'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    hit_die = db.Column(db.String(10)) # e.g., "d8"
    proficiencies_armor = db.Column(db.Text, nullable=True) # JSON list
    proficiencies_weapons = db.Column(db.Text, nullable=True) # JSON list
    proficiencies_tools = db.Column(db.Text, nullable=True) # JSON list
    proficiency_saving_throws = db.Column(db.Text, nullable=False) # JSON list, e.g., ["INT", "WIS"]
    skill_proficiencies_option_count = db.Column(db.Integer, nullable=False)
    skill_proficiencies_options = db.Column(db.Text, nullable=False) # JSON list of skill choices
    starting_equipment = db.Column(db.Text, nullable=False) # JSON structure
    spellcasting_ability = db.Column(db.String(20), nullable=True) # e.g., "WIS", "CHA"
    spell_slots_by_level = db.Column(db.Text, nullable=True) # JSON: {level: [slots]}
    cantrips_known_by_level = db.Column(db.Text, nullable=True) # JSON: {level: count}
    spells_known_by_level = db.Column(db.Text, nullable=True) # JSON: {level: count}
    can_prepare_spells = db.Column(db.Boolean, default=False) # For classes like Wizard vs Sorcerer
    level_specific_data = db.Column(db.Text, nullable=True) # JSON: {level: {"features": ["Feature Name"], "asi_count": 0/1}}

    def __repr__(self):
        return f'<Class {self.name}>'


class Race(db.Model):
    __tablename__ = 'race'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    speed = db.Column(db.Integer, nullable=False)
    ability_score_increases = db.Column(db.Text, nullable=False) # JSON: { "STR": 1, "DEX": 2 }
    age_description = db.Column(db.Text, nullable=True)
    alignment_description = db.Column(db.Text, nullable=True)
    size = db.Column(db.String(20)) # e.g., "Medium", "Small"
    size_description = db.Column(db.Text, nullable=True)
    languages = db.Column(db.Text, nullable=False) # JSON list
    traits = db.Column(db.Text, nullable=True) # JSON list of trait names/descriptions
    skill_proficiencies = db.Column(db.Text, nullable=True) # JSON list, optional choices

    def __repr__(self):
        return f'<Race {self.name}>'

class Setting(db.Model):
    __tablename__ = 'setting'
    key = db.Column(db.String(100), primary_key=True, nullable=False)
    value = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'


class Item(db.Model):
    __tablename__ = 'item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, default=1)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)

    character = db.relationship('Character', back_populates='items')

    def __repr__(self):
        return f'<Item {self.name}>'


class Coinage(db.Model):
    __tablename__ = 'coinage'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Gold", "Silver", "Copper"
    quantity = db.Column(db.Integer, default=0)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)

    character = db.relationship('Character', back_populates='coinage')

    def __repr__(self):
        return f'<Coinage {self.quantity} {self.name}>'
