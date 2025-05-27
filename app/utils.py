import random
import re # For _parse_gold
from flask import current_app
import google.generativeai as genai
import logging # For logging errors/warnings

def roll_dice(num_dice: int, num_sides: int, drop_lowest: int = 0) -> tuple[int, list[int]]:
    '''
    Rolls a specified number of dice with a given number of sides,
    optionally dropping a specified number of the lowest rolls.

    Args:
        num_dice (int): The number of dice to roll.
        num_sides (int): The number of sides on each die.
        drop_lowest (int): The number of lowest dice rolls to drop. Default is 0.

    Returns:
        tuple[int, list[int]]: A tuple containing the sum of the final rolls
                               and a list of all dice rolls made.
    '''
    if num_dice <= 0 or num_sides <= 0:
        raise ValueError("Number of dice and sides must be positive.")
    if drop_lowest < 0 or drop_lowest >= num_dice:
        raise ValueError("Number of dice to drop must be non-negative and less than the number of dice.")

    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    
    if drop_lowest > 0:
        # To get the sum of the highest rolls, we sort and then slice off the lowest ones.
        # The 'rolls' list itself is not modified for the return value if drop_lowest is used.
        sorted_rolls_for_sum = sorted(rolls)
        final_rolls_for_sum = sorted_rolls_for_sum[drop_lowest:]
        sum_of_rolls = sum(final_rolls_for_sum)
    else:
        sum_of_rolls = sum(rolls)
    
    return sum_of_rolls, rolls # Return original rolls for transparency

def list_gemini_models():
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key or api_key == 'YOUR_GEMINI_API_KEY_HERE':
        logging.warning("GEMINI_API_KEY is not configured or is set to the placeholder.")
        return []

    try:
        genai.configure(api_key=api_key)
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                models.append(m.name)
        return models
    except Exception as e:
        logging.error(f"Error listing Gemini models: {e}")
        return []

def parse_coinage(text_content: str) -> dict:
    """
    Parses a string to find and return amounts of gold (gp), silver (sp), and copper (cp).
    Returns a dictionary with keys 'Gold', 'Silver', 'Copper' and their respective amounts.
    Amounts default to 0 if not found.
    """
    coins = {'Gold': 0, 'Silver': 0, 'Copper': 0}
    if not text_content or not isinstance(text_content, str):
        return coins

    # Regex for gold: number followed by "gp", "gold pieces", or "g" (case insensitive)
    gold_match = re.search(r'(\d+)\s*(gp|gold\s*pieces?|g)\b', text_content, re.IGNORECASE)
    if gold_match:
        coins['Gold'] = int(gold_match.group(1))

    # Regex for silver: number followed by "sp" or "silver pieces" (case insensitive)
    silver_match = re.search(r'(\d+)\s*(sp|silver\s*pieces?)\b', text_content, re.IGNORECASE)
    if silver_match:
        coins['Silver'] = int(silver_match.group(1))

    # Regex for copper: number followed by "cp" or "copper pieces" (case insensitive)
    copper_match = re.search(r'(\d+)\s*(cp|copper\s*pieces?)\b', text_content, re.IGNORECASE)
    if copper_match:
        coins['Copper'] = int(copper_match.group(1))
        
    return coins
