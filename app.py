from gevent import monkey
monkey.patch_all()

import logging
import time
from flask import Flask, render_template, redirect, url_for, session
from flask_socketio import SocketIO, emit
from threading import Thread
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import auth
from flask_sqlalchemy import SQLAlchemy
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY='your-very-secret-key! barbarandomkeybarchar',
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'users.db'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
app.config.from_pyfile('config.py', silent=True)


db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='gevent')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

auth.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=True)

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

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, debug=True)