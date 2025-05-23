from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db # Import db from app.extensions
from app.character import bp
from app.main.forms import CharacterCreationForm # Assuming forms are in main
from app.models import Character

@bp.route('/create_character', methods=['GET', 'POST'])
@login_required
def create_character():
    form = CharacterCreationForm()
    if form.validate_on_submit():
        character = Character(
            name=form.name.data,
            race=form.race.data,
            character_class=form.character_class.data,
            owner=current_user
        )
        db.session.add(character)
        db.session.commit()
        flash('Character created successfully!')
        return redirect(url_for('character.select_character')) # Redirect to character selection
    return render_template('character/create_character.html', title='Create Character', form=form)

@bp.route('/select_character')
@login_required
def select_character():
    characters = Character.query.filter_by(user_id=current_user.id).all() # type: ignore
    return render_template('character/select_character.html', title='Select Character', characters=characters)

@bp.route('/adventure/<int:character_id>')
@login_required
def adventure(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        # Not the owner, return 403 Forbidden
        # Alternatively, could return 404 to not reveal character existence
        return render_template('errors/403.html'), 403 # You'll need to create this template
    
    # Load adventure log entries
    log_entries = AdventureLogEntry.query.filter_by(character_id=character.id).order_by(AdventureLogEntry.timestamp.asc()).all()
    
    return render_template('character/adventure.html', title='Adventure', character=character, log_entries=log_entries)

from app.models import AdventureLogEntry # Add this import
from app.extensions import db # Add this import
import json # Add this import

@bp.route('/adventure/<int:character_id>/chat', methods=['POST'])
@login_required
def adventure_chat(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Missing message in request'}), 400

    user_input = data['message']

    # Save user's message
    user_log_entry = AdventureLogEntry(
        character_id=character.id,
        entry_type="user_message",
        message=user_input,
        actor_name=character.name
    )
    db.session.add(user_log_entry)
    
    # Retrieve chat history for Gemini context (simplified for now)
    # In a more advanced setup, you might pass structured history
    chat_history_for_gemini = AdventureLogEntry.query.filter_by(character_id=character.id).order_by(AdventureLogEntry.timestamp.asc()).all()

    from app.services.gemini_service import get_story_response
    try:
        gemini_response = get_story_response(character, user_input, chat_history_for_gemini)
    except ValueError as e: # Catch API key error specifically
        db.session.rollback() # Rollback user message if Gemini fails
        return jsonify({'reply': str(e)}), 503 # Service Unavailable
    except Exception as e: # Catch other errors from the service
        db.session.rollback()
        current_app.logger.error(f"Error in get_story_response: {e}")
        return jsonify({'reply': "An unexpected error occurred with the storyteller."}), 500

    # Save Gemini's response
    gemini_log_entry = AdventureLogEntry(
        character_id=character.id,
        entry_type="gemini_response",
        message=gemini_response,
        actor_name="DM"
    )
    db.session.add(gemini_log_entry)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database commit error in chat: {e}")
        return jsonify({'reply': "Error saving adventure progress."}), 500

    return jsonify({'reply': gemini_response})

@bp.route('/adventure/<int:character_id>/roll_action', methods=['POST'])
@login_required
def roll_action(character_id):
    character = Character.query.get_or_404(character_id)
    if character.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    if not data or 'action_type' not in data:
        return jsonify({'error': 'Missing action_type in request'}), 400

    action_type = data.get('action_type')
    stat_name = data.get('stat_name', '').lower() # e.g., 'strength', 'dexterity'
    # skill_name = data.get('skill_name', '') # e.g., 'Acrobatics' - for future use
    
    from app.utils.dice_roller import roll_dice
    roll_result = {}
    message = ""

    try:
        if action_type == "attack":
            # Simple attack roll: 1d20 + (Dex or Str modifier, let's assume Str for now or make it simple)
            # For now, let's make it a simple d20 roll without complex modifier logic from character stats
            # to keep the initial implementation straightforward.
            # A more complex implementation would check character.proficient_in_weapon, character.weapon_used etc.
            attack_modifier_from_char = character.get_modifier_for_ability('strength') # Example
            # Add proficiency bonus if it were a weapon attack the character is proficient with
            # attack_modifier_from_char += character.proficiency_bonus 
            roll_result = roll_dice(sides=20, num_dice=1, modifier=data.get('modifier_override', attack_modifier_from_char))
            message = f"{character.name} attacks! Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"

        elif action_type == "skill_check":
            if not stat_name:
                return jsonify({'error': 'Missing stat_name for skill_check'}), 400
            
            ability_modifier = character.get_modifier_for_ability(stat_name)
            # In a full system, skill proficiency might add character.proficiency_bonus
            # For a specific skill like 'Acrobatics (Dex)', you'd check if proficient in Acrobatics.
            roll_result = roll_dice(sides=20, num_dice=1, modifier=ability_modifier)
            skill_display_name = data.get('skill_name', stat_name.capitalize())
            message = f"{character.name} attempts a {skill_display_name} check. Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"

        elif action_type == "saving_throw":
            if not stat_name:
                return jsonify({'error': 'Missing stat_name for saving_throw'}), 400
            
            ability_modifier = character.get_modifier_for_ability(stat_name)
            # Proficiency in saving throws for certain classes could be added here
            # e.g. if character.class_has_strength_save_proficiency: modifier += character.proficiency_bonus
            roll_result = roll_dice(sides=20, num_dice=1, modifier=ability_modifier)
            message = f"{character.name} makes a {stat_name.capitalize()} saving throw! Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"
        
        elif action_type == "damage":
            dice_type = data.get('dice_type')
            num_dice = data.get('num_dice', 1)
            modifier = data.get('modifier', 0) # This could come from character.get_modifier_for_ability(stat_name)
            if not dice_type:
                return jsonify({'error': 'Missing dice_type for damage roll'}),400
            roll_result = roll_dice(sides=dice_type, num_dice=num_dice, modifier=modifier)
            message = f"{character.name} deals damage! Roll: {roll_result['total_with_modifier']} ({roll_result['description']})"

        else:
            return jsonify({'error': 'Invalid action_type'}), 400
        
        # Save the action roll to the log
        action_log_entry = AdventureLogEntry(
            character_id=character.id,
            entry_type="action_roll",
            message=message,
            actor_name=character.name,
            roll_details=json.dumps(roll_result)
        )
        db.session.add(action_log_entry)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Database commit error in roll_action: {e}")
            # Still return the roll result to the user, but log the DB error
            return jsonify({'message': message, 'roll_details': roll_result, 'db_error': 'Error saving action to log.'}), 500


        return jsonify({'message': message, 'roll_details': roll_result})

    except ValueError as e: # Catch errors from roll_dice or bad stat_names
        current_app.logger.error(f"Error during roll_action: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Unexpected error in roll_action: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500
