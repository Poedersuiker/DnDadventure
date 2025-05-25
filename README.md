# DnDadventure
One player DnD adventure using Gemini as a storyteller

## Configuration

This application uses a layered configuration system:
1.  **Defaults (`config.py`)**: The `config.py` file in the project root contains default settings and fallbacks for configurations that can be set via environment variables. You generally shouldn't need to edit this file directly.
2.  **Instance Configuration (`instance/config.py`)**: For user-specific settings, especially secrets like API keys and the Flask `SECRET_KEY`, you should use the `instance/config.py` file. This file is **gitignored** and will not be committed to the repository, keeping your sensitive information secure.
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

        # Optional: Override Google API Key for Gemini services if not set as an environment variable
        # GOOGLE_API_KEY = 'YOUR_GEMINI_API_KEY' 
        ```
3.  **Environment Variables**: As shown in `config.py`, settings like `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_API_KEY` can also be provided via environment variables. Environment variables will take precedence over the defaults in `config.py` but will be overridden by values in `instance/config.py` if that file exists and defines them. *(Correction: `config.py` is structured so env vars override `config.py` defaults, and `instance/config.py` overrides all).* The application loads configurations in this order: `config.py` -> `instance/config.py`. Environment variables are checked by `config.py` itself.

**Key configurations you MUST set in `instance/config.py` or via environment variables:**
-   `SECRET_KEY`: Used by Flask for session management.
-   `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID.
-   `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret.
-   `GOOGLE_API_KEY`: Your Google API Key for Gemini services (this one is mentioned in `run.py` args, but can also be set here or via env var for consistency if `run.py` is adapted).

## Running the Application

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
- **`X-Forwarded-Proto` Header**: Your reverse proxy must be configured to send the `X-Forwarded-Proto` header to the Flask application. This header should be set to `https` when the original request from the client was HTTPS. This allows the application to understand that it's being accessed via HTTPS, even if the direct connection from the proxy to the app is HTTP.

### Application Configuration (`ProxyFix`)
- The Flask application is already equipped with the `ProxyFix` middleware (configured in `app/__init__.py`). This middleware reads the `X-Forwarded-Proto`, `X-Forwarded-For`, `X-Forwarded-Host`, and `X-Forwarded-Prefix` headers set by the proxy, ensuring that Flask's URL generation (e.g., for redirects and OAuth callbacks) works correctly.

### Google OAuth Configuration (Google Cloud Console)
For Google OAuth to function correctly when the application is behind a reverse proxy and accessed via a custom domain:
- **Authorized redirect URIs**: You must configure the "Authorized redirect URIs" in your Google Cloud Console project for your OAuth 2.0 client. This URI should match the path where Google will send the user back after authentication. Given the application's setup, this will be:
  ```
  https://yourdomain.com/auth/google/authorized
  ```
  Replace `yourdomain.com` with your actual domain name.

### Flask-Dance Configuration
-   **Credentials**: The `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are no longer set directly in `app/auth.py`. Instead, they are loaded from `app.config` (which is populated from `config.py`, `instance/config.py`, or environment variables as described in the "Configuration" section). Ensure these are correctly set in your `instance/config.py` or environment variables.
-   **`authorized_url`**: This is set to `"/authorized"` within the `make_google_blueprint` configuration in `app/auth.py`. Combined with the blueprint's prefix (`/auth/google`), this forms the path part of the redirect URI (`/auth/google/authorized`) that Google uses. The application will correctly construct the full redirect URL based on the incoming request's host and scheme (thanks to `ProxyFix`).
