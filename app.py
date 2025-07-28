import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# It's recommended to set a secret key for production apps
app.config['SECRET_KEY'] = 'your-very-secret-key! barbarandomkeybarchar'
# The async_mode is important for performance
socketio = SocketIO(app, async_mode='eventlet')

@app.route('/')
def index():
    # This would be your main chat page (e.g., index.html)
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handles a new client connection."""
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """Handles a client disconnection.""" 
    print('Client disconnected')

@socketio.on('new_message')
def handle_new_message(message):
    """Listens for a 'new_message' event from a client,
       then broadcasts it to all other clients."""
    print(f'Received message: {message}')
    # Broadcast the message to all connected clients
    emit('broadcast_message', message, broadcast=True)

if __name__ == '__main__':
    # To run: gunicorn --worker-class gevent -w 1 --bind 0.0.0.0:5000 app:app
    socketio.run(app)
