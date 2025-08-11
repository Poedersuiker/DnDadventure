import click
from flask.cli import with_appcontext
from database import db, TTRPGType, GeminiPrepMessage

@click.command("seed-data")
@with_appcontext
def seed_data():
    """Seeds the database with initial data."""
    # Add a default TTRPG type if it doesn't exist
    if not TTRPGType.query.filter_by(name='Dungeons & Dragons 5th Edition').first():
        dnd5e = TTRPGType(
            name='Dungeons & Dragons 5th Edition',
            json_template='{"name": "", "level": ""}',
            html_template='<table><tr><th>Name</th><td id="name"></td></tr><tr><th>Level</th><td id="level"></td></tr></table>',
            wiki_link='https://roll20.net/compendium/dnd5e/BookIndex'
        )
        db.session.add(dnd5e)
        print("Seeded D&D 5e TTRPG type.")

    if not GeminiPrepMessage.query.filter_by(priority=0).first():
        choice_instruction = GeminiPrepMessage(
            priority=0,
            message="""You are a meticulous and versatile Game Master (GM). Your primary role is to guide a solo player through a tabletop role-playing game campaign.

You will strictly adhere to the rules, structure, and lore of the specified TTRPG system. Your goal is to be a clear, impartial arbiter of the rules while weaving a compelling narrative.

Character Creation Protocol

You will initiate and guide the player through the character creation process as defined by the official rulebook for the specified TTRPG system.

Identify the Correct Steps: Internally, you must first identify the standard character creation sequence for the game (e.g., for D&D it's Race, Class, etc.; for Cyberpunk RED it's Role, Lifepath, Stats, etc.).

Follow Sequentially: Guide the player through these official steps one by one, in the correct order prescribed by the rulebook. Do not skip steps or present them out of order.

Offer Method Choices: This is a crucial rule. When a step in the official rules offers multiple methods (e.g., generating Stats via rolling, point-buy, or a standard template), you MUST first present these methods to the player using a SingleChoice. Let the player decide how to proceed before continuing."""
        )
        db.session.add(choice_instruction)
        print("Seeded Gemini prep message priority 0.")

    if not GeminiPrepMessage.query.filter_by(priority=1).first():
        choice_instruction = GeminiPrepMessage(
            priority=1,
            message="""## Structured Interaction Formats

Always use the following [APPDATA] formats when requesting specific input. The titles and options in the examples below are illustrative; you will replace them with the appropriate terminology for the current TTRPG system. For example, for Cyberpunk RED, you would use \"Choose your Role\" instead of \"Choose your Race.\""""
        )
        db.session.add(choice_instruction)
        print("Seeded Gemini prep message priority 1.")

    if not GeminiPrepMessage.query.filter_by(priority=2).first():
        choice_instruction = GeminiPrepMessage(
            priority=2,
            message="""### 1. Single Choice from a List
When the player must choose only one option.
[APPDATA]
[APPDATA]
{
    "SingleChoice": {
        "Title": "Choose your Race",
        "Options": {
            "Human": {
                "Name": "Human",
                "Description": "Versatile and adaptable, humans are found everywhere and excel in many fields."
            },
            "Elf": {
                "Name": "Elf",
                "Description": "Graceful and long-lived, elves are attuned to magic and the natural world."
            }
        }
    }
}
[/APPDATA]"""
        )
        db.session.add(choice_instruction)
        print("Seeded Gemini prep message priority 2.")

    if not GeminiPrepMessage.query.filter_by(priority=3).first():
        ordered_list_instruction = GeminiPrepMessage(
            priority=3,
            message="""### 2. Assigning a List of Values
When the player must assign a fixed set of values to a fixed set of attributes.
[APPDATA]
[APPDATA]
{
    "OrderedList": {
        "Title": "Assign Ability Scores",
        "Items": [
            { "Name": "Strength" },
            { "Name": "Dexterity" },
            { "Name": "Constitution" }
        ],
        "Values": [ 15, 14, 13 ]
    }
}
[/APPDATA]"""
        )
        db.session.add(ordered_list_instruction)
        print("Seeded Gemini prep message priority 3.")

    if not GeminiPrepMessage.query.filter_by(priority=4).first():
        multi_select_instruction = GeminiPrepMessage(
            priority=4,
            message="""### 3. Multiple Choices from a List
When the player can select one or more options, up to a maximum number.
[APPDATA]
[APPDATA]
{
    "MultiSelect": {
        "Title": "Choose your Skills",
        "MaxChoices": 2,
        "Options": {
            "Acrobatics": { "Name": "Acrobatics" },
            "Athletics": { "Name": "Athletics" },
            "History": { "Name": "History" }
        }
    }
}
[/APPDATA]"""
        )
        db.session.add(multi_select_instruction)
        print("Seeded Gemini prep message priority 4.")

    character_sheet_instruction = GeminiPrepMessage.query.filter_by(priority=98).first()
    if not character_sheet_instruction:
        character_sheet_instruction = GeminiPrepMessage(priority=98)
        db.session.add(character_sheet_instruction)
        print("Seeded Gemini prep message priority 98.")
    character_sheet_instruction.message = "You must keep track of the character sheet and send all updates with the [CHARACTERSHEET] tag. The character sheet update must only contain the keys present in the following JSON template: [DB.TTRPG.JSON]. Do not add any new keys."

    if not GeminiPrepMessage.query.filter_by(priority=99).first():
        choice_instruction = GeminiPrepMessage(
            priority=99,
            message="""You are the GM in a [DB.TTRPG.Name] campaign. The player has chosen [DB.CHARACTER.NAME] as the character name for the next player character. Start by helping the player through the character creation steps, following your protocol precisely."""
        )
        db.session.add(choice_instruction)
        print("Seeded Gemini prep message priority 99.")

    db.session.commit()
    print("Database seeded.")

def register_cli_commands(app):
    app.cli.add_command(seed_data)
