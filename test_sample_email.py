import base64
import json
import os
import sys
from unittest.mock import MagicMock, patch

# 1. Setup path to import the cloud function
# We need to add the 'cloud_function' folder to the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
cloud_function_dir = os.path.join(current_dir, 'cloud_function')
sys.path.append(cloud_function_dir)

# 2. Mock environment variables required by main.py
# These must be set before importing main if main reads them at module level,
# or just to ensure functions don't crash.
os.environ['GMAIL_REFRESH_TOKEN'] = 'mock_refresh_token'
os.environ['GMAIL_CLIENT_ID'] = 'mock_client_id'
os.environ['GMAIL_CLIENT_SECRET'] = 'mock_client_secret'

# Set these to your real backend details or export them in your shell before running
if 'BACKEND_URL' not in os.environ:
    os.environ['BACKEND_URL'] = 'http://127.0.0.1:8000'
if 'BACKEND_API_KEY' not in os.environ:
    os.environ['BACKEND_API_KEY'] = 'your-real-api-key'

# 3. Import main safely
# We patch firestore.Client to prevent real connection attempts during import
# because main.py initializes 'db = firestore.Client()' at the module level.
with patch('google.cloud.firestore.Client'):
    import main


def create_mock_gmail_message(msg_id="msg_123"):
    """
    Creates a mock Gmail API message resource.
    This mimics the JSON structure returned by service.users().messages().get()

    Using a real email from your inbox. extracted using test_utils/get_email_sample.py

    """
    json_path = os.path.join(current_dir, 'test_utils', 'sample_msg.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        msg = json.load(f)
        msg['id'] = msg_id
        return msg

def test_email_notification_to_backend_flow():
    print(f"🧪 Starting Test")

    # --- Mocks Setup ---
    
    # 1. Mock Firestore (State Management)
    mock_firestore = MagicMock()
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {'last_id': 1000} # Current state in DB
    
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_firestore.collection.return_value.document.return_value = mock_doc_ref

    # 2. Mock Gmail Service (API Calls)
    mock_service = MagicMock()
    
    # Mock history.list() to return one new message
    mock_service.users().history().list.return_value.execute.return_value = {
        "history": [
            {
                "messagesAdded": [
                    {"message": {"id": "msg_123", "threadId": "thread_123"}}
                ]
            }
        ]
    }
    
    # Mock messages.get() to return our template
    mock_service.users().messages().get.return_value.execute.return_value = create_mock_gmail_message()

    # 4. Construct the CloudEvent (Pub/Sub Trigger)
    # The function expects a historyId (1005) > last_id (1000) to trigger processing
    new_history_id = 1005
    pubsub_msg = {
        "emailAddress": "user@example.com",
        "historyId": new_history_id
    }
    encoded_data = base64.b64encode(json.dumps(pubsub_msg).encode('utf-8')).decode('utf-8')
    
    class MockCloudEvent:
        data = {
            "message": {
                "data": encoded_data,
                "messageId": "event_id_1"
            }
        }

    # --- Execution ---
    
    # Patch dependencies in cloud_function/main.py
    # We patch 'main.db' specifically because it is a module-level variable
    with patch('main._db', mock_firestore), \
         patch('main.get_gmail_service', return_value=mock_service), \
         patch('main.update_in_transaction'): # Skip complex transaction logic for this test
        
        try:
            main.process_gmail_notification(MockCloudEvent())
            print("✅ Function executed without errors.")
        except Exception as e:
            print(f"❌ Function failed: {e}")
            return

    # --- Verification ---
    print("\n🔍 Verification:")
    print(f"Request sent to: {os.environ['BACKEND_URL']}")
    print("Check your real backend logs to confirm receipt of the payload.")

if __name__ == "__main__":
    test_email_notification_to_backend_flow()
