"""Add DiceRoll Gemini prep message

Revision ID: d62e0f9bab9e
Revises: e5c17fa534d7
Create Date: 2025-08-11 12:53:14.265034

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd62e0f9bab9e'
down_revision = 'e5c17fa534d7'
branch_labels = None
depends_on = None


def upgrade():
    gemini_prep_message_table = sa.table('gemini_prep_message',
        sa.column('id', sa.Integer),
        sa.column('message', sa.String),
        sa.column('priority', sa.Integer)
    )

    op.bulk_insert(gemini_prep_message_table,
        [
            {
                'priority': 5,
                'message': """### 4. Requesting a Dice Roll
When the player needs to roll dice.
[APPDATA]
{
    "DiceRoll": {
        "Title": "Roll for Strength",
        "ButtonText": "Roll Stat",
        "Mechanic": "Heroic",
        "Dice": "4d6",
        "NumRolls": 6,
        "Advantage": false,
        "Disadvantage": false
    }
}
[/APPDATA]

**Parameters:**
- `Title`: (Required) A descriptive title for the roll.
- `ButtonText`: (Required) The text to display on the roll button.
- `Mechanic`: (Required) The dice mechanic to use. Supported values are:
    - `"Heroic"`: Rolls the specified dice, drops the lowest.
    - `"Classic"`: Rolls the specified dice.
    - `"High Floor"`: Rolls 2d6+6.
    - `"Percentile"`: Rolls 1d100.
- `Dice`: (Required for Heroic/Classic) The dice to roll (e.g., "4d6", "5d8").
- `NumRolls`: (Optional) The number of times to perform the roll. Defaults to 1.
- `Advantage`: (Optional) Set to `true` to roll with advantage. Defaults to `false`.
- `Disadvantage`: (Optional) Set to `true` to roll with disadvantage. Defaults to `false`.
"""
            }
        ]
    )


def downgrade():
    op.execute("DELETE FROM gemini_prep_message WHERE priority = 5")
