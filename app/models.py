from flask_login import UserMixin
from app import db  # Assuming db will be initialized in app/__init__.py
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'user'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    
    characters = db.relationship('Character', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email or self.google_id}>'

class CharacterWeaponAssociation(db.Model):
    __tablename__ = 'character_weapon_association'
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), primary_key=True)
    weapon_id = db.Column(db.Integer, db.ForeignKey('weapon.id'), primary_key=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    is_equipped_main_hand = db.Column(db.Boolean, default=False, nullable=False)
    is_equipped_off_hand = db.Column(db.Boolean, default=False, nullable=False)

    character = db.relationship("Character", back_populates="weapon_associations")
    weapon = db.relationship("Weapon") # No back_populates needed on Weapon side for this simple association

    def __repr__(self):
        return f"<CharacterWeaponAssociation char_id={self.character_id} wep_id={self.weapon_id} qty={self.quantity}>"

class Character(db.Model):
    __tablename__ = 'character'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    speed = db.Column(db.Integer, default=30, nullable=False) 
    alignment = db.Column(db.String(100), nullable=True)
    dm_allowed_level = db.Column(db.Integer, default=1, nullable=False)
    current_xp = db.Column(db.Integer, default=0, nullable=False)
    background_name = db.Column(db.String(100), nullable=True)
    background_proficiencies = db.Column(db.Text, nullable=True)
    adventure_log = db.Column(db.Text, nullable=True)
    current_hit_dice = db.Column(db.Integer, default=1, nullable=False)
    player_notes = db.Column(db.Text, nullable=True)

    items = db.relationship('Item', back_populates='character', lazy=True)
    coinage = db.relationship('Coinage', back_populates='character', lazy=True)

    race = db.relationship('Race', backref='characters')
    char_class = db.relationship('Class', backref='characters')

    levels = db.relationship('CharacterLevel', backref='parent_character', lazy='dynamic', 
                             order_by='CharacterLevel.level_number', cascade='all, delete-orphan')

    weapon_associations = db.relationship(
        "CharacterWeaponAssociation",
        back_populates="character",
        cascade="all, delete-orphan",
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Character {self.name}>'

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

    def __repr__(self):
        return f'<CharacterLevel {self.level_number} for Character ID {self.character_id}>'

# Comment out old association table definition
# character_weapon_association = db.Table('character_weapon_association',
#     db.Column('id', db.Integer, primary_key=True, autoincrement=True),
#     db.Column('character_id', db.Integer, db.ForeignKey('character.id'), nullable=False),
#     db.Column('weapon_id', db.Integer, db.ForeignKey('weapon.id'), nullable=False),
#     db.Column('quantity', db.Integer, default=1),
#     db.Column('is_equipped_main_hand', db.Boolean, default=False),
#     db.Column('is_equipped_off_hand', db.Boolean, default=False),
#     db.UniqueConstraint('character_id', 'weapon_id', name='uq_character_weapon')
# )

class Weapon(db.Model):
    __tablename__ = 'weapon'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.String(50), nullable=True)
    damage_dice = db.Column(db.String(20), nullable=False)
    damage_type = db.Column(db.String(50), nullable=False)
    weight = db.Column(db.String(20), nullable=True)
    properties = db.Column(db.Text, nullable=True)
    range = db.Column(db.String(50), nullable=True)
    normal_range = db.Column(db.Integer, nullable=True)
    long_range = db.Column(db.Integer, nullable=True)
    throw_range_normal = db.Column(db.Integer, nullable=True)
    throw_range_long = db.Column(db.Integer, nullable=True)
    is_martial = db.Column(db.Boolean, default=False)

    # Omitted: character_associations = db.relationship("CharacterWeaponAssociation", back_populates="weapon")
    # This side of the relationship is not strictly needed for the current task and is implicitly handled.

    def __repr__(self):
        return f'<Weapon {self.name}>'

class Spell(db.Model):
    __tablename__ = 'spell'
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    higher_level = db.Column(db.Text, nullable=True)
    range = db.Column(db.String(100))
    components = db.Column(db.String(50))
    material = db.Column(db.Text, nullable=True)
    ritual = db.Column(db.Boolean, default=False)
    duration = db.Column(db.String(100))
    concentration = db.Column(db.Boolean, default=False)
    casting_time = db.Column(db.String(100))
    level = db.Column(db.Integer, nullable=False)
    attack_type = db.Column(db.String(100), nullable=True)
    damage_type = db.Column(db.String(50), nullable=True)
    damage_at_slot_level = db.Column(db.Text, nullable=True)
    school = db.Column(db.String(50), nullable=False)
    classes_that_can_use = db.Column(db.Text, nullable=False)
    subclasses_that_can_use = db.Column(db.Text, nullable=True)
    requires_attack_roll = db.Column(db.Boolean, default=False)
    spell_attack_ability = db.Column(db.String(20), nullable=True)

    def __repr__(self):
        return f'<Spell {self.name}>'


class Class(db.Model):
    __tablename__ = 'class'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    hit_die = db.Column(db.String(10))
    proficiencies_armor = db.Column(db.Text, nullable=True)
    proficiencies_weapons = db.Column(db.Text, nullable=True)
    proficiencies_tools = db.Column(db.Text, nullable=True)
    proficiency_saving_throws = db.Column(db.Text, nullable=False)
    skill_proficiencies_option_count = db.Column(db.Integer, nullable=False)
    skill_proficiencies_options = db.Column(db.Text, nullable=False)
    starting_equipment = db.Column(db.Text, nullable=False)
    spellcasting_ability = db.Column(db.String(20), nullable=True)
    spell_slots_by_level = db.Column(db.Text, nullable=True)
    cantrips_known_by_level = db.Column(db.Text, nullable=True)
    spells_known_by_level = db.Column(db.Text, nullable=True)
    can_prepare_spells = db.Column(db.Boolean, default=False)
    level_specific_data = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Class {self.name}>'


class Race(db.Model):
    __tablename__ = 'race'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    speed = db.Column(db.Integer, nullable=False)
    ability_score_increases = db.Column(db.Text, nullable=False)
    age_description = db.Column(db.Text, nullable=True)
    alignment_description = db.Column(db.Text, nullable=True)
    size = db.Column(db.String(20))
    size_description = db.Column(db.Text, nullable=True)
    languages = db.Column(db.Text, nullable=False)
    traits = db.Column(db.Text, nullable=True)
    skill_proficiencies = db.Column(db.Text, nullable=True)

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
    name = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)

    character = db.relationship('Character', back_populates='coinage')

    def __repr__(self):
        return f'<Coinage {self.quantity} {self.name}>'
