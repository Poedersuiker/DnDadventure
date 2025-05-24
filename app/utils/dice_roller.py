import random

def roll_dice(sides: int, num_dice: int = 1, modifier: int = 0) -> dict:
    if sides <= 0 or num_dice <= 0:
        raise ValueError("Number of dice and sides must be positive.")
    
    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    raw_total = sum(rolls)
    total_with_modifier = raw_total + modifier
    
    # Construct a dice notation string, e.g., "1d20+2" or "2d6-1"
    modifier_str = ""
    if modifier > 0:
        modifier_str = f"+{modifier}"
    elif modifier < 0:
        modifier_str = f"{modifier}" # Already includes the minus sign
    elif modifier == 0:
        modifier_str = "" # Explicitly empty for +0 case in description
        
    description = f"{num_dice}d{sides}{modifier_str}"
    
    return {
        'rolls': rolls,
        'raw_total': raw_total,
        'modifier': modifier,
        'total_with_modifier': total_with_modifier,
        'description': description
    }

def roll_ability_scores() -> list[int]:
    """
    Generates 6 D&D 5e ability scores using the "4d6 drop lowest" method.
    
    Returns:
        A list containing the 6 generated ability scores.
    """
    ability_scores = []
    for _ in range(6): # Generate 6 scores
        # Roll four 6-sided dice
        rolls = [random.randint(1, 6) for _ in range(4)]
        # Sort the rolls to easily find the lowest
        rolls.sort()
        # Sum the three highest rolls (discarding the lowest)
        score = sum(rolls[1:]) # The first element is the lowest after sorting
        ability_scores.append(score)
    return ability_scores
