import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# This scope allows us to read, send, and delete emails. 
# For your processing system, 'readonly' might be safer if you don't need to delete.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def generate_refresh_token():
    # Load the credentials you just downloaded
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    
    # This opens your browser for manual login
    creds = flow.run_local_server(port=0)

    # This is the "Gold" we are looking for
    print(f"Refresh Token: {creds.refresh_token}")
    print(f"Client ID: {creds.client_id}")
    print(f"Client Secret: {creds.client_secret}")

if __name__ == '__main__':
    generate_refresh_token()