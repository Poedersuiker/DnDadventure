from gevent import monkey
monkey.patch_all()

import logging
import time
from flask import Flask, render_template, redirect, url_for, session
from flask_socketio import SocketIO, emit
from threading import Thread
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import auth
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, init_db, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, instance_relative_config=True)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config.from_mapping(
    SECRET_KEY='your-very-secret-key! barbarandomkeybarchar',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
app.config.from_pyfile('config.py', silent=True)

# Database setup
db_type = app.config.get("DB_TYPE", "sqlite")
if db_type == "sqlite":
    db_path = app.config.get("DB_PATH", "users.db")
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

init_db(app)

socketio = SocketIO(app, async_mode='gevent')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

auth.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Background thread for sending numbers
number_thread = None
thread_stop_event = False

def send_numbers():
    count = 0
    while not thread_stop_event:
        count += 1
        logger.info(f'Emitting number: {count}')
        socketio.emit('number', count)
        time.sleep(1)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return auth.login()

@app.route('/authorize')
def authorize():
    user_info = auth.authorize()
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(google_id=google_id, email=email, name=name)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@socketio.on('connect')
def handle_connect():
    """Handles a new client connection."""
    if not current_user.is_authenticated:
        return False
    logger.info('Client connected')
    global number_thread
    global thread_stop_event
    if number_thread is None:
        thread_stop_event = False
        number_thread = Thread(target=send_numbers)
        number_thread.daemon = True
        number_thread.start()

@socketio.on('disconnect')
def handle_disconnect():
    """Handles a client disconnection."""
    logger.info('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True)