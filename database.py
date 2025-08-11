from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.sql import func
import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=True)
    characters = db.relationship('Character', backref='user', lazy=True, cascade="all, delete-orphan")

class TTRPGType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    json_template = db.Column(db.Text, nullable=False)
    html_template = db.Column(db.Text, nullable=False)
    wiki_link = db.Column(db.String(256))
    characters = db.relationship('Character', backref='ttrpg_type', lazy=True)

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ttrpg_type_id = db.Column(db.Integer, db.ForeignKey('ttrpg_type.id'), nullable=False)
    character_name = db.Column(db.String(128), nullable=False)
    charactersheet = db.Column(db.Text, nullable=False)
    messages = db.relationship('Message', backref='character', lazy=True, cascade="all, delete-orphan")
    recap = db.Column(db.Text, nullable=True)
    last_recap_message_id = db.Column(db.Integer, nullable=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

class CharacterSheetHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    sheet_data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.datetime.utcnow)

class GeminiPrepMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, nullable=False)

