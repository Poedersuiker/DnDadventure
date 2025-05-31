import sqlite3
import requests
import json
import os
import time

DATABASE_NAME = "open5e.db"
INSTANCE_FOLDER = "instance"
DATABASE_PATH = os.path.join(INSTANCE_FOLDER, DATABASE_NAME)

API_ENDPOINTS = [
    {
        "name": "manifest",
        "url": "https://api.open5e.com/v1/manifest/",
        "id_field": "slug", # Special handling: use a fixed slug for the single manifest entry
        "is_single_entry": True,
    },
    {
        "name": "spells",
        "url": "https://api.open5e.com/v2/spells/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "spelllist",
        "url": "https://api.open5e.com/v1/spelllist/",
        "id_field": "slug",
        "results_field": "results",
    },
    {
        "name": "monsters",
        "url": "https://api.open5e.com/v1/monsters/",
        "id_field": "slug",
        "results_field": "results",
    },
    {
        "name": "documents",
        "url": "https://api.open5e.com/v2/documents/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "backgrounds",
        "url": "https://api.open5e.com/v2/backgrounds/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "planes",
        "url": "https://api.open5e.com/v1/planes/",
        "id_field": "slug",
        "results_field": "results",
    },
    {
        "name": "sections",
        "url": "https://api.open5e.com/v1/sections/",
        "id_field": "slug",
        "results_field": "results",
    },
    {
        "name": "feats",
        "url": "https://api.open5e.com/v2/feats/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "conditions",
        "url": "https://api.open5e.com/v2/conditions/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "races",
        "url": "https://api.open5e.com/v2/races/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "classes",
        "url": "https://api.open5e.com/v1/classes/",
        "id_field": "slug",
        "results_field": "results",
    },
    {
        "name": "magicitems",
        "url": "https://api.open5e.com/v1/magicitems/",
        "id_field": "slug",
        "results_field": "results",
    },
    {
        "name": "weapons",
        "url": "https://api.open5e.com/v2/weapons/",
        "id_field": "key",
        "results_field": "results",
    },
    {
        "name": "armor",
        "url": "https://api.open5e.com/v2/armor/",
        "id_field": "key",
        "results_field": "results",
    },
]

def fetch_and_store_data():
    """Fetches data from Open5e API and stores it in the SQLite database."""
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}. Please run create_db.py first.")
        return

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        print(f"Successfully connected to database: {DATABASE_PATH}")

        for endpoint_info in API_ENDPOINTS:
            table_name = endpoint_info["name"]
            url = endpoint_info["url"]
            id_field = endpoint_info["id_field"]
            is_single_entry = endpoint_info.get("is_single_entry", False)
            results_field = endpoint_info.get("results_field", "results") # Default for most

            print(f"\nFetching data for table: {table_name} from {url}")
            total_items_fetched = 0

            if is_single_entry:
                try:
                    response = requests.get(url, timeout=30)
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    item_data = response.json()

                    # For manifest, the API returns a dictionary, not a list.
                    # We'll use a fixed slug for it.
                    slug = "open5e_manifest_v1" # Fixed slug for the manifest
                    data_json = json.dumps(item_data)

                    cursor.execute(
                        f"INSERT OR REPLACE INTO {table_name} (slug, data) VALUES (?, ?)",
                        (slug, data_json),
                    )
                    conn.commit()
                    total_items_fetched = 1
                    print(f"Stored manifest data with slug '{slug}'.")
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching manifest {url}: {e}")
                    continue # Move to next endpoint
            else:
                current_url = url
                page_num = 1
                while current_url:
                    print(f"Fetching page {page_num} for {table_name} from {current_url}...")
                    try:
                        response = requests.get(current_url, timeout=30)
                        response.raise_for_status()
                        page_data = response.json()

                        items = page_data.get(results_field, [])
                        if not items:
                            print(f"No items found in '{results_field}' for {table_name} at {current_url}. Stopping.")
                            break

                        for item in items:
                            slug = item.get(id_field)
                            if slug is None:
                                print(f"Warning: Missing id_field '{id_field}' in item: {item}. Skipping.")
                                continue

                            data_json = json.dumps(item)
                            cursor.execute(
                                f"INSERT OR REPLACE INTO {table_name} (slug, data) VALUES (?, ?)",
                                (slug, data_json),
                            )
                            total_items_fetched += 1

                        conn.commit() # Commit after each page
                        print(f"Fetched and stored {len(items)} items from page {page_num} for {table_name}.")

                        current_url = page_data.get("next")
                        page_num += 1
                        if current_url:
                            time.sleep(0.2) # Brief pause to be polite to the API

                    except requests.exceptions.RequestException as e:
                        print(f"Error fetching page {current_url} for {table_name}: {e}")
                        current_url = None # Stop trying for this endpoint on error
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from {current_url} for {table_name}: {e}")
                        current_url = None # Stop trying for this endpoint

            print(f"Finished fetching for {table_name}. Total items stored: {total_items_fetched}.")

    except sqlite3.Error as e:
        print(f"SQLite error during data harvesting: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    print("Running script to harvest Open5e API data...")
    fetch_and_store_data()
    print("Script finished.")
