import random
import re
from typing import List, Dict, Any, Tuple

def roll_dice(dice_string: str) -> Tuple[List[int], int]:
    """
    Rolls dice based on a string like '4d6' or 'd20'.

    Args:
        dice_string: The string representing the dice to roll.

    Returns:
        A tuple containing a list of the individual rolls and their sum.
    """
    if not isinstance(dice_string, str):
        raise TypeError("dice_string must be a string.")

    match = re.match(r'(\d*)d(\d+)([\+\-]\d+)?', dice_string)
    if not match:
        raise ValueError(f"Invalid dice string format: {dice_string}")

    num_dice = int(match.group(1)) if match.group(1) else 1
    num_sides = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    if num_dice <= 0 or num_sides <= 0:
        raise ValueError("Number of dice and sides must be positive.")

    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    return rolls, total

def _roll_heroic(dice_string: str) -> Dict[str, Any]:
    """
    Rolls a set of dice, drops the lowest, and sums the rest.
    """
    rolls, _ = roll_dice(dice_string)
    dropped = min(rolls)
    total = sum(rolls) - dropped
    return {
        "total": total,
        "rolls": sorted(rolls, reverse=True),
        "dropped": [dropped]
    }

def _roll_classic(dice_string: str) -> Dict[str, Any]:
    """
    Rolls a set of dice and sums them.
    """
    rolls, total = roll_dice(dice_string)
    return {
        "total": total,
        "rolls": rolls,
        "dropped": []
    }

def _roll_high_floor() -> Dict[str, Any]:
    """
    Rolls 2d6+6.
    """
    rolls, total = roll_dice('2d6+6')
    return {
        "total": total,
        "rolls": rolls,
        "dropped": []
    }

def _roll_percentile() -> Dict[str, Any]:
    """
    Rolls d100.
    """
    rolls, total = roll_dice('1d100')
    return {
        "total": total,
        "rolls": rolls,
        "dropped": []
    }

MECHANICS = {
    "Heroic": _roll_heroic,
    "Classic": _roll_classic,
    "High Floor": _roll_high_floor,
    "Percentile": _roll_percentile
}

def roll(mechanic: str, dice: str = None, num_rolls: int = 1, advantage: bool = False, disadvantage: bool = False) -> List[Dict[str, Any]]:
    """
    Performs one or more dice rolls using a specified mechanic.

    Args:
        mechanic: The name of the rolling mechanic to use.
        dice: The dice string (e.g., '4d6'). Required for 'Heroic' and 'Classic'.
        num_rolls: The number of times to perform the roll.
        advantage: Whether to roll with advantage.
        disadvantage: Whether to roll with disadvantage.

    Returns:
        A list of dictionaries, where each dictionary represents a single roll result.
    """
    if mechanic not in MECHANICS:
        raise ValueError(f"Unknown mechanic: {mechanic}")

    roll_func = MECHANICS[mechanic]

    # These mechanics require a dice string
    if mechanic in ["Heroic", "Classic"]:
        if not dice:
            raise ValueError(f"Mechanic '{mechanic}' requires a 'dice' string.")

        # Create a partial function with the dice string
        import functools
        roll_func = functools.partial(roll_func, dice_string=dice)

    results = []

    for _ in range(num_rolls):
        if advantage and disadvantage:
            result = roll_func()
        elif advantage:
            roll1 = roll_func()
            roll2 = roll_func()
            result = roll1 if roll1['total'] >= roll2['total'] else roll2
            result['all_rolls'] = [roll1, roll2]
        elif disadvantage:
            roll1 = roll_func()
            roll2 = roll_func()
            result = roll1 if roll1['total'] <= roll2['total'] else roll2
            result['all_rolls'] = [roll1, roll2]
        else:
            result = roll_func()

        results.append(result)

    return results
