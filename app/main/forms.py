from flask_wtf import FlaskForm
# Remove StringField, SubmitField, DataRequired if no other forms use them,
# or keep them if other forms in this file need them.
# For now, let's assume no other forms, so we can clear it out.
# If there were other forms, they would remain here.

# CharacterCreationForm has been moved to app.character.forms

# Example of another form if it existed:
# from wtforms import StringField, SubmitField
# from wtforms.validators import DataRequired
# class AnotherMainForm(FlaskForm):
#     some_field = StringField('Some Field', validators=[DataRequired()])
#     submit = SubmitField('Submit Another')
