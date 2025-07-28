from gevent import monkey
monkey.patch_all()

import logging
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key! barbarandomkeybarchar' # It's recommended to set a secret key for production apps
socketio = SocketIO(app, async_mode='gevent') # The async_mode is important for performance

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
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handles a new client connection."""
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
    # We don't stop the thread here, it keeps sending numbers even without clients.
    # A more sophisticated approach would stop the thread when no clients are connected.

if __name__ == '__main__':
    socketio.run(app, debug=True)