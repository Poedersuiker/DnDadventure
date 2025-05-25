import argparse # Import argparse
from app import app, db
from app.models import User, Character # Ensure models are imported

def init_db():
    with app.app_context():
        db.create_all()
        print("Database initialized!")

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run the D&D Adventure Flask App.')
    parser.add_argument('--host', type=str, default='127.0.0.1', 
                        help='The host IP address to bind the server to (e.g., 0.0.0.0 for all interfaces)')
    
    args = parser.parse_args() # Parse arguments

    init_db()
    app.run(host=args.host, debug=True) # Use parsed host
