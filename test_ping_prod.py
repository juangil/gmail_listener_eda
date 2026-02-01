import json
import base64
from google.cloud import pubsub_v1

# SET THESE VALUES
PROJECT_ID = "your-project-id"
TOPIC_ID = "gmail-notifications-topic"

def simulate_gmail_notification():
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

    # This mimics the exact JSON structure Gmail sends
    data = {
        "emailAddress": "your-email@gmail.com",
        "historyId": "12345678"
    }
    
    # Convert to string and then to bytes
    message_json = json.dumps(data)
    message_bytes = message_json.encode("utf-8")

    print(f"Publishing message to {topic_path}...")
    
    future = publisher.publish(topic_path, data=message_bytes)
    print(f"Published! Message ID: {future.result()}")

if __name__ == "__main__":
    simulate_gmail_notification()