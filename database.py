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

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

class GeminiPrepMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, nullable=False)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # Add a default TTRPG type if it doesn't exist
        if not TTRPGType.query.filter_by(name='Dungeons & Dragons 5th Edition').first():
            dnd5e = TTRPGType(
                name='Dungeons & Dragons 5th Edition',
                json_template='{test}',
                html_template='<a href="test">Test</a>',
                wiki_link='https://roll20.net/compendium/dnd5e/BookIndex'
            )
            db.session.add(dnd5e)

        if not GeminiPrepMessage.query.filter_by(priority=0).first():
            choice_instruction = GeminiPrepMessage(
                priority=0,
                message="""You are the DM in a <fill selected TTRPG name> campaign. The user will be the player. Adhere to the ruleset of the given RPG system."""
            )
            db.session.add(choice_instruction)
        
        if not GeminiPrepMessage.query.filter_by(priority=1).first():
            choice_instruction = GeminiPrepMessage(
                priority=1,
                message="""When you want to give the user a choice, use the following format. Replace the values in the example with the actual values for the choice.

[APPDATA]
{
    "SingleChoice": {
        "Title": "Choose your Race",
        "Options": {
            "Human": {
                "Name": "Human",
                "Description": "Versatile and adaptable, humans are found everywhere and excel in many fields."
            },
            "Elf": {
                "Name": "Elf",
                "Description": "Graceful and long-lived, elves are attuned to magic and the natural world."
            },
            "Dwarf": {
                "Name": "Dwarf",
                "Description": "Stout and resilient, dwarves are master craftspeople and fierce warriors."
            }
        }
    }
}
[/APPDATA]"""
            )
            db.session.add(choice_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=2).first():
            choice_instruction = GeminiPrepMessage(
                priority=2,
                message="""The player has choosen <fill selected character name> as the character name for the next player character. Start by helping the player through the character creation steps."""
            )
            db.session.add(choice_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=3).first():
            ordered_list_instruction = GeminiPrepMessage(
                priority=3,
                message="""When you want the user to assign a list of values to a list of items, use the following format. Replace the values in the example with the actual values for the list.

[APPDATA]
{
    "OrderedList": {
        "Title": "Assign Ability Scores",
        "Items": [
            { "Name": "Strength" },
            { "Name": "Dexterity" },
            { "Name": "Constitution" },
            { "Name": "Intelligence" },
            { "Name": "Wisdom" },
            { "Name": "Charisma" }
        ],
        "Values": [ 15, 14, 13, 12, 10, 8 ]
    }
}
[/APPDATA]"""
            )
            db.session.add(ordered_list_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=4).first():
            multi_select_instruction = GeminiPrepMessage(
                priority=4,
                message="""When you want to give the user a choice from a list of options where multiple can be selected, use the following format. Replace the values in the example with the actual values for the choice.

[APPDATA]
{
    "MultiSelect": {
        "Title": "Choose your Skills",
        "MaxChoices": 2,
        "Options": {
            "Acrobatics": {
                "Name": "Acrobatics",
                "Description": "Your ability to stay on your feet in tricky situations."
            },
            "Athletics": {
                "Name": "Athletics",
                "Description": "Your ability to climb, jump, and swim."
            },
            "History": {
                "Name": "History",
                "Description": "Your knowledge of past events."
            }
        }
    }
}
[/APPDATA]"""
            )
            db.session.add(multi_select_instruction)

        db.session.commit()
