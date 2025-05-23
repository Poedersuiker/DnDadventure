from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db # Import db from extensions
from datetime import datetime

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
    hp = db.Column(db.Integer, default=10)
    max_hp = db.Column(db.Integer, default=10)
    armor_class = db.Column(db.Integer, default=10)
    proficiency_bonus = db.Column(db.Integer, default=2) # Default for level 1
    alignment = db.Column(db.String(50))
    background = db.Column(db.String(100))
    experience_points = db.Column(db.Integer, default=0)
    inventory = db.Column(db.Text) # Can store JSON or delimited text
    notes = db.Column(db.Text)
    adventure_log = db.relationship('AdventureLogEntry', backref='character_owner', lazy='dynamic', order_by='AdventureLogEntry.timestamp.asc()') # type: ignore

    def get_ability_modifier_value(self, ability_score_value: int) -> int:
        """Helper to calculate modifier from a raw score value."""
        return (ability_score_value - 10) // 2

    def get_modifier_for_ability(self, ability_name: str) -> int:
        """Calculates the modifier for a given ability score name e.g. 'strength'."""
        score = getattr(self, ability_name.lower(), 10) # Defaults to 10 if attr not found
        return self.get_ability_modifier_value(score)

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
