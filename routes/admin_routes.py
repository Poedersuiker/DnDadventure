import os
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from flask_login import current_user, login_required
from database import db, TTRPGType, GeminiPrepMessage
import google.generativeai as genai

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    """Admin page to select the Gemini model."""
    if current_user.email != current_app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    if request.method == 'POST':
        if request.form.get('form_type') == 'add_ttrpg':
            ttrpg_name = request.form.get('ttrpg_name')
            json_template = request.form.get('json_template')
            html_template = request.form.get('html_template')
            wiki_link = request.form.get('wiki_link')
            new_ttrpg_type = TTRPGType(
                name=ttrpg_name,
                json_template=json_template,
                html_template=html_template,
                wiki_link=wiki_link
            )
            db.session.add(new_ttrpg_type)
            db.session.commit()
        else:
            config_path = os.path.join(current_app.instance_path, 'config.py')

            new_model = request.form.get('model')
            new_debug_status = 'gemini_debug' in request.form

            config_lines = []
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_lines = f.readlines()

            updated_keys = {'GEMINI_MODEL', 'GEMINI_DEBUG'}
            new_config_lines = []
            keys_found = set()

            for line in config_lines:
                stripped_line = line.strip()
                key_found_on_line = False
                if not stripped_line or stripped_line.startswith('#'):
                    new_config_lines.append(line)
                    continue

                for key in updated_keys:
                    if stripped_line.startswith(key + ' '):
                        if key == 'GEMINI_MODEL':
                            new_config_lines.append(f"GEMINI_MODEL = '{new_model}'\\n")
                        elif key == 'GEMINI_DEBUG':
                            new_config_lines.append(f"GEMINI_DEBUG = {new_debug_status}\\n")
                        keys_found.add(key)
                        key_found_on_line = True
                        break
                if not key_found_on_line:
                    new_config_lines.append(line)

            if 'GEMINI_MODEL' not in keys_found:
                new_config_lines.append(f"GEMINI_MODEL = '{new_model}'\\n")
            if 'GEMINI_DEBUG' not in keys_found:
                new_config_lines.append(f"GEMINI_DEBUG = {new_debug_status}\\n")

            with open(config_path, 'w') as f:
                f.writelines(new_config_lines)

            current_app.config.from_pyfile('config.py', silent=True)

        return redirect(url_for('admin.admin'))

    models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    ttrpg_types = TTRPGType.query.all()
    gemini_model = current_app.config.get('GEMINI_MODEL')
    gemini_debug = current_app.config.get('GEMINI_DEBUG', False)
    return render_template('admin.html', models=models, selected_model=gemini_model, gemini_debug=gemini_debug, ttrpg_types=ttrpg_types)

@admin_bp.route('/admin/ttrpg_data', methods=['GET', 'POST', 'DELETE', 'PUT'])
@login_required
def ttrpg_data():
    if current_user.email != current_app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    if request.method == 'GET':
        ttrpg_types = TTRPGType.query.all()
        return jsonify([
            {
                'id': t.id,
                'name': t.name,
                'json_template': t.json_template,
                'html_template': t.html_template,
                'wiki_link': t.wiki_link
            } for t in ttrpg_types
        ])

    if request.method == 'POST':
        data = request.get_json()
        ttrpg_type = TTRPGType.query.get(data['id'])
        if ttrpg_type:
            ttrpg_type.name = data['name']
            ttrpg_type.json_template = data['json_template']
            ttrpg_type.html_template = data['html_template']
            ttrpg_type.wiki_link = data['wiki_link']
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'TTRPG type not found'})

    if request.method == 'PUT':
        data = request.get_json()
        new_ttrpg_type = TTRPGType(
            name=data['name'],
            json_template=data['json_template'],
            html_template=data['html_template'],
            wiki_link=data['wiki_link']
        )
        db.session.add(new_ttrpg_type)
        db.session.commit()
        return jsonify({'success': True})

    if request.method == 'DELETE':
        data = request.get_json()
        ttrpg_type = TTRPGType.query.get(data['id'])
        if ttrpg_type:
            db.session.delete(ttrpg_type)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'TTRPG type not found'})

@admin_bp.route('/admin/gemini_prep_data', methods=['GET', 'POST', 'DELETE', 'PUT'])
@login_required
def gemini_prep_data():
    if current_user.email != current_app.config.get('ADMIN_EMAIL'):
        return "Unauthorized", 401

    if request.method == 'GET':
        messages = GeminiPrepMessage.query.order_by(GeminiPrepMessage.priority).all()
        return jsonify([
            {
                'id': m.id,
                'message': m.message,
                'priority': m.priority
            } for m in messages
        ])

    if request.method == 'POST':
        data = request.get_json()
        message = GeminiPrepMessage.query.get(data['id'])
        if message:
            message.message = data['message']
            message.priority = data['priority']
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Message not found'})

    if request.method == 'PUT':
        data = request.get_json()
        new_message = GeminiPrepMessage(
            message=data['message'],
            priority=data['priority']
        )
        db.session.add(new_message)
        db.session.commit()
        return jsonify({'success': True})

    if request.method == 'DELETE':
        data = request.get_json()
        message = GeminiPrepMessage.query.get(data['id'])
        if message:
            db.session.delete(message)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Message not found'})
