from flask import render_template, redirect, url_for, flash # Added flash import
from flask_login import login_required, current_user
from app.main import bp
from app.auth.forms import CSRFTestForm # Added CSRFTestForm import

@bp.route('/')
@bp.route('/index') # Keep /index for now, can be removed later if not needed
def index():
    if current_user.is_authenticated:
        # User is logged in, check if they have characters
        if current_user.characters.first(): # type: ignore
            return redirect(url_for('character.select_character'))
        else:
            # No characters, redirect to creation or show a message
            return redirect(url_for('character.create_character')) # Or a different page
    # User is not logged in, show public page or redirect to login
    # For now, let's redirect to login as an example
    return redirect(url_for('auth.login'))
    # If you have a public landing page:
    # return render_template('main/public_index.html', title='Welcome')

# Example of a protected route that might have been the old index
@bp.route('/dashboard') # A new route for the old index content perhaps
@login_required
def dashboard():
    # This could be the page that 'main/index.html' was rendering
    # Or it could be a new dashboard specific to logged-in users
    # For now, let's assume it renders the old main/index.html content
    return render_template('main/index.html', title='Dashboard')

@bp.route('/test_csrf', methods=['GET', 'POST'])
def test_csrf():
    form = CSRFTestForm()
    if form.validate_on_submit():
        flash('CSRF form submitted successfully (test).')
        return redirect(url_for('main.index'))
    return render_template('main/test_csrf_form.html', form=form, title='Test CSRF')
