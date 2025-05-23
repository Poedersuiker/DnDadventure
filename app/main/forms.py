from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

class CharacterCreationForm(FlaskForm):
    name = StringField('Character Name', validators=[DataRequired()])
    race = StringField('Race')
    character_class = StringField('Class')
    submit = SubmitField('Create Character')
