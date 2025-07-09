A single player Dugeons and Dragons adventure narrated by Google Gemini.

## Google Authentication Login Page

This project implements a Flask-based web application with Google OAuth for user authentication and a simple SQLite database (configurable for other SQL databases) to store user information.

### Setup and Running

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\\Scripts\\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    If you plan to use MySQL/MariaDB or PostgreSQL, uncomment the respective driver in `requirements.txt` (`pymysql` or `psycopg2-binary`) and run `pip install -r requirements.txt` again.

4.  **Configure the application:**
    *   The application expects a configuration file at `instance/config.py`.
    *   Create the `instance` directory if it doesn't exist:
        ```bash
        mkdir instance
        ```
    *   Copy the example configuration:
        ```bash
        cp instance/config.py.example instance/config.py
        ```
    *   **Edit `instance/config.py`:**
        *   **Google OAuth Credentials:**
            *   `GOOGLE_CLIENT_ID`: Your Google Cloud project's OAuth 2.0 Client ID.
            *   `GOOGLE_CLIENT_SECRET`: Your Google Cloud project's OAuth 2.0 Client Secret.
            *   `GOOGLE_REDIRECT_URI`: This **must** match one of the Authorized redirect URIs you configured in your Google Cloud Console for the OAuth client. By default, for local development, this is `http://localhost:5000/authorize`.
        *   **Database Configuration:**
            *   `DB_TYPE`: Set to `"sqlite"` (default), `"mysql"`, or `"postgresql"`.
            *   If `DB_TYPE` is `"sqlite"`:
                *   `DB_PATH`: Path to the SQLite database file (e.g., `"app.db"`). This will be created in the `instance` folder if a relative path is given.
            *   If `DB_TYPE` is `"mysql"` or `"postgresql"`:
                *   `DB_HOST`: Database server host (e.g., `"localhost"`).
                *   `DB_PORT`: Database server port (e.g., `"3306"` for MySQL, `"5432"` for PostgreSQL).
                *   `DB_USER`: Database username.
                *   `DB_PASSWORD`: Database password.
                *   `DB_NAME`: Database name.
            *   `SECRET_KEY`: A long, random string used to secure sessions. Generate a strong one for production.

5.  **Set up Google OAuth 2.0 Credentials:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Navigate to "APIs & Services" > "Credentials".
    *   Click "+ CREATE CREDENTIALS" and choose "OAuth client ID".
    *   Select "Web application" as the application type.
    *   Give it a name (e.g., "Flask Login App").
    *   Under "Authorized redirect URIs", add `http://localhost:5000/authorize` (or the `GOOGLE_REDIRECT_URI` you set in `config.py`). You might also need `http://127.0.0.1:5000/authorize`.
    *   Click "Create". Copy the "Client ID" and "Client Secret" into your `instance/config.py`.
    *   Ensure the "OAuth consent screen" is configured with necessary scopes (email, profile, openid are used by this app). You might need to add your Google account as a test user if the app is in "testing" mode.

6.  **Run the application:**
    ```bash
    python app.py
    ```
    The application should now be running at `http://localhost:5000`.

### How it Works

*   **`app.py`**: The main Flask application. It handles routing, database interaction (SQLAlchemy), user sessions (Flask-Login), and Google OAuth flow (Authlib).
*   **`instance/config.py`**: Stores sensitive configuration like API keys and database credentials. This file is not tracked by Git (it should be in `.gitignore`).
*   **`instance/config.py.example`**: A template for `config.py`.
*   **`templates/`**: Contains HTML templates for the login page (`login.html`) and the main page after login (`index.html`).
*   **`requirements.txt`**: Lists Python dependencies.
*   **Database**: A `User` model is defined to store user `id`, `google_id`, `email`, and `name`. The database is automatically created if it doesn't exist when the app starts.

### To use a different database (e.g., MariaDB/MySQL):

1.  Ensure the database server is running.
2.  Create a database and a user with permissions for that database.
3.  Install the required Python driver: `pip install pymysql` (for MySQL/MariaDB) or `pip install psycopg2-binary` (for PostgreSQL). Uncomment the respective line in `requirements.txt`.
4.  Update `instance/config.py` with:
    *   `DB_TYPE = "mysql"` (or `"postgresql"`)
    *   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` with your database details.
5.  Restart the Flask application. It should connect to the specified database.
