# DnDadventure
One player DnD adventure using Gemini as a storyteller

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

### Flask-Dance Configuration (`app/auth.py`)
The following settings in `app/auth.py` are relevant for Google OAuth:
-   **`client_id` and `client_secret`**: These must be replaced with your actual credentials obtained from the Google Cloud Console. The current placeholders are:
    -   `client_id="YOUR_CLIENT_ID_FROM_USER_JSON"`
    -   `client_secret="YOUR_CLIENT_SECRET_FROM_USER_JSON"`
-   **`authorized_url`**: This is set to `"/authorized"` within the `make_google_blueprint` configuration. Combined with the blueprint's prefix (`/auth/google`), this forms the path part of the redirect URI (`/auth/google/authorized`) that Google uses. The application will correctly construct the full redirect URL based on the incoming request's host and scheme (thanks to `ProxyFix`).
