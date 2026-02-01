"""
Setup watch script. This only has to be run the first time.
afterwards there will be a watch renewal logic inside the cloud function code.
Pub/sub topics need to be renewed every 7 days to watch email events.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from google.cloud import firestore

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

def setup_gmail_watch():
    # 1. Prepare Credentials
    load_dotenv()
    email_fetching_labels_raw = os.getenv('EMAIL_FETCHING_LABELS', [])
    email_fetching_labels = [label.strip() for label in email_fetching_labels_raw.split(",") if label]
    print(os.environ.get('GMAIL_CLIENT_ID'))
    creds = Credentials(
        token=None,
        refresh_token=os.environ.get('GMAIL_REFRESH_TOKEN'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get('GMAIL_CLIENT_ID'),
        client_secret=os.environ.get('GMAIL_CLIENT_SECRET'),
    )

    # 2. Refresh the token
    if not creds.valid:
        creds.refresh(Request())

    # 3. Build Gmail Service
    service = build('gmail', 'v1', credentials=creds)

    # 4. Define the Pub/Sub Topic
    # Format: projects/{project_id}/topics/{topic_name}
    topic_name = f"projects/{os.environ.get('PROJECT_ID')}/topics/gmail-notifications-topic"

    label_id_list = get_label_id(service, email_fetching_labels)

    labels_to_listen = ['INBOX'] if len(label_id_list) == 0 else label_id_list

    print(labels_to_listen)

    body = {
        'topicName': topic_name,
        'labelIds': labels_to_listen
    }

    # 5. Execute the Watch request
    try:
        response = service.users().watch(userId='me', body=body).execute()
        initial_id = response.get('historyId')
        print("Successfully established watch!")
        print(f"History ID: {initial_id}")
        print(f"Expiration (ms): {response.get('expiration')}")
        db = firestore.Client(project=os.environ.get('PROJECT_ID'))
        db.collection('state').document('gmail_sync').set({
            'last_id': int(initial_id)
        })
        print("Firestore seeded successfully. Ready for notifications! 🚀")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    setup_gmail_watch()