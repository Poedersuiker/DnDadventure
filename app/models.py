from flask_login import UserMixin
from app import db  # Assuming db will be initialized in app/__init__.py

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
    level = db.Column(db.Integer, default=1)
    strength = db.Column(db.Integer, default=10)
    dexterity = db.Column(db.Integer, default=10)
    constitution = db.Column(db.Integer, default=10)
    intelligence = db.Column(db.Integer, default=10)
    wisdom = db.Column(db.Integer, default=10)
    charisma = db.Column(db.Integer, default=10)
    hp = db.Column(db.Integer, default=0)
    max_hp = db.Column(db.Integer, default=0)
    armor_class = db.Column(db.Integer, default=10)
    current_proficiencies = db.Column(db.Text, nullable=True)  # JSON
    current_equipment = db.Column(db.Text, nullable=True)  # JSON
    alignment = db.Column(db.String(100), nullable=True)
    background_name = db.Column(db.String(100), nullable=True)
    background_proficiencies = db.Column(db.Text, nullable=True)  # JSON
    background_equipment = db.Column(db.Text, nullable=True)  # JSON

    race = db.relationship('Race', backref='characters')
    char_class = db.relationship('Class', backref='characters')

    known_spells = db.relationship('Spell', secondary='character_known_spells', lazy='subquery',
                                   backref=db.backref('characters_that_know', lazy=True))
    prepared_spells = db.relationship('Spell', secondary='character_prepared_spells', lazy='subquery',
                                      backref=db.backref('characters_that_prepare', lazy=True))

    def __repr__(self):
        return f'<Character {self.name}>'


# Association table for Character and known Spells (Many-to-Many)
character_known_spells = db.Table('character_known_spells',
    db.Column('character_id', db.Integer, db.ForeignKey('character.id'), primary_key=True),
    db.Column('spell_id', db.Integer, db.ForeignKey('spell.id'), primary_key=True)
)

# Association table for Character and prepared Spells (Many-to-Many)
character_prepared_spells = db.Table('character_prepared_spells',
    db.Column('character_id', db.Integer, db.ForeignKey('character.id'), primary_key=True),
    db.Column('spell_id', db.Integer, db.ForeignKey('spell.id'), primary_key=True)
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
