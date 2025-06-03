import subprocess
import datetime
import os

def get_project_root():
    """Determines the project root directory (where .git and instance/ typically are)."""
    return os.path.dirname(os.path.abspath(__file__))

def generate_build_info():
    project_root = get_project_root()
    instance_dir = os.path.join(project_root, 'instance')
    build_info_file_path = os.path.join(instance_dir, 'build_info.py')

    # Get Git branch
    git_branch = "unknown"
    try:
        git_process = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root # Ensure git command runs in project root
        )
        git_branch = git_process.stdout.strip()
    except Exception as e:
        print(f"Error getting Git branch: {e}. Defaulting to 'unknown'.")

    # Get deployment time
    deployment_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Ensure instance directory exists
    if not os.path.exists(instance_dir):
        try:
            os.makedirs(instance_dir)
            print(f"Created instance directory: {instance_dir}")
        except OSError as e:
            print(f"Error creating instance directory {instance_dir}: {e}. Please ensure the script has write permissions.")
            return False # Indicate failure

    # Write build info
    try:
        with open(build_info_file_path, 'w') as f:
            f.write(f'GIT_BRANCH = "{git_branch}"\n')
            f.write(f'DEPLOYMENT_TIME = "{deployment_time}"\n')
        print(f"Successfully wrote build information to {build_info_file_path}")
        print(f"  GIT_BRANCH='{git_branch}'")
        print(f"  DEPLOYMENT_TIME='{deployment_time}'")
        return True # Indicate success
    except IOError as e:
        print(f"Error writing to {build_info_file_path}: {e}. Please ensure the script has write permissions.")
        return False # Indicate failure

if __name__ == '__main__':
    print("Generating build information...")
    if generate_build_info():
        print("Build information generated successfully.")
    else:
        print("Failed to generate build information.")
        # Optional: exit with a non-zero status code for Jenkins
        # import sys
        # sys.exit(1)
