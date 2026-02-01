import base64
import json
import logging
import os
import requests
import re
import html
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import functions_framework
from google.cloud import firestore

# 🛠️ Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to hold the DB client
_db = None

def get_db():
    # The client automatically finds your credentials 
    # when running inside Google Cloud
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db

@firestore.transactional
def update_in_transaction(transaction, doc_ref, new_id):
    """
        In a Cloud Function environment, things happen very fast and often in parallel.
        The @firestore.transactional decorator is our "safety officer" 🛡️ that prevents two different
        instances of your function from tripping over each other when they try
        to update the same piece of data.
    """
    snapshot = doc_ref.get(transaction=transaction)
    current_id = int(snapshot.get('last_id'))
    
    # 🏁 The "Moving Forward" Rule
    if new_id > current_id:
        transaction.update(doc_ref, {'last_id': new_id})
        print(f"Update successful: {new_id}")
    else:
        print(f"Update skipped: {new_id} is older than {current_id}")


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

def get_label_id(service, label_list):
    """Find label ID by name"""
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    label_id_list = []

    for label_name in label_list:
        for label in labels:
            if label['name'] == label_name:
                label_id_list.append(label['id'])
    
    return label_id_list


def parse_message(service, msg_id):
    """Retrieves and extracts specific fields from an email."""
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    #print(msg)
    payload = msg.get('payload', {})
    headers = payload.get('headers', [])
    
    # 🏷️ Extract Metadata
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
    
    # 🕒 Convert internalDate (ms) to readable format
    timestamp = int(msg.get('internalDate')) / 1000
    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        "message_id": msg_id,
        "subject": subject,
        "from": sender,
        "date": date_str,
        "body": payload
    }

def forward_to_backend(email_data):
    """POSTs the cleaned data to your backend."""
    url = os.environ.get('BACKEND_URL')
    api_key = os.environ.get('BACKEND_API_KEY')
    #headers = {"X-API-KEY": api_key}
    print(email_data)
    response = requests.post(url, json=email_data, timeout=10)
    response.raise_for_status()
    logger.info(f"✅ Forwarded {email_data['message_id']} to backend.")

@functions_framework.cloud_event
def process_gmail_notification(cloud_event):
    """Entry point triggered by Pub/Sub via Eventarc."""
    try:
        db = get_db()
        # finding Last History ID in Firestore
        # Create a reference to the specific document
        doc_ref = db.collection('state').document('gmail_sync')
        # Get a "snapshot" of the document
        doc = doc_ref.get()

        if not doc.exists:
            print("No state found. Please run the setup script to seed Firestore.")
            return

        last_processed_id = int(doc.to_dict().get('last_id', 0))

        print(f"Processing Pub/Sub event")
        print(f"sending it to {os.environ.get('BACKEND_URL')}")
        # 1. Extract historyId from the Pub/Sub payload
        # The cloud_event.data['message']['data'] is base64 encoded
        pubsub_data = base64.b64decode(cloud_event.data["message"]["data"]).decode('utf-8')
        notification = json.loads(pubsub_data)
        new_history_id = notification.get('historyId')
        
        print(f"🔔 Notification received. History ID: {new_history_id}")
        
        service = get_gmail_service()

        # Get specific Labels you want to process
        # Even though the watch() method in setup_watch.py has a labelIds parameter,
        # Gmail often ignores it and sends a notification for every single change in
        # the mailbox—including drafts, sent mail, and chats. It's frustrating, but it's consistent.
        # This is a bug reported since 2015 apparently. thus you need to add this filtering logic here.
        email_fetching_labels_raw = os.environ.get('EMAIL_FETCHING_LABELS', [])
        email_fetching_labels = [label.strip() for label in email_fetching_labels_raw.split(",") if label]

        label_id_list = get_label_id(service, email_fetching_labels)

        # 2. Get the list of changes since that historyId

        # sometimes you need to convert to a valid int because
        # If the value is being passed through multiple layers of JSON encoding or terminal commands,
        # it might be getting "double-escaped" or treated as a special string.
        # To fix this properly, we need to ensure the ID is treated as a number (integer)
        # by the time it reaches the Gmail API client.
        new_history_id = int(new_history_id)

        if new_history_id <= last_processed_id:
            print(f"No new changes. Current ID {new_history_id} is not newer than {last_processed_id}")
            return

        print(f"New activity detected! Syncing from {last_processed_id} to {new_history_id}")

        history_response = service.users().history().list(
            userId='me', 
            startHistoryId=last_processed_id,
            historyTypes=['messageAdded']
        ).execute()

        print(history_response)

        # 3. Process each new message found
        history_records = history_response.get('history', [])
        print(f"history records added processing: {len(history_records)}")
        for record in history_records:
            messages_added = record.get('messagesAdded', [])
            print(f"messages added processing: {len(messages_added)}")
            for item in messages_added:
                labels_in_message = set(item.get('message', {}).get('labelIds', []))
                common_labels = labels_in_message.intersection(set(label_id_list))
                msg_id = item['message']['id']

                if len(common_labels) == 0:
                    print(f"📧 Not Processing message {msg_id} as not present in {label_id_list}")
                else:
                    # 4. Clean and Forward
                    print(f"📧 Processing message {msg_id}")
                    clean_email = parse_message(service, msg_id)
                    forward_to_backend(clean_email)
        
        # 5. Update Firestore with the new "High Water Mark"
        # doc_ref.update({'last_id': new_history_id})
        transaction = db.transaction()
        update_in_transaction(transaction, doc_ref, new_history_id)
        print(f"Successfully updated last_id to {new_history_id}")

    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        # Raising the error allows Pub/Sub to retry the delivery
        raise e