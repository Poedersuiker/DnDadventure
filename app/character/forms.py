from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, SubmitField, IntegerField, TextAreaField, BooleanField, widgets
from wtforms.validators import DataRequired, NumberRange, Length

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

class RaceSelectionForm(FlaskForm):
    race = SelectField('Choose your Race', choices=RACE_CHOICES, validators=[DataRequired()])
    submit = SubmitField('Next Step') # For completeness, though wizard template might handle button

class ClassSelectionForm(FlaskForm):
    character_class = SelectField('Choose your Class', choices=CLASS_CHOICES, validators=[DataRequired()])
    submit = SubmitField('Next Step') # For completeness

class AbilityScoreAssignmentForm(FlaskForm):
    strength = IntegerField('Strength', validators=[DataRequired(), NumberRange(min=3, max=18, message="Scores must be between 3 and 18 before racial modifiers.")])
    dexterity = IntegerField('Dexterity', validators=[DataRequired(), NumberRange(min=3, max=18, message="Scores must be between 3 and 18 before racial modifiers.")])
    constitution = IntegerField('Constitution', validators=[DataRequired(), NumberRange(min=3, max=18, message="Scores must be between 3 and 18 before racial modifiers.")])
    intelligence = IntegerField('Intelligence', validators=[DataRequired(), NumberRange(min=3, max=18, message="Scores must be between 3 and 18 before racial modifiers.")])
    wisdom = IntegerField('Wisdom', validators=[DataRequired(), NumberRange(min=3, max=18, message="Scores must be between 3 and 18 before racial modifiers.")])
    charisma = IntegerField('Charisma', validators=[DataRequired(), NumberRange(min=3, max=18, message="Scores must be between 3 and 18 before racial modifiers.")])
    # submit = SubmitField('Next Step') # Submit is handled by the main wizard template

# This form might not be strictly necessary if using direct action buttons,
# but can be useful for structure or if more complex generation options are added.
class AbilityGenerationMethodForm(FlaskForm):
    # Example: could have a SelectField for method if not using buttons
    # For now, just a hidden field to demonstrate structure, though POST actions will likely be distinct.
    method_choice = SelectField('Generation Method', choices=[('roll', 'Roll 4d6 drop lowest'), ('standard_array', 'Use Standard Array')])
    submit = SubmitField('Choose Method')

ALIGNMENT_CHOICES = [
    ('LG', 'Lawful Good'), ('NG', 'Neutral Good'), ('CG', 'Chaotic Good'),
    ('LN', 'Lawful Neutral'), ('N', 'True Neutral'), ('CN', 'Chaotic Neutral'),
    ('LE', 'Lawful Evil'), ('NE', 'Neutral Evil'), ('CE', 'Chaotic Evil')
]

class BackgroundAlignmentForm(FlaskForm):
    alignment = SelectField('Alignment', choices=ALIGNMENT_CHOICES, validators=[DataRequired()])
    background = StringField('Background', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Next Step') # For completeness

ALL_SKILLS = [
    ('prof_athletics', 'Athletics (Str)'), ('prof_acrobatics', 'Acrobatics (Dex)'),
    ('prof_sleight_of_hand', 'Sleight of Hand (Dex)'), ('prof_stealth', 'Stealth (Dex)'),
    ('prof_arcana', 'Arcana (Int)'), ('prof_history', 'History (Int)'),
    ('prof_investigation', 'Investigation (Int)'), ('prof_nature', 'Nature (Int)'),
    ('prof_religion', 'Religion (Int)'), ('prof_animal_handling', 'Animal Handling (Wis)'),
    ('prof_insight', 'Insight (Wis)'), ('prof_medicine', 'Medicine (Wis)'),
    ('prof_perception', 'Perception (Wis)'), ('prof_survival', 'Survival (Wis)'),
    ('prof_deception', 'Deception (Cha)'), ('prof_intimidation', 'Intimidation (Cha)'),
    ('prof_performance', 'Performance (Cha)'), ('prof_persuasion', 'Persuasion (Cha)')
]

# Skill Proficiencies Form
class SkillsProficienciesForm(FlaskForm):
    prof_athletics = BooleanField('Athletics (Str)', default=False)
    prof_acrobatics = BooleanField('Acrobatics (Dex)', default=False)
    prof_sleight_of_hand = BooleanField('Sleight of Hand (Dex)', default=False)
    prof_stealth = BooleanField('Stealth (Dex)', default=False)
    prof_arcana = BooleanField('Arcana (Int)', default=False)
    prof_history = BooleanField('History (Int)', default=False)
    prof_investigation = BooleanField('Investigation (Int)', default=False)
    prof_nature = BooleanField('Nature (Int)', default=False)
    prof_religion = BooleanField('Religion (Int)', default=False)
    prof_animal_handling = BooleanField('Animal Handling (Wis)', default=False)
    prof_insight = BooleanField('Insight (Wis)', default=False)
    prof_medicine = BooleanField('Medicine (Wis)', default=False)
    prof_perception = BooleanField('Perception (Wis)', default=False)
    prof_survival = BooleanField('Survival (Wis)', default=False)
    prof_deception = BooleanField('Deception (Cha)', default=False)
    prof_intimidation = BooleanField('Intimidation (Cha)', default=False)
    prof_performance = BooleanField('Performance (Cha)', default=False)
    prof_persuasion = BooleanField('Persuasion (Cha)', default=False)
    submit = SubmitField('Next Step')

class EquipmentForm(FlaskForm):
    inventory = TextAreaField('Equipment and Inventory', 
                              validators=[Length(max=1000, message="Inventory text cannot exceed 1000 characters.")],
                              render_kw={"rows": 10, "cols": 50})
    submit = SubmitField('Next Step')

class SpellSelectionForm(FlaskForm):
    selected_cantrips = SelectMultipleField(
        'Choose Cantrips', 
        choices=[], 
        coerce=str, 
        widget=widgets.ListWidget(prefix_label=False), 
        option_widget=widgets.CheckboxInput()
    )
    selected_level1_spells = SelectMultipleField(
        'Choose 1st Level Spells', 
        choices=[], 
        coerce=str, 
        widget=widgets.ListWidget(prefix_label=False), 
        option_widget=widgets.CheckboxInput()
    )
    submit = SubmitField('Next Step')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'cantrip_choices' in kwargs:
            self.selected_cantrips.choices = kwargs['cantrip_choices']
        if 'level1_spell_choices' in kwargs:
            self.selected_level1_spells.choices = kwargs['level1_spell_choices']
