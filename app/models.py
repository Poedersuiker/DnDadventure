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
    description = db.Column(db.Text, nullable=True)  # Added a description field
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Character {self.name}>'
