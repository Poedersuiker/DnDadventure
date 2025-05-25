from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Character
from app.main import bp # Import the blueprint 'bp' from app.main package

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    characters = Character.query.filter_by(user_id=current_user.id).all()
    return render_template('main.html', characters=characters)

@bp.route('/login_page')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('login.html')

@bp.route('/create_character', methods=['GET', 'POST'])
@login_required
def create_character():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Character name is required.', 'error')
            return render_template('create_character.html')

        new_character = Character(name=name, description=description, user_id=current_user.id)
        db.session.add(new_character)
        db.session.commit()
        flash('Character created successfully!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('create_character.html')

@bp.route('/delete_character/<int:character_id>', methods=['POST'])
@login_required
def delete_character(character_id):
    character = Character.query.get_or_404(character_id) # Use get_or_404 for convenience
    
    if character.user_id != current_user.id:
        flash('You do not have permission to delete this character.', 'error')
        # Or abort(403)
        return redirect(url_for('main.index'))
        
    db.session.delete(character)
    db.session.commit()
    flash('Character deleted successfully.', 'success')
    return redirect(url_for('main.index'))
