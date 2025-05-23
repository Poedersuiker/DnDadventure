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
