from flask import Blueprint, redirect, url_for, flash
from flask_login import current_user, login_user, logout_user
from flask_dance.contrib.google import make_google_blueprint # Correct import
from flask_dance.consumer import oauth_authorized # Correct import
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage # For storing tokens if needed, though example returns False

from app import db # db instance from app package
from .models import User # User model

# Auth Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Flask-Dance Google OAuth2 Blueprint
# Client ID and Secret are no longer passed directly.
# Flask-Dance will look for GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET
# in app.config, which will be set in app/__init__.py.
google_bp = make_google_blueprint(
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
    authorized_url="/authorized" # Explicitly set the default relative callback path
)

# Register Google blueprint onto the Auth blueprint
# The final login URL might be /auth/google/login if google_bp is named 'google'
auth_bp.register_blueprint(google_bp, url_prefix='/google') # e.g. /auth/google/login

# Step 3: Implement the OAuth authorized callback function
@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        flash("Failed to log in with Google.", category="error")
        return redirect(url_for("main.index")) # Assuming a main blueprint with an index route

    resp = blueprint.session.get("https://www.googleapis.com/oauth2/v1/userinfo")
    if not resp.ok:
        msg = "Failed to fetch user info from Google."
        flash(msg, category="error")
        return redirect(url_for("main.index")) # Assuming a main blueprint with an index route

    user_info = resp.json()
    google_id = str(user_info["id"]) # 'id' is typically the user's unique Google ID
    email = user_info.get("email")

    # Find or create user in the database
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(google_id=google_id, email=email)
        db.session.add(user)
        db.session.commit()
        flash("Account created and logged in via Google.", category="success")
    else:
        flash("Logged in successfully via Google.", category="success")
    
    login_user(user)
    
    # Return False to signal that Flask-Dance should not store the token.
    # We are managing the user session with Flask-Login.
    return False


# Step 4: Implement a logout route
@auth_bp.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out.", category="info")
    return redirect(url_for("main.index")) # Assuming a main blueprint with an index route
