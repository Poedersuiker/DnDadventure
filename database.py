from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=True)
    characters = db.relationship('Character', backref='user', lazy=True)

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
                message="""When you want to give the user a choice, use the following format: [APPDATA]{ "SingleChoice": { "Title": { "Option1": { "Name": "Option1", "Description": "Description of Option 1" }, "Option2": { "Name": "Option2", "Description": "Description of Option 2" } } } }[/APPDATA]"""
            )
            db.session.add(choice_instruction)

        if not GeminiPrepMessage.query.filter_by(priority=2).first():
            choice_instruction = GeminiPrepMessage(
                priority=2,
                message="""The player has choosen <fill selected character name> as the character name for the next player character. Start by helping the player through the character creation steps."""
            )
            db.session.add(choice_instruction)

        db.session.commit()
