from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, NumberRange

# Define choices for D&D 5e races and classes
RACE_CHOICES = [
    ("Human", "Human"), 
    ("Elf", "Elf"), 
    ("Dwarf", "Dwarf"), 
    ("Halfling", "Halfling"), 
    ("Dragonborn", "Dragonborn"), 
    ("Gnome", "Gnome"), 
    ("Half-Elf", "Half-Elf"), 
    ("Half-Orc", "Half-Orc"), 
    ("Tiefling", "Tiefling")
]

CLASS_CHOICES = [
    ("Artificer", "Artificer"),
    ("Barbarian", "Barbarian"), 
    ("Bard", "Bard"), 
    ("Cleric", "Cleric"), 
    ("Druid", "Druid"), 
    ("Fighter", "Fighter"), 
    ("Monk", "Monk"), 
    ("Paladin", "Paladin"), 
    ("Ranger", "Ranger"), 
    ("Rogue", "Rogue"), 
    ("Sorcerer", "Sorcerer"), 
    ("Warlock", "Warlock"), 
    ("Wizard", "Wizard")
]

class CharacterCreationForm(FlaskForm):
    name = StringField('Character Name', validators=[DataRequired()])
    race = SelectField('Race', choices=RACE_CHOICES, validators=[DataRequired()])
    character_class = SelectField('Class', choices=CLASS_CHOICES, validators=[DataRequired()])
    strength = IntegerField('Strength', default=10, validators=[DataRequired(), NumberRange(min=3, max=20)])
    dexterity = IntegerField('Dexterity', default=10, validators=[DataRequired(), NumberRange(min=3, max=20)])
    constitution = IntegerField('Constitution', default=10, validators=[DataRequired(), NumberRange(min=3, max=20)])
    intelligence = IntegerField('Intelligence', default=10, validators=[DataRequired(), NumberRange(min=3, max=20)])
    wisdom = IntegerField('Wisdom', default=10, validators=[DataRequired(), NumberRange(min=3, max=20)])
    charisma = IntegerField('Charisma', default=10, validators=[DataRequired(), NumberRange(min=3, max=20)])
    spells_known = TextAreaField('Spells Known')
    submit = SubmitField('Create Character')
