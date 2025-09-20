import os
from decouple import config
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    # Load client config from .env
    client_config = {
        "installed": {
            "client_id": config("GOOGLE_CLIENT_ID"),
            "client_secret": config("GOOGLE_CLIENT_SECRET"),
            "auth_uri": config("GOOGLE_AUTH_URI"),
            "token_uri": config("GOOGLE_TOKEN_URI"),
            "auth_provider_x509_cert_url": config("GOOGLE_AUTH_PROVIDER_CERT_URL"),
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }

    # Define the scope for Google Sheets read access
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    # Run the console-based OAuth2 flow
    flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
    creds = flow.run_local_server(port=8765)

    # Print values for .env
    print("\n# Paste these into your .env")
    print(f"GOOGLE_ACCESS_TOKEN={creds.token}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print(f"GOOGLE_TOKEN_URI={creds.token_uri}")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_AUTH_PROVIDER_CERT_URL={client_config['installed']['auth_provider_x509_cert_url']}\n")

if __name__ == "__main__":
    main()