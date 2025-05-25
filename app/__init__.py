from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key'  # Added secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dndadventure.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'main.login_page' # Updated as per Step 6

from .models import User
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from . import models # models is already imported above for User, keep for db registration

# Import and register blueprints
from .auth import auth_bp
app.register_blueprint(auth_bp)

from app.main import bp as main_bp # Import main blueprint
app.register_blueprint(main_bp) # Register main blueprint
