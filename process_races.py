import json
import requests
import time # For potential delays if needed, and for logging

# Default status updater if none is provided (e.g., for standalone runs)
def _default_status_updater(update):
    print(f"SCRIPT_PROGRESS: {update}")

def fetch_all_races(status_updater=_default_status_updater):
    """Fetches all race data from the Open5E API."""
    all_races_data = []
    url = "https://api.open5e.com/v2/races/"
    page_num = 1
    status_updater({
        "status": "running",
        "message": "Starting to fetch race list from Open5E API...",
        "current": 0,
        "total": 0 # Total unknown until first page is fetched
    })
    while url:
        try:
            status_updater({"message": f"Fetching page {page_num} from {url}..."})
            response = requests.get(url, timeout=30) # Increased timeout
            response.raise_for_status()
            data = response.json()
            all_races_data.extend(data["results"])
            if page_num == 1: # After first page, we know the total
                status_updater({"total": data.get("count", len(all_races_data))}) # Update total based on API count
            status_updater({"message": f"Fetched page {page_num}. Total races so far: {len(all_races_data)}."})
            url = data.get("next")
            page_num += 1
        except requests.exceptions.RequestException as e:
            error_message = f"Error fetching race list page {page_num}: {e}"
            status_updater({"status": "error", "message": error_message})
            raise # Re-raise to stop processing if list fetching fails

    status_updater({"message": f"Finished fetching all race data. Total entries: {len(all_races_data)}.", "total": len(all_races_data)})
    return all_races_data

def fetch_race_data(race_url, race_name_for_log, status_updater=_default_status_updater):
    """Fetches data for a single race if not already present."""
    status_updater({"message": f"Fetching detailed data for {race_name_for_log} from {race_url}..."})
    try:
        response = requests.get(race_url, timeout=30) # Increased timeout
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        error_message = f"Error fetching detailed data for {race_name_for_log} from {race_url}: {e}"
        # Log this but allow processing to continue with potentially incomplete data for this race, or decide to fail hard
        status_updater({"message": f"WARNING: {error_message}. Skipping details for this entry or using partial data."})
        return None # Or raise, depending on how critical full data is

def process_races(races_data, status_updater=_default_status_updater):
    """Processes the race data to extract relevant information."""
    processed_races = []
    parent_race_cache = {}
    total_races_to_process = len(races_data)
    status_updater({"total": total_races_to_process, "message": "Starting to process races..."})

    for i, race_entry in enumerate(races_data):
        current_race_num = i + 1
        race_name = race_entry.get("name", race_entry.get("key", f"UnknownRace_{current_race_num}"))
        status_updater({
            "current": current_race_num,
            "message": f"Processing race {current_race_num}/{total_races_to_process}: {race_name}"
        })

        # Make a copy to avoid modifying the original list dicts if they are re-used
        race = dict(race_entry)

        if 'traits' not in race or 'desc' not in race:
            detailed_race_data = fetch_race_data(race['url'], race_name, status_updater)
            if detailed_race_data:
                race.update(detailed_race_data)
            else:
                status_updater({"message": f"Could not fetch full details for {race_name}. Proceeding with available data."})


        processed_race = {
            "name": race.get("name"),
            "description": race.get("desc", ""),
            "ability_score_increase": "",
            "languages": "",
            "damage_resistance": "",
            "other_traits_html": ""
        }

        # Initial setup for traits and description, defaults to the race's own.
        current_traits_list = list(race.get("traits", []))
        processed_race["description"] = race.get('desc', "")

        if race.get("is_subrace") and race.get("subrace_of"):
            parent_url = race["subrace_of"]
            parent_name_for_log = parent_url.split('/')[-2] if parent_url.endswith('/') else parent_url.split('/')[-1]
            status_updater({"message": f"Race {race_name} is a subrace. Processing parent {parent_name_for_log}."})

            parent_data = None # Initialize parent_data to None

            if parent_url in parent_race_cache:
                parent_data = parent_race_cache[parent_url]
                if parent_data: # Ensure cached data is not None
                    status_updater({"message": f"Found parent {parent_name_for_log} in cache for {race_name}."})
                else:
                    status_updater({"message": f"Parent {parent_name_for_log} in cache was None/invalid. Will attempt re-fetch."})
                    del parent_race_cache[parent_url] # Remove invalid entry

            if not parent_data: # If not found in cache or cache was invalid
                fetched_parent = fetch_race_data(parent_url, f"parent ({parent_name_for_log})", status_updater)
                if fetched_parent:
                    parent_data = fetched_parent
                    parent_race_cache[parent_url] = parent_data # Cache successfully fetched data
                else:
                    status_updater({"message": f"WARNING: Failed to fetch parent race data for {parent_name_for_log}. Subrace {race_name} will not include parent traits."})

            if parent_data: # Proceed with merging only if parent_data is valid.
                # Further check if parent_data needs its details fetched/updated
                if 'traits' not in parent_data or 'desc' not in parent_data:
                    if 'url' in parent_data: # Check if URL exists for re-fetch
                        status_updater({"message": f"Parent {parent_name_for_log} data is missing details. Attempting re-fetch..."})
                        detailed_parent_data = fetch_race_data(parent_data['url'], f"parent ({parent_name_for_log}) details", status_updater)
                        if detailed_parent_data:
                            parent_data.update(detailed_parent_data)
                            parent_race_cache[parent_url] = parent_data # Update cache
                    else:
                        status_updater({"message": f"WARNING: Parent {parent_name_for_log} data is incomplete (no URL for re-fetch)."})

                parent_desc = parent_data.get('desc', '')
                subrace_desc = race.get('desc', '')
                if parent_desc:
                    processed_race["description"] = f"{parent_desc}\n\n{subrace_desc}".strip()

                # Combine traits: parent traits first, then subrace traits
                final_traits_map = {trait['name']: trait['desc'] for trait in parent_data.get('traits', [])}

                for trait_entry in race.get('traits', []): # Subrace's original traits
                    trait_name = trait_entry['name']
                    trait_desc = trait_entry['desc']
                    if trait_name == "Ability Score Increase" and trait_name in final_traits_map:
                        final_traits_map[trait_name] = f"{final_traits_map[trait_name]}. {trait_desc}"
                    else:
                        final_traits_map[trait_name] = trait_desc
                current_traits_list = [{'name': name, 'desc': desc} for name, desc in final_traits_map.items()]

        # Process the final list of traits (either subrace's own or combined)
        other_traits_html_parts = []
        for trait in current_traits_list:
            trait_name = trait.get("name", "Unnamed Trait")
            trait_desc = trait.get("desc", "No description available.")
            if trait_name == "Ability Score Increase":
                processed_race["ability_score_increase"] = trait_desc
            elif trait_name == "Languages":
                processed_race["languages"] = trait_desc
            elif trait_name == "Damage Resistance":
                processed_race["damage_resistance"] = trait_desc
            elif "resistance" in trait_name.lower() and not processed_race["damage_resistance"]:
                 processed_race["damage_resistance"] = trait_desc # Catch other resistances if specific one not found
            else:
                other_traits_html_parts.append(f"<b>{trait_name}</b><br>{trait_desc}")

        processed_race["other_traits_html"] = "<br><br>".join(other_traits_html_parts)
        processed_races.append(processed_race)

    status_updater({"message": "Finished processing all races."})
    return processed_races

def main(status_updater=_default_status_updater):
    """Main function to fetch, process, and save race data."""
    output_filename = "races_database.json"
    try:
        status_updater({
            "status": "running",
            "message": "Initiating race data processing...",
            "current": 0,
            "total": 0,
            "output_file": None
        })

        races_data = fetch_all_races(status_updater)

        processed_data = process_races(races_data, status_updater)

        status_updater({"message": f"Saving processed data to {output_filename}..."})
        with open(output_filename, "w") as f:
            json.dump(processed_data, f, indent=4)

        status_updater({
            "status": "complete",
            "message": f"Data successfully saved to {output_filename}.",
            "current": len(processed_data), # Should be total
            "output_file": output_filename
        })
        print(f"Data successfully saved to {output_filename}.") # For standalone console
    except Exception as e:
        error_message = f"An error occurred during race processing: {e}"
        print(f"ERROR: {error_message}") # For standalone console
        status_updater({"status": "error", "message": error_message, "output_file": None})


if __name__ == "__main__":
    # Example of how to run it standalone for testing (without Flask status updater)
    def _test_updater(status_update):
        print(f"Status Update: {status_update}")
    main(status_updater=_test_updater)
