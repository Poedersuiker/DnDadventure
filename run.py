import argparse # Import argparse
import subprocess
import datetime
import os
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

    # Get Git branch
    try:
        git_branch_process = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        git_branch = git_branch_process.stdout.strip()
    except Exception:
        git_branch = "unknown"

    # Get deployment time
    deployment_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Ensure instance directory exists
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)

    # Write build info
    build_info_path = os.path.join(instance_dir, 'build_info.py')
    with open(build_info_path, 'w') as f:
        f.write(f'GIT_BRANCH = "{git_branch}"\n')
        f.write(f'DEPLOYMENT_TIME = "{deployment_time}"\n')

    init_db()
    app.run(host=args.host, debug=True) # Use parsed host
