from authlib.integrations.flask_client import OAuth
from flask import url_for, session
import os
import secrets

oauth = OAuth()

def init_app(app):
    """Initializes the OAuth provider."""
    oauth.init_app(app)

    # Register Google OAuth provider
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

def login():
    """Redirects to Google's authorization page."""
    redirect_uri = url_for('main.authorize', _external=True)
    nonce = secrets.token_urlsafe(16)
    session['nonce'] = nonce
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)

def authorize():
    """Handles the callback from Google."""
    token = oauth.google.authorize_access_token()
    nonce = session.pop('nonce', None)
    user_info = oauth.google.parse_id_token(token, nonce=nonce)
    session['user'] = user_info
    return user_info
