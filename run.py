import argparse # Import argparse
from app import app, db
from app.models import User, Character # Ensure models are imported

if __name__ == '__main__':
    # Ensure your database is initialized and migrations are up-to-date.
    # Run the following commands in your terminal if setting up for the first time or after model changes:
    # export FLASK_APP=run.py  (or set FLASK_APP=run.py on Windows)
    # flask db init  (only if migrations folder doesn't exist)
    # flask db migrate -m "Initial migration"
    # flask db upgrade
    #
    # To apply subsequent migrations:
    # flask db migrate -m "Description of changes"
    # flask db upgrade

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run the D&D Adventure Flask App.')
    parser.add_argument('--host', type=str, default='127.0.0.1', 
                        help='The host IP address to bind the server to (e.g., 0.0.0.0 for all interfaces)')
    
    args = parser.parse_args() # Parse arguments

    app.run(host=args.host, debug=True) # Use parsed host
