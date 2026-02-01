import sys
import os
import json
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load environment variables (GMAIL_REFRESH_TOKEN, etc.)
load_dotenv()

def get_gmail_service():
    """Authorizes the Gmail API using Refresh Tokens from Secret Manager."""
    creds = Credentials(
        token=None,
        refresh_token=os.environ.get('GMAIL_REFRESH_TOKEN'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get('GMAIL_CLIENT_ID'),
        client_secret=os.environ.get('GMAIL_CLIENT_SECRET'),
    )
    if not creds.valid:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)


def fetch_email_sample(message_id):
    """
    Fetches a real email from Gmail and saves it in sample_msg.json
    file. It is ready to be used in testing.
    """
    print(f"🔍 Fetching email ID: {message_id}...")
    
    try:
        # 1. Authenticate using the same logic as the Cloud Function
        service = get_gmail_service()

        # Search for the message by subject to find the correct Hex ID
        query = f"rfc822msgid:{message_id}"
        response = service.users().messages().list(userId='me', q=query).execute()

        if 'messages' in response:
            api_id = response['messages'][0]['id']
            print(f"Use this ID for your GET request: {api_id}")
        else:
            print("No message found with that search.")
        
        # 2. Parse the message using the Cloud Function's parser
        msg = service.users().messages().get(userId='me', id=api_id, format='full').execute()
        
        # 3. Output the result
        file_name = f"sample_msg.json"
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(msg, f, indent=4, ensure_ascii=False)
        print(f"Saved email to {file_name}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Ensure your .env file contains valid GMAIL credentials.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_email_sample.py <HEX ID>")
        print("Tip: You can find the Message HEX ID in the Gmail original message view.")
        print("Go to the browser -> Open Message you want to fetch -> click on the 3 dots -> click in show original -> Copy Message ID")
    else:
        fetch_email_sample(sys.argv[1])
