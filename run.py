import argparse
import sys # For sys.exit
from sqlalchemy.exc import OperationalError
from app import app, db
from app.models import User, Setting # Changed Character to Setting as it's more fundamental for app init

def check_database_readiness(current_app, current_db):
    """
    Checks if the database is initialized and essential tables exist.
    Exits the application if the database is not ready.
    """
    with current_app.app_context():
        try:
            # Try to query an essential table. The 'setting' table is checked during app init.
            # Alternatively, checking for 'alembic_version' indicates migrations have run.
            # current_db.session.query(Setting).first()
            # More direct check for alembic_version table:
            if not current_db.engine.dialect.has_table(current_db.engine.connect(), 'alembic_version'):
                 # Simulating an OperationalError if alembic_version doesn't exist,
                 # as has_table itself doesn't raise it.
                 raise OperationalError("Alembic version table not found, migrations likely not applied.", "", "")

            # If Setting table query is preferred and it's essential for startup before this check:
            # current_db.session.query(Setting).first()
            # If the above doesn't raise an error, it implies tables exist.

        except OperationalError:
            print("**********************************************************************", file=sys.stderr)
            print("ERROR: Database tables not found or schema is not up-to-date.", file=sys.stderr)
            print("The application cannot start without a valid database.", file=sys.stderr)
            print("", file=sys.stderr)
            print("Please initialize or upgrade your database by running the following commands in your terminal:", file=sys.stderr)
            print("1. export FLASK_APP=run.py  (or 'set FLASK_APP=run.py' on Windows)", file=sys.stderr)
            print("2. flask db upgrade", file=sys.stderr)
            print("", file=sys.stderr)
            print("If this is the very first time setting up, you might also need:", file=sys.stderr)
            print(" - flask db init  (only if 'migrations' folder doesn't exist)", file=sys.stderr)
            print(" - flask db migrate -m \"Initial setup\" (to create the first migration if none exist)", file=sys.stderr)
            print("   (then run 'flask db upgrade')", file=sys.stderr)
            print("", file=sys.stderr)
            print("After running these commands, restart the application.", file=sys.stderr)
            print("**********************************************************************", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred during database readiness check: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    # Perform database readiness check before attempting to run the app
    check_database_readiness(app, db)

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run the D&D Adventure Flask App.')
    parser.add_argument('--host', type=str, default='127.0.0.1', 
                        help='The host IP address to bind the server to (e.g., 0.0.0.0 for all interfaces)')
    
    args = parser.parse_args() # Parse arguments

    app.run(host=args.host, debug=True) # Use parsed host
