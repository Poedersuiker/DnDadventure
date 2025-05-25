from app import app, db
from app.models import User, Character # Ensure models are imported

def init_db():
    with app.app_context():
        # Import models here too, or ensure they are imported before db.create_all() is called
        # This is more of a failsafe if the import in app/__init__.py is not sufficient
        # for some execution paths, though typically it should be.
        # from app import models 
        db.create_all()
        print("Database initialized!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
