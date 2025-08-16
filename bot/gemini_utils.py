import logging
import time
import re
import json
import html
from flask import current_app
from flask_socketio import emit
from bot.character_utils import update_character_sheet

logger = logging.getLogger(__name__)

class MalformedAppDataError(Exception):
    pass

def process_bot_response(bot_response, character_id=None):
    charactersheet_pattern = re.compile(r'\[CHARACTERSHEET\](.*?)\[/CHARACTERSHEET\]', re.DOTALL)
    match_cs = charactersheet_pattern.search(bot_response)
    if match_cs and character_id:
        cs_json_str = match_cs.group(1)
        try:
            cs_data = json.loads(cs_json_str)
            update_character_sheet(character_id, cs_data)
            bot_response = charactersheet_pattern.sub('', bot_response).strip()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse CHARACTERSHEET json: {e}")

    if bot_response.count('[APPDATA]') != bot_response.count('[/APPDATA]'):
        raise MalformedAppDataError("Mismatched number of [APPDATA] and [/APPDATA] tags.")

    appdata_pattern = re.compile(r'\[APPDATA\](.*?)\[/APPDATA\]', re.DOTALL)
    match = appdata_pattern.search(bot_response)

    if not match:
        return bot_response.replace('\\n', '<br>')

    appdata_json_str = match.group(1)
    processed_text = appdata_pattern.sub('', bot_response).strip().replace('\\n', '<br>')

    try:
        appdata = json.loads(appdata_json_str)
        if 'SingleChoice' in appdata:
            choice_data = appdata['SingleChoice']
            title = choice_data.get('Title', 'Choose an option')
            options = choice_data.get('Options', {})

            html_choices = f'<div class="singlechoice-container"><h3>{title}</h3>'
            for key, details in options.items():
                html_choices += f"""
                    <div class="singlechoice-option">
                        <div class="singlechoice-option-inner">
                            <button onclick="sendChoice('{details['Name']}')">{details['Name']}</button>
                        </div>
                        <span class="description">{details['Description']}</span>
                    </div>
                """
            html_choices += '</div>'

            return processed_text + html_choices

        if 'OrderedList' in appdata:
            list_data = appdata['OrderedList']
            title = list_data.get('Title', 'Ordered List')
            items = list_data.get('Items', [])
            values = list_data.get('Values', [])

            html_list = f'<div class="ordered-list-container"><h3>{title}</h3><ul id="sortable-list">'
            for i, item in enumerate(items):
                value = values[i] if i < len(values) else ''
                li_class = "sortable-item"
                if i == 0:
                    li_class += " first-item"
                if i == len(items) - 1:
                    li_class += " last-item"

                html_list += f'<li class="{li_class}" data-name="{item["Name"]}">{item["Name"]}<div class="value-card" draggable="true" ondragstart="drag(event)" id="val-{i}"><span class="value">{value}</span><span class="arrows"><span class="up-arrow" onclick="moveValueUp(this)">&#8593;</span><span class="down-arrow" onclick="moveValueDown(this)">&#8595;</span></span><span class="drag-handle">&#9776;</span></div></li>'
            html_list += '</ul><button onclick="confirmOrderedList()">Confirm</button></div>'

            return processed_text + html_list

        if 'MultiSelect' in appdata:
            multiselect_data = appdata['MultiSelect']
            title = multiselect_data.get('Title', 'Choose an option')
            max_choices = multiselect_data.get('MaxChoices', 1)
            options = multiselect_data.get('Options', {})

            html_choices = f'<div class="multiselect-container" data-max-choices="{max_choices}"><h3>{title}</h3>'
            for key, details in options.items():
                html_choices += f"""
                    <div class="multiselect-option">
                        <div class="multiselect-option-inner">
                            <input type="checkbox" id="{key}" name="{details['Name']}" value="{details['Name']}">
                            <label for="{key}">{details['Name']}</label>
                        </div>
                        <span class="description">{details['Description']}</span>
                    </div>
                """
            html_choices += '<button onclick="confirmMultiSelect(this)">Confirm</button></div>'

            return processed_text + html_choices

        if 'DiceRoll' in appdata:
            dice_data = appdata['DiceRoll']
            title = dice_data.get('Title', 'Roll Dice')
            button_text = dice_data.get('ButtonText', 'Roll')

            dice_data_str = html.escape(json.dumps(dice_data))
            html_dice = f'''
                <div class="diceroll-container">
                    <h3>{title}</h3>
                    <button onclick="rollDice('{dice_data_str}')">{button_text}</button>
                </div>
            '''
            return processed_text + html_dice

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse APPDATA json: {e}")
        raise MalformedAppDataError(f"Failed to parse APPDATA json: {e}")

    return processed_text

def send_to_gemini_with_retry(model, history, character_id, max_retries=3):
    if current_app.config.get('GEMINI_DEBUG'):
        emit('debug_message', {'type': 'request', 'data': json.dumps(history, indent=2), 'character_id': character_id})

    bot_response_text = None
    for attempt in range(max_retries):
        try:
            response = model.generate_content(history)

            if not response or not (hasattr(response, 'parts') and response.parts or hasattr(response, 'text')):
                logger.warning(f"Empty response from Gemini on attempt {attempt + 1}")
                if attempt + 1 == max_retries:
                    return "Sorry, I received an empty or invalid response from the AI.", None
                continue

            if hasattr(response, 'parts') and response.parts:
                bot_response_text = "".join(part.text for part in response.parts)
            else:
                bot_response_text = response.text

            if current_app.config.get('GEMINI_DEBUG'):
                emit('debug_message', {'type': 'response', 'data': bot_response_text, 'character_id': character_id})

            logger.info(f"Gemini response (attempt {attempt+1}): {bot_response_text}")
            processed_response = process_bot_response(bot_response_text, character_id)
            return processed_response, bot_response_text

        except MalformedAppDataError as e:
            logger.warning(f"Malformed APPDATA from Gemini (attempt {attempt+1}): {e}. Retrying...")
            if bot_response_text:
                history.append({'role': 'model', 'parts': [bot_response_text]})
            history.append({'role': 'user', 'parts': ["The response you just sent contained a malformed [APPDATA] block. Please correct the formatting of the JSON data and resend your message."]})

            if attempt + 1 == max_retries:
                logger.error(f"Failed to get valid response from Gemini after {max_retries} attempts.")
                return "Sorry, I'm having trouble generating a valid response right now. Please try again later.", None

        except Exception as e:
            logger.error(f"Error calling Gemini API on attempt {attempt + 1}: {e}")
            if attempt + 1 == max_retries:
                return "Error: Could not connect to the bot.", None
            time.sleep(1)

    return "An unexpected error occurred.", None
