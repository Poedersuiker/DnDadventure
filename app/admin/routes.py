import os # Add os import
from flask import render_template, abort, current_app, redirect, url_for, flash, request
from flask_login import login_required, current_user
from . import admin_bp
from app.utils import list_gemini_models
from app.models import User, Setting # Add Setting import
from app import db # Add db import

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
        # Handle DEFAULT_GEMINI_MODEL
        new_model = request.form.get('gemini_model')
        if new_model:
            available_models_check = list_gemini_models()
            if new_model in available_models_check:
                try:
                    db_setting = Setting.query.filter_by(key='DEFAULT_GEMINI_MODEL').first()
                    if db_setting:
                        db_setting.value = new_model
                    else:
                        db_setting = Setting(key='DEFAULT_GEMINI_MODEL', value=new_model)
                        db.session.add(db_setting)
                    current_app.config['DEFAULT_GEMINI_MODEL'] = new_model
                    flash(f"Default Gemini Model updated to {new_model}.", 'success')
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error updating DEFAULT_GEMINI_MODEL in database: {str(e)}")
                    flash(f"Error saving Gemini model setting to database: {str(e)}", 'danger')
                    return redirect(url_for('admin.general_settings')) # Early redirect on specific error
            else:
                flash("Invalid Gemini model selected.", 'danger')

        # Handle CHARACTER_CREATION_DEBUG_MODE
        debug_mode_is_on_from_form = request.form.get('character_creation_debug_mode') == 'on' # Boolean
        debug_mode_db_string = str(debug_mode_is_on_from_form) # Convert to 'True' or 'False' for DB

        try:
            debug_setting_db = Setting.query.filter_by(key='CHARACTER_CREATION_DEBUG_MODE').first()
            if debug_setting_db:
                debug_setting_db.value = debug_mode_db_string
            else:
                debug_setting_db = Setting(key='CHARACTER_CREATION_DEBUG_MODE', value=debug_mode_db_string)
                db.session.add(debug_setting_db)

            current_app.config['CHARACTER_CREATION_DEBUG_MODE'] = debug_mode_is_on_from_form # Update live config with boolean
            flash('Character Creation Debug Mode updated.', 'success')
        except Exception as e:
            db.session.rollback() # Rollback only for debug mode error if gemini model was fine
            current_app.logger.error(f"Error saving CHARACTER_CREATION_DEBUG_MODE to database: {str(e)}")
            flash(f"Error saving debug mode setting to database: {str(e)}", 'danger')
            return redirect(url_for('admin.general_settings')) # Early redirect on specific error

        try:
            db.session.commit() # Commit all changes (Gemini model and/or Debug mode)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing settings to database: {str(e)}")
            flash(f"Error committing settings to database: {str(e)}", 'danger')

        return redirect(url_for('admin.general_settings'))

    # GET request handling
    available_models = list_gemini_models()
    current_model = current_app.config.get('DEFAULT_GEMINI_MODEL')
    current_debug_mode_bool = current_app.config.get('CHARACTER_CREATION_DEBUG_MODE', True) # Expect boolean from app.config

    return render_template('admin/general_settings.html', 
                           available_models=available_models, 
                           current_model=current_model,
                           current_debug_mode=current_debug_mode_bool)

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
