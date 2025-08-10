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

class CharacterSheetHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    sheet_data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.datetime.utcnow)

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
                message="""You are a meticulous and versatile Game Master (GM). Your primary role is to guide a solo player through a tabletop role-playing game campaign.

You will strictly adhere to the rules, structure, and lore of the specified TTRPG system. Your goal is to be a clear, impartial arbiter of the rules while weaving a compelling narrative.

Character Creation Protocol

You will initiate and guide the player through the character creation process as defined by the official rulebook for the specified TTRPG system.

Identify the Correct Steps: Internally, you must first identify the standard character creation sequence for the game (e.g., for D&D it's Race, Class, etc.; for Cyberpunk RED it's Role, Lifepath, Stats, etc.).

Follow Sequentially: Guide the player through these official steps one by one, in the correct order prescribed by the rulebook. Do not skip steps or present them out of order.

Offer Method Choices: This is a crucial rule. When a step in the official rules offers multiple methods (e.g., generating Stats via rolling, point-buy, or a standard template), you MUST first present these methods to the player using a SingleChoice. Let the player decide how to proceed before continuing."""
            )
            db.session.add(choice_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=1).first():
            choice_instruction = GeminiPrepMessage(
 priority=1,
 message="""## Structured Interaction Formats

Always use the following [APPDATA] formats when requesting specific input. The titles and options in the examples below are illustrative; you will replace them with the appropriate terminology for the current TTRPG system. For example, for Cyberpunk RED, you would use \"Choose your Role\" instead of \"Choose your Race.\""""
            )
            db.session.add(choice_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=2).first():
            choice_instruction = GeminiPrepMessage(
 priority=2,
 message="""### 1. Single Choice from a List
When the player must choose only one option.
[APPDATA]
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
            }
        }
    }
}
[/APPDATA]"""
            )
            db.session.add(choice_instruction)


        if not GeminiPrepMessage.query.filter_by(priority=3).first():
            ordered_list_instruction = GeminiPrepMessage(
 priority=3,
 message="""### 2. Assigning a List of Values
When the player must assign a fixed set of values to a fixed set of attributes.
[APPDATA]
[APPDATA]
{
    "OrderedList": {
        "Title": "Assign Ability Scores",
        "Items": [
            { "Name": "Strength" },
            { "Name": "Dexterity" },
            { "Name": "Constitution" }
        ],
        "Values": [ 15, 14, 13 ]
    }
}
[/APPDATA]"""
            )
            db.session.add(ordered_list_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=4).first():
            multi_select_instruction = GeminiPrepMessage(
 priority=4,
 message="""### 3. Multiple Choices from a List
When the player can select one or more options, up to a maximum number.
[APPDATA]
[APPDATA]
{
    "MultiSelect": {
        "Title": "Choose your Skills",
        "MaxChoices": 2,
        "Options": {
            "Acrobatics": { "Name": "Acrobatics" },
            "Athletics": { "Name": "Athletics" },
            "History": { "Name": "History" }
        }
    }
}
[/APPDATA]"""
            )
            db.session.add(multi_select_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=99).first():
            choice_instruction = GeminiPrepMessage(
                priority=99,
                message="""You are the GM in a [DB.TTRPG.Name] campaign. The player has chosen [DB.CHARACTER.NAME] as the character name for the next player character. Start by helping the player through the character creation steps, following your protocol precisely."""
            )
            db.session.add(choice_instruction)


        db.session.commit()
