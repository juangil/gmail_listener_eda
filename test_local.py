import requests
import base64
import json

# The local URL where your function will be running
LOCAL_URL = "http://localhost:8080"

def send_mock_push(mock_history_id):
    # 1. Create the Gmail notification payload
    gmail_data = {
        "emailAddress": "user@example.com",
        "historyId": mock_history_id
    }
    
    # 2. Base64 encode it (just like Pub/Sub does)
    encoded_data = base64.b64encode(json.dumps(gmail_data).encode('utf-8')).decode('utf-8')
    
    # 3. Create the CloudEvent wrapper
    mock_event = {
        "message": {
            "data": encoded_data,
            "messageId": "12345"
        }
    }

    # 3. Add CloudEvent Headers 🌐
    headers = {
        "ce-id": "1234567890",
        "ce-specversion": "1.0",
        "ce-type": "google.cloud.pubsub.topic.v1.messagePublished",
        "ce-source": "//pubsub.googleapis.com/projects/sample-project/topics/sample-topic",
        "Content-Type": "application/json"
    }

    print(f"Sending mock notification for History ID: {mock_history_id}...")
    
    try:
        response = requests.post(LOCAL_URL, json=mock_event, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Use a real history ID from your 'setup_watch.py' output to test actual fetching!
    hid = input("Enter a valid historyId to test fetching: ")
    send_mock_push(hid)