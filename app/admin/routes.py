import os
import threading # Added
import uuid # Added
from flask import render_template, abort, current_app, redirect, url_for, flash, request, jsonify # Added jsonify
from flask_login import login_required, current_user
from . import admin_bp
from app.utils import list_gemini_models
from app.models import User, Setting # Add Setting import
from app import db # Add db import
# Imports for population scripts from app/scripts/
from app.scripts.populate_races import populate_races_data
from app.scripts.populate_classes import populate_classes_data
from app.scripts.populate_spells import populate_spells_data
from app.scripts.populate_weapons import populate_weapons_data

@admin_bp.route('/')
@login_required
def admin_dashboard():
    # Redirect to general settings by default
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)
    return redirect(url_for('admin.general_settings'))

@admin_bp.route('/general', methods=['GET', 'POST'])
@login_required
def general_settings():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)

    if request.method == 'POST':
        new_model = request.form.get('gemini_model')
        if new_model:
            # Validate if new_model is one of the available models to prevent arbitrary values
            available_models_check = list_gemini_models() # Potentially re-fetch or pass from a session/cache
            if new_model in available_models_check:
                try:
                    db_setting = Setting.query.filter_by(key='DEFAULT_GEMINI_MODEL').first()
                    if db_setting:
                        db_setting.value = new_model
                    else:
                        # This case should ideally be handled by app/__init__.py on startup
                        db_setting = Setting(key='DEFAULT_GEMINI_MODEL', value=new_model)
                        db.session.add(db_setting)
                    
                    db.session.commit()
                    current_app.config['DEFAULT_GEMINI_MODEL'] = new_model # Update live config
                    flash(f"Default Gemini Model updated to {new_model} and saved persistently.", 'success')
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error saving DEFAULT_GEMINI_MODEL to database: {str(e)}")
                    flash(f"Error saving setting to database: {str(e)}", 'danger')
            else:
                flash("Invalid model selected.", 'danger')
        else:
            flash("No model selected or invalid submission.", 'danger')
        return redirect(url_for('admin.general_settings'))

    # GET request
    available_models = list_gemini_models()
    current_model = current_app.config.get('DEFAULT_GEMINI_MODEL')
    return render_template('admin/general_settings.html', 
                           available_models=available_models, 
                           current_model=current_model)

@admin_bp.route('/users')
@login_required
def users_list():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)
    
    all_users = User.query.all()
    return render_template('admin/registered_users.html', users=all_users)

@admin_bp.route('/db-populate', methods=['GET'])
@login_required
def db_population_status():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)
    return render_template('admin/db_population.html')

@admin_bp.route('/db-populate/races', methods=['POST'])
@login_required
def run_populate_races():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)

    task_id = str(uuid.uuid4())
    # Ensure the root 'population_tasks' dictionary exists in extensions
    current_app.extensions.setdefault('population_tasks', {})
    # Initialize this specific task
    current_app.extensions['population_tasks'][task_id] = {
        'progress': 0,
        'status': 'Initializing race population...',
        'script': 'races', # To identify which script this task is for
        'error': False # Initialize error state
    }

    try:
        # Run populate_races_data in a separate thread
        thread = threading.Thread(target=populate_races_data, kwargs={'task_id': task_id})
        thread.start()
        # flash("Race population script started. You will be notified upon completion.", "info") # Optional flash
        return jsonify({'message': 'Race population started.', 'task_id': task_id})
    except Exception as e:
        current_app.logger.error(f"Error starting race population thread: {str(e)}")
        # Update task status to reflect error during initiation
        current_app.extensions['population_tasks'][task_id].update({
            'status': f"Error initiating population: {str(e)}",
            'error': True,
            'progress': 0 # Or some other error indication
        })
        return jsonify({'error': f"Error starting race population: {str(e)}"}), 500

@admin_bp.route('/db-populate/progress/<task_id>', methods=['GET'])
@login_required
def task_progress(task_id):
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403) # Or return jsonify({'error': 'Forbidden'}), 403

    # Safely get the task_info
    tasks_dict = current_app.extensions.get('population_tasks', {})
    task_info = tasks_dict.get(task_id)

    if not task_info:
        return jsonify({'error': 'Task not found or completed and cleared.'}), 404 # Changed message slightly

    return jsonify(task_info)

@admin_bp.route('/db-populate/classes', methods=['POST'])
@login_required
def run_populate_classes():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)

    task_id = str(uuid.uuid4())
    current_app.extensions.setdefault('population_tasks', {})
    current_app.extensions['population_tasks'][task_id] = {
        'progress': 0,
        'status': 'Initializing class population...',
        'script': 'classes',
        'error': False
    }

    try:
        thread = threading.Thread(target=populate_classes_data, kwargs={'task_id': task_id})
        thread.start()
        return jsonify({'message': 'Class population started.', 'task_id': task_id})
    except Exception as e:
        current_app.logger.error(f"Error starting class population thread: {str(e)}")
        current_app.extensions['population_tasks'][task_id].update({
            'status': f"Error initiating population: {str(e)}",
            'error': True
        })
        return jsonify({'error': f"Error starting class population: {str(e)}"}), 500

@admin_bp.route('/db-populate/spells', methods=['POST'])
@login_required
def run_populate_spells():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)

    task_id = str(uuid.uuid4())
    current_app.extensions.setdefault('population_tasks', {})
    current_app.extensions['population_tasks'][task_id] = {
        'progress': 0,
        'status': 'Initializing spell population...',
        'script': 'spells',
        'error': False
    }

    try:
        thread = threading.Thread(target=populate_spells_data, kwargs={'task_id': task_id})
        thread.start()
        return jsonify({'message': 'Spell population started.', 'task_id': task_id})
    except Exception as e:
        current_app.logger.error(f"Error starting spell population thread: {str(e)}")
        current_app.extensions['population_tasks'][task_id].update({
            'status': f"Error initiating population: {str(e)}",
            'error': True
        })
        return jsonify({'error': f"Error starting spell population: {str(e)}"}), 500

@admin_bp.route('/db-populate/weapons', methods=['POST'])
@login_required
def run_populate_weapons():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)

    task_id = str(uuid.uuid4())
    current_app.extensions.setdefault('population_tasks', {})
    current_app.extensions['population_tasks'][task_id] = {
        'progress': 0,
        'status': 'Initializing weapon population...',
        'script': 'weapons',
        'error': False
    }

    try:
        thread = threading.Thread(target=populate_weapons_data, kwargs={'task_id': task_id})
        thread.start()
        return jsonify({'message': 'Weapon population started.', 'task_id': task_id})
    except Exception as e:
        current_app.logger.error(f"Error starting weapon population thread: {str(e)}")
        current_app.extensions['population_tasks'][task_id].update({
            'status': f"Error initiating population: {str(e)}",
            'error': True
        })
        return jsonify({'error': f"Error starting weapon population: {str(e)}"}), 500

@admin_bp.route('/server-logs')
@login_required
def server_logs():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)
    
    log_content = "Log file not configured or not found."
    log_file = current_app.config.get('APP_LOG_FILE')
    if log_file and os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                log_lines = f.readlines()
                log_content = "".join(log_lines[-200:]) # Display last 200 lines
                if not log_content.strip():
                    log_content = "Log file is empty."
        except Exception as e:
            log_content = f"Error reading log file: {str(e)}"
            current_app.logger.error(f"Error reading log file: {str(e)}")
    elif not log_file:
        log_content = "APP_LOG_FILE not set in Flask config."
        current_app.logger.warning("APP_LOG_FILE not set in Flask config.")
        
    return render_template('admin/server_logging.html', log_content=log_content)

@admin_bp.route('/server-logs/clear', methods=['GET']) 
@login_required
def clear_logs():
    if not current_user.is_authenticated or current_user.email != current_app.config.get('ADMIN_EMAIL'):
        abort(403)
    
    log_file = current_app.config.get('APP_LOG_FILE')
    if log_file and os.path.exists(log_file):
        try:
            with open(log_file, 'w') as f: 
                f.write('') 
            flash("Log file cleared successfully.", "success")
            current_app.logger.info(f"Log file cleared by admin: {current_user.email}")
        except Exception as e:
            flash(f"Error clearing log file: {str(e)}", "danger")
            current_app.logger.error(f"Error clearing log file: {str(e)}")
    else:
        flash("Log file not found or not configured.", "warning")
        current_app.logger.warning("Attempt to clear log file failed: Log file not found or not configured.")
    return redirect(url_for('admin.server_logs'))
