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
