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
            db.session.commit()
