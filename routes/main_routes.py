from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify, current_app
from flask_login import login_user, logout_user, current_user, login_required
from database import db, User, Character, TTRPGType
import auth
from bot.character_utils import get_recap as get_recap_util

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    admin_email = current_app.config.get('ADMIN_EMAIL')
    characters = Character.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', admin_email=admin_email, characters=characters)

@main_bp.route('/login')
def login():
    return auth.login()

@main_bp.route('/authorize')
def authorize():
    user_info = auth.authorize()
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(google_id=google_id, email=email, name=name)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for('main.index'))

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('main.login'))

@main_bp.route('/new_character', methods=['GET', 'POST'])
@login_required
def new_character():
    if request.method == 'POST':
        character_name = request.form.get('character_name')
        ttrpg_type_id = request.form.get('ttrpg_type')
        ttrpg_type = TTRPGType.query.get(ttrpg_type_id)
        new_char = Character(
            user_id=current_user.id,
            ttrpg_type_id=ttrpg_type_id,
            character_name=character_name,
            charactersheet=ttrpg_type.json_template
        )
        db.session.add(new_char)
        db.session.commit()
        return redirect(url_for('main.index', new_char_id=new_char.id))
    ttrpg_types = TTRPGType.query.all()
    return render_template('new_character.html', ttrpg_types=ttrpg_types)

@main_bp.route('/delete_character/<int:character_id>', methods=['DELETE'])
@login_required
def delete_character(character_id):
    character = Character.query.get(character_id)
    if character and character.user_id == current_user.id:
        db.session.delete(character)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Character not found or unauthorized'}), 404

@main_bp.route('/recap/<int:character_id>')
@login_required
def get_recap(character_id):
    character = Character.query.get(character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    recap_data = get_recap_util(character_id)
    return jsonify(recap_data)
