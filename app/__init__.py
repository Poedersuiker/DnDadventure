from flask import Flask
# Remove direct imports of SQLAlchemy, Migrate, LoginManager
from .config import Config
from .models import User
from .extensions import db, migrate, login_manager # Import from extensions

login_manager.login_view = 'auth.login' # type: ignore

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db) # db is now imported from extensions
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        # User is still imported from .models
        return User.query.get(int(user_id))

    # Register blueprints here
    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .character import bp as character_bp # New blueprint
    app.register_blueprint(character_bp, url_prefix='/character') # New blueprint

    return app
