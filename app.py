from gevent import monkey
monkey.patch_all()

import logging
import os
import google.generativeai as genai
from flask import Flask
from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, User
import auth
from cli import register_cli_commands
from routes.main_routes import main_bp
from routes.admin_routes import admin_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App Initialization
app = Flask(__name__, instance_relative_config=True)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configuration
app.config.from_mapping(
    SECRET_KEY='your-very-secret-key! barbarandomkeybarchar',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    GEMINI_MODEL='gemini-1.5-pro-latest',
    GEMINI_DEBUG=False
)
app.config.from_pyfile('config.py', silent=True)

# Gemini API Key
gemini_api_key = app.config.get('GEMINI_API_KEY')
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

# Database setup
db_type = app.config.get("DB_TYPE", "sqlite")
if db_type == "sqlite":
    db_path = app.config.get("DB_PATH", "database.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, db_path)
elif db_type in ["mysql", "postgresql"]:
    db_user = app.config.get("DB_USER")
    db_password = app.config.get("DB_PASSWORD")
    db_host = app.config.get("DB_HOST")
    db_port = app.config.get("DB_PORT")
    db_name = app.config.get("DB_NAME")
    if db_type == "mysql":
        app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else: # postgresql
        app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

db.init_app(app)
migrate = Migrate(app, db)

# SocketIO
socketio = SocketIO(app, async_mode='gevent')

# Login Manager
login_manager = LoginManager(app)
login_manager.login_view = 'main.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Auth
auth.init_app(app)

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)

# Register CLI commands
register_cli_commands(app)

# Import and register socket.io handlers
from socketio_handlers import register_socketio_handlers
register_socketio_handlers(socketio)

if __name__ == '__main__':
    socketio.run(app, debug=True)
