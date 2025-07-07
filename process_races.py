import json
import requests

def fetch_all_races():
    """Fetches all race data from the Open5E API."""
    all_races_data = []
    url = "https://api.open5e.com/v2/races/"
    while url:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        all_races_data.extend(data["results"])
        url = data["next"]
    return all_races_data

def fetch_race_data(race_url):
    """Fetches data for a single race if not already present."""
    response = requests.get(race_url)
    response.raise_for_status()
    return response.json()

def process_races(races_data):
    """Processes the race data to extract relevant information."""
    processed_races = []
    # Cache for parent race data to avoid redundant API calls
    parent_race_cache = {}

    for race in races_data:
        # Ensure all necessary data for the current race is present
        # Sometimes the list endpoint might not contain all details like 'desc' or 'traits' for all races
        if 'traits' not in race or 'desc' not in race:
            print(f"Fetching full data for {race.get('name', race.get('key'))}...")
            detailed_race_data = fetch_race_data(race['url'])
            race.update(detailed_race_data) # Update the race dict with full data

        processed_race = {
            "name": race.get("name"),
            "description": race.get("desc", ""),
            "ability_score_increase": "",
            "languages": "",
            "damage_resistance": "",
            "other_traits_html": ""
        }

        # Handle subraces: merge parent race traits
        if race.get("is_subrace") and race.get("subrace_of"):
            parent_url = race["subrace_of"]
            if parent_url not in parent_race_cache:
                print(f"Fetching parent race data from {parent_url} for subrace {race.get('name')}...")
                parent_data = fetch_race_data(parent_url)
                parent_race_cache[parent_url] = parent_data
            else:
                parent_data = parent_race_cache[parent_url]

            # Ensure parent data also has traits, fetch if not
            if 'traits' not in parent_data:
                 print(f"Fetching full data for parent race {parent_data.get('name', parent_data.get('key'))}...")
                 detailed_parent_data = fetch_race_data(parent_data['url'])
                 parent_data.update(detailed_parent_data)


            # Combine descriptions
            processed_race["description"] = f"{parent_data.get('desc', '')}\n\n{race.get('desc', '')}".strip()

            # Combine traits, subrace traits take precedence or add to parent traits
            combined_traits = {trait['name']: trait['desc'] for trait in parent_data.get('traits', [])}
            for trait in race.get('traits', []):
                # For ability score increases, we want to combine them if possible
                if trait['name'] == "Ability Score Increase" and "Ability Score Increase" in combined_traits:
                    combined_traits[trait['name']] = f"{combined_traits[trait['name']]}. {trait['desc']}"
                else:
                    combined_traits[trait['name']] = trait['desc']

            current_traits = [{"name": name, "desc": desc} for name, desc in combined_traits.items()]

        else:
            current_traits = race.get("traits", [])

        other_traits_list = []
        for trait in current_traits:
            trait_name = trait.get("name", "Unnamed Trait")
            trait_desc = trait.get("desc", "No description available.")
            if trait_name == "Ability Score Increase":
                processed_race["ability_score_increase"] = trait_desc
            elif trait_name == "Languages":
                processed_race["languages"] = trait_desc
            elif trait_name == "Damage Resistance": # Exact match for "Damage Resistance"
                processed_race["damage_resistance"] = trait_desc
            elif "resistance" in trait_name.lower() and not processed_race["damage_resistance"]: # More generic check if specific not found
                 processed_race["damage_resistance"] = trait_desc
            else:
                other_traits_list.append(f"<b>{trait_name}</b><br>{trait_desc}")

        processed_race["other_traits_html"] = "<br><br>".join(other_traits_list)
        processed_races.append(processed_race)

    return processed_races

def main():
    """Main function to fetch, process, and save race data."""
    print("Fetching all race data from Open5E API...")
    races_data = fetch_all_races()
    print(f"Fetched {len(races_data)} race entries.")

    print("Processing race data...")
    processed_data = process_races(races_data)
    print("Finished processing race data.")

    output_filename = "races_database.json"
    print(f"Saving processed data to {output_filename}...")
    with open(output_filename, "w") as f:
        json.dump(processed_data, f, indent=4)
    print(f"Data successfully saved to {output_filename}.")

if __name__ == "__main__":
    main()
