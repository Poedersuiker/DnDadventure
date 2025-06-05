# DnDadventure


DnDadventure offers a solo Dungeons & Dragons experience where Google's Gemini large language model takes on the role of the AI Dungeon Master (DM). Gemini is responsible for weaving the narrative, controlling non-player characters (NPCs), interpreting player actions, and describing the unfolding world. Players interact with the game through an adventure log, making choices, managing their character's inventory, and deciding when to rest and recover. Future enhancements aim to include mechanics for dice rolling for skill checks and combat.

This README provides an overview of how to set up, configure, and run the application, as well as details on its core features like character management and the local Open5e API data mirror.

## Configuration

This application uses a layered configuration system:
1.  **Defaults (`config.py`)**: The `config.py` file in the project root contains default settings. You generally shouldn't need to edit this file directly.
2.  **Instance Configuration (`instance/config.py`)**: For user-specific settings, especially secrets like API keys and the Flask `SECRET_KEY`, you should use an `instance/config.py` file. This file is gitignored by default to protect your sensitive information.
    -   To set up your instance configuration:
        1.  Copy the example file: `cp instance/config.py.example instance/config.py`
        2.  Edit `instance/config.py` with your actual values.
    -   Example structure for `instance/config.py`:
        ```python
        # Flask App Secret Key - Replace with a long, random string
        # Generate one using: python -c 'import secrets; print(secrets.token_hex(16))'
        SECRET_KEY = 'YOUR_ACTUAL_FLASK_SECRET_KEY'

        # Google OAuth Credentials
        GOOGLE_CLIENT_ID = 'YOUR_ACTUAL_GOOGLE_CLIENT_ID'
        GOOGLE_CLIENT_SECRET = 'YOUR_ACTUAL_GOOGLE_CLIENT_SECRET'

        # Google API Key for Gemini services
        # This is highly recommended to be set here or as an environment variable.
        GOOGLE_API_KEY = 'YOUR_GEMINI_API_KEY'
        ```
3.  **Environment Variables**: Settings like `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_API_KEY` can also be provided via environment variables.

The application loads configurations with the following precedence (highest to lowest):
1.  `instance/config.py`
2.  Environment Variables
3.  `config.py` defaults

**Key configurations you MUST set (ideally in `instance/config.py` or via environment variables):**
-   `SECRET_KEY`: Used by Flask for session management.
-   `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID.
-   `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret.
-   `GOOGLE_API_KEY`: Your Google API Key for Gemini services. This is crucial for the AI storyteller features. Alternatively, this key can be provided at runtime using the `--google_api_key` argument in `run.py`.

## Running the Application

Before running the application, ensure that you have properly configured your secrets (like `SECRET_KEY`, Google OAuth credentials, and `GOOGLE_API_KEY`) in `instance/config.py` or as environment variables, as detailed in the "Configuration" section.

You can run the application using `run.py`. It supports the following command-line arguments:
-   `--host`: Specifies the IP address the application will listen on (e.g., `0.0.0.0` to listen on all network interfaces). Defaults to `127.0.0.1`.
-   `--google_api_key`: Specifies your Google API Key for Gemini services.

Example:
```bash
python run.py --host 0.0.0.0 --google_api_key YOUR_API_KEY_HERE
```

For more advanced deployment scenarios, such as running behind a reverse proxy, see the section below.

## Running Behind a Reverse Proxy (e.g., HAProxy, Nginx)

When deploying the application behind a reverse proxy that handles SSL termination (i.e., converts HTTPS traffic from the internet to HTTP traffic for the Flask application), it's crucial to configure the proxy and the application correctly.

### Proxy Configuration
-   **`X-Forwarded-Proto` Header**: Your reverse proxy must be configured to send the `X-Forwarded-Proto` header to the Flask application. This header should be set to `https` when the original request from the client was HTTPS. This allows the application to understand that it's being accessed via HTTPS, even if the direct connection from the proxy to the app is HTTP.

### Application Configuration (`ProxyFix`)
-   The Flask application is already equipped with the `ProxyFix` middleware (configured in `app/__init__.py`). This middleware reads the `X-Forwarded-Proto`, `X-Forwarded-For`, `X-Forwarded-Host`, and `X-Forwarded-Prefix` headers set by the proxy, ensuring that Flask's URL generation (e.g., for redirects and OAuth callbacks) works correctly.

### Google OAuth Configuration (Google Cloud Console)
For Google OAuth to function correctly when the application is behind a reverse proxy and accessed via a custom domain:
-   **Authorized redirect URIs**: You must configure the "Authorized redirect URIs" in your Google Cloud Console project for your OAuth 2.0 client. This URI should match the path where Google will send the user back after authentication. Given the application's setup, this will be:
    ```
    https://yourdomain.com/auth/google/authorized
    ```
    Replace `yourdomain.com` with your actual domain name.

### Flask-Dance Configuration
-   **Credentials**: The `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are no longer set directly in `app/auth.py`. Instead, they are loaded from `app.config` (which is populated from `config.py`, `instance/config.py`, or environment variables as described in the "Configuration" section). Ensure these are correctly set in your `instance/config.py` or environment variables.
-   **`authorized_url`**: This is set to `"/authorized"` within the `make_google_blueprint` configuration in `app/auth.py`. Combined with the blueprint's prefix (`/auth/google`), this forms the path part of the redirect URI (`/auth/google/authorized`) that Google uses. The application will correctly construct the full redirect URL based on the incoming request's host and scheme (thanks to `ProxyFix`).

## Local Open5e API Mirror

This feature provides a local copy of the Open5e API data, served directly by this application. This can be useful for offline development, reducing reliance on the external API, or ensuring consistent data for testing.

### Overview
The application can host a mirror of the Open5e API, serving data for various D&D entities such as monsters, spells, races, classes, and more. This data is fetched from the public Open5e API and stored in a local SQLite database named `instance/open5e.db`. Flask endpoints then serve this data, mimicking the structure of the official API.

### Database Structure
The `instance/open5e.db` SQLite database is structured as follows:
-   For each category of D&D entity supported (e.g., "spells", "monsters", "races", "classes"), a dedicated table exists in the database (e.g., a `spells` table, a `monsters` table).
-   Within each such table, individual entries (like a specific spell or race) are stored as a single row.
-   Each row primarily consists of two columns:
    -   `slug`: A unique text identifier for the entity (e.g., "fireball" for a spell).
    -   `data`: A JSON text field containing the complete data for that entity, exactly as retrieved from the Open5e API.
This structure allows the application to store a direct mirror of the API's JSON responses for each item, rather than using a complex relational schema with many columns per entity.

### Setup and Data Population
The primary external Python dependency for fetching data is `requests` (which should be listed in `requirements.txt`).

1.  **Create Database Schema**
    The `app/scripts/create_db.py` script is responsible for setting up the `instance/open5e.db` database with the table structures described above (i.e., creating the various entity tables like `spells`, `monsters`, etc., each with `slug` and `data` columns). Before populating the data, run the following command from the project root:
    ```bash
    python app/scripts/create_db.py
    ```
    This will create the `instance/open5e.db` file if it doesn't exist and ensure all necessary tables are present.

2.  **Populate the Database**
    Once the database schema is created by `app/scripts/create_db.py`, you can populate it with data harvested from the live Open5e API using the `app/scripts/harvest_open5e_data.py` script:
    ```bash
    python app/scripts/harvest_open5e_data.py
    ```
    **Note:** This script fetches a large amount of data (potentially hundreds of megabytes) from the live Open5e API and can take a significant amount of time to complete (e.g., 10-30 minutes or more depending on network speed and API responsiveness). Please be patient. It is also advisable to run it during off-peak hours if you are concerned about API rate limits on the public API.

### Running the API
The local Open5e API endpoints become available automatically when you run the main Flask application:
```bash
python run.py [arguments, e.g., --host 0.0.0.0]
```
Refer to the "Running the Application" section for more details on `run.py` arguments.

### Running API Tests
Specific unit tests for the local Open5e API endpoints can be run as follows:
```bash
python -m unittest tests.test_open5e_api
```
This command executes the tests defined in `tests/test_open5e_api.py`. Ensure you have populated the database at least once, or that the test setup (which includes minimal data population) can successfully create and access `instance/open5e.db`.

### Available API Endpoints
All local Open5e API endpoints are available under the `/api` URL prefix. List endpoints support `?page=<number>` and `?limit=<number>` query parameters for pagination (defaulting to `page=1`, `limit=10`).

-   **Manifest**: `GET /api/v1/manifest/`
-   **Monsters**:
    -   `GET /api/v1/monsters/`
    -   `GET /api/v1/monsters/<slug>/`
-   **Spells**:
    -   `GET /api/v2/spells/`
    -   `GET /api/v2/spells/<slug>/`
-   **Spell Lists**:
    -   `GET /api/v1/spelllist/`
    -   `GET /api/v1/spelllist/<slug>/`
-   **Documents**:
    -   `GET /api/v2/documents/`
    -   `GET /api/v2/documents/<slug>/`
-   **Backgrounds**:
    -   `GET /api/v2/backgrounds/`
    -   `GET /api/v2/backgrounds/<slug>/`
-   **Planes**:
    -   `GET /api/v1/planes/`
    -   `GET /api/v1/planes/<slug>/`
-   **Sections**:
    -   `GET /api/v1/sections/`
    -   `GET /api/v1/sections/<slug>/`
-   **Feats**:
    -   `GET /api/v2/feats/`
    -   `GET /api/v2/feats/<slug>/`
-   **Conditions**:
    -   `GET /api/v2/conditions/`
    -   `GET /api/v2/conditions/<slug>/`
-   **Races**:
    -   `GET /api/v2/races/`
    -   `GET /api/v2/races/<slug>/`
-   **Classes**:
    -   `GET /api/v1/classes/`
    -   `GET /api/v1/classes/<slug>/`
-   **Magic Items**:
    -   `GET /api/v1/magicitems/`
    -   `GET /api/v1/magicitems/<slug>/`
-   **Weapons**:
    -   `GET /api/v2/weapons/`
    -   `GET /api/v2/weapons/<slug>/`
-   **Armor**:
    -   `GET /api/v2/armor/`
    -   `GET /api/v2/armor/<slug>/`

## Character Management

This section outlines how player characters are created, stored, and leveled up within the application.

### Character Creation
Player characters are created using a multi-step wizard available at the `/creation_wizard` endpoint. This interactive process guides the user through selecting their character's race, class, background, abilities, and initial equipment.

-   **Data Sourcing**: Essential Dungeons & Dragons data for character creation—such as available races, classes, spells, equipment options, and features—is primarily drawn from the data sourced from the Open5e API. The application can use a local mirror of this data, as described in the "Local Open5e API Mirror" section, ensuring availability and consistency. It's important to note that the old system of using direct database models (e.g., `Race`, `Class`, `Spell` in `app/models`) for storing the *definitions* of these D&D entities has been removed in favor of using the JSON data from Open5e.
-   **Session Management**: The creation wizard relies on server-side session data to manage the player's choices across the multiple steps of character building.

### Character Data Storage
Once a character is created, their information is stored in the application's database using the following models:

-   **`Character` Model**: This is the primary model for a player character. It stores general information such as the character's name, selected race and class (referencing slugs from Open5e data), ability scores, alignment, background, and current status (e.g., `dm_allowed_level`).
-   **`CharacterLevel` Model**: Detailed attributes specific to each level the character attains are stored in this model. Each `CharacterLevel` record is linked to a `Character` and includes information such as hit points (HP) for that level, chosen class features, new spells known or prepared, proficiencies gained, and any ability score increases (ASIs) taken at that level. This allows for a complete history of the character's progression.

### Leveling Up
Characters can advance in level through a DM-controlled process:

-   **DM Approval**: The Dungeon Master (Gemini) can grant a level up by issuing a specific command like `SYSTEM: LEVELUP GRANTED TO LEVEL X`. The application then updates the `dm_allowed_level` attribute on the `Character` model.
-   **Level-Up Process**: When a character is eligible to level up (i.e., their current level is less than `dm_allowed_level`), they can go through a level-up process. This typically involves:
    -   Increasing maximum Hit Points.
    -   Selecting new class features or making choices for existing ones (e.g., choosing an Ability Score Increase (ASI) or a feat).
    -   Acquiring new spells (for spellcasting classes).
-   **Data Recording**: All changes, choices, and new attributes gained during level-up are recorded by creating a new `CharacterLevel` entry associated with the character for their new level.
