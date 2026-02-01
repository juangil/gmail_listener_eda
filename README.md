
# 📂 Gmail Email Processor: EDA(Event-Driven Architecture) (Pub/Sub + Cloud Functions + Terraform)

This project automates email processing by using **Google Cloud Functions (2nd Gen)** to listen for Gmail notifications via **Pub/Sub**.
This is designed to listen to personal emails only. The emails read by this are then forwarded to another API for further processing.

Useful for personal applications/automations that involve your email inbox. This is still in devleopment, DO NOT USE for production
deployments.

## 🛠️ Infrastructure Overview

| Service | Role in your Project | Why it's Critical |
| :--- | :--- | :--- |
| Cloud Functions (Gen 2) | The Logic Engine | Hosts your Python code. Built on Cloud Run for better performance and scaling. |
| Pub/Sub | The Message Bus | Receives pings from Gmail. Decouples Gmail's alert from your code's execution. |
| Eventarc | The Event Router | The "plumbing" that connects Pub/Sub to your Gen 2 function using the CloudEvents standard. |
| Secret Manager | The Vault | Stores your sensitive GMAIL_CLIENT_SECRET and REFRESH_TOKEN safely. |
| Firestore | The Database | A serverless NoSQL database where you store history ID of processed emails |
| Cloud Build | The Constructor | Automatically turns your Python source code into a container image during deployment. |
| Artifact Registry | The Garage | Stores the container images created by Cloud Build. |

Please Check [Infrastructure notes and learnings section](#infrastructure-notes-and-learnings) in case you want to see more of the rationale
behind the configurations of these services in the `terraform/main.tf` file.

## 📂 Project Structure

```text
gmail_fetcher/
├── cloud_function/               # 🧠 The Brain: Python source code for the Cloud Function
│   └── main.py                   # Contains the `process_gmail_notification` logic
│   └── requirements.txt          # Contains libaries you need to run your cloud function
├── credentials_setup_script/.    # 🔑 Auth: Scripts to generate the initial OAuth tokens necessary to listen to your email
│   └── setup_script.py           # Runs locally to authorize access to your Gmail
├── setup_watch/                  # 📡 Connection: Configures Gmail to talk to Pub/Sub
│   └── setup_watch.py            # Calls the Gmail API watch() method
├── terraform/                    # 🏗️ Infrastructure: Terraform configuration files
│   ├── main.tf                   # Defines all GCP resources (Function, Pub/Sub, Secrets)
│   └── variables.tf              # Input variables
│   └── terraform.tfvars.example  # Value Setting Example for your terraform Inpu Variables
├── test_utils/                   # 🧪 Testing: Utilities for fetching real email samples
│   ├── get_email_sample.py       # Downloads raw JSON of a specific email ID useful for testing your flow with real emails
├── test_local.py                 # 🏃 Local Run: Simulates a Pub/Sub event locally
├── test_sample_email.py          # 🧪 Test: Mocks the full flow with a sample email
├── test_ping_prod.py             # 🧪 Test: Sends a ping to your cloud function useful for debugging
└── README.md                     # 📖 Documentation
```

## Make sure you have

* An active google cloud account.
* An active google cloud project.
* An active Gmail Account.
* gcp cli installed in your terminal

---

# 🚀 Deployment Guide

make sure you install everything in `cloud_function/requirements.txt`

## Setting Up your terminal

make sure you run the following command with your project id.

```bash
gcloud config set project <YOUR_PROJECT_ID>

```

make sure you set your authorization default credentials to be the ones of this project. this will
prompt you to your web browser. This is important to run your terraform files as well as to facilitate
other things such as login to firestore.

```bash
gcloud auth application-default login

```

## 🔑 Generating Google OAuth 2.0 Credentials

This is how you will allow your pub/sub topic to "hear" your email inbox, as well as your cloud function to
fetch specific email data.

1. **Go to the Google Cloud Console**: Navigate to the **APIs & Services > Credentials** page.
2. **Configure Consent Screen**: If you haven't done this, Google will prompt you. Set the user type to **External** and add your own email as a **Test User**.
3. Do not forget to add your gmail account as part of the test users under the audience section.
4. **Create Credentials**: Click `+ CREATE CREDENTIALS` at the top and select **OAuth client ID**.
5. **Application Type**: For a script that runs on your machine to generate the initial token, choose **Desktop App**. 💻
6. **Download JSON**: Once created, click the **Download icon** (down arrow) next to your new Client ID to get the `client_secret_xxx.json` file.

### Why "Desktop App" for a Cloud Function?

It might seem strange to choose "Desktop App" for a system that will live in the cloud. We do this because we need a way to run a one-time
local script that opens a browser window for you to click "Allow." This is the only way to generate that first **Refresh Token**.
Once we have it, we move it to the cloud (Secret Manager), and the "Desktop" part of the process is over.

---

Once you have that JSON file downloaded, we have everything we need to generate your long-term token.

## 🔑 Generating Refresher Token

Run your local script `credentials_setup_script/setup_script.py` to generate refresh token (authorizes scopes). This
Script should read the `credentials.json` or `token.json` that you just downloaded. Make sure that file is the same that
you just downloaded in the previous step.

**Understanding the Output**
When you run this, a browser tab will pop up. You might see a "Google hasn't verified this app" warning.
Since you are the developer and the only user, you can click Advanced > Go to [Your App Name] (unsafe).

Once you finish, the script will print three strings to your terminal.
These are the values we will put into GCP Secret Manager using Terraform. Please make sure you copy them as you will need
them to set infrastructure with Terraform.

**Important Note**: This Refresher Token expires after 7 days. To avoid this you need to publish your app in your Configure Consent Screen
in Google Cloud Console. DO THIS ONLY IN PRODUCTION MODE. Go to Google Cloud Console -> Into your project -> APIs and Services -> OAuth Consent Screen
-> Publish Your App.

---

## Deploying in Terraform

Dont forget to crate your `terraform.tfvars` file, the repo provided and example of this file structure under the terraform folder.
There you will need to input your google project and respective credentials to setup the watch from pub/sub.

3. **Terraform Apply**:
```bash
terraform plan
terraform apply

```

You are going to have to enable a lot of services as you run Terraform Apply. TO DO: Add a way to enable
services automatically.

## Destroying infrastructure

You can use terraform destroy command. However, there's a lot of dependencies that can generate a lot of headache if
not handled properly. My suggestions is for run the destroy command, delete the google project you were working on
and start with a fresh one, not ideal, but hopefully I can add workarounds to this soon.

---

## Setup Watch Function

running the commands above creates all the infrastructure needed, nevertheless you still need to add a way
for your pub/Sub topic to "listen" your email notifications. You can do this once by running the
`setup_watch/setup_watch.py` very important to pass the credentials you generated in the steps before.

Please create a `.env` file following this structure before you run it. You need the following configuration variables
for it to be able to setup a watch from pub/sub under your email inboxes.

```bash
EMAIL_FETCHING_LABELS="<Comma Separated names of the inboxes you want to listen, inf not present defaults to inbox>"

GMAIL_CLIENT_ID="<Very alphanumeric string>.apps.googleusercontent.com"
GMAIL_CLIENT_SECRET="GOC....."
GMAIL_REFRESH_TOKEN="1//refres-token"

PROJECT_ID="id-of-your-project"
```

The link between your Gmail account and Pub/Sub is established through a process called the **Gmail API `watch()` request**.


### How the Connection Works

1. **Authorization:** You use the **Refresh Token** and **Client ID** to prove to Google that your code has permission to access your email.
2. **The `watch()` Call:** Your code sends a request to the Gmail API saying: *"Please notify the Pub/Sub topic `projects/your-project/topics/gmail-notifications-topic` whenever a new message arrives in my inbox."*
3. **Permissions:** Because of that IAM binding we added in Terraform (`gmail-api-push@system.gserviceaccount.com`), Gmail has the "key" to enter your Pub/Sub topic and drop off a notification.

### Verifying the Setup

You can't just set it and forget it, because a `watch()` request has a limited lifespan—usually **7 days**.
After that, Gmail stops sending notifications unless you "renew" the watch. ⏳

To be 100% sure it's working, you can perform a manual check:

* **The Initial Call:** We'll write a small Python snippet (or include it in your Cloud Function's startup) that calls `watch()`.
* **Sepcific Email Labels:** you can specify in the watch which specific inboxes you would like your email sending notifications from.
* **The Response:** If successful, the Gmail API returns a `historyId` and an `expiration` timestamp. This is your confirmation that the "bridge" is active.

by running `setup_watch/setup_watch.py` you get an `historyId` and  the `expiration` timestamp that you can use for local testing your function.

### Important Note: How to approach the "Renewal" problem (NOT IMPLEMENTED ON THIS REPO YET).

Since the watch expires every 7 days, we have a few options for keeping it alive:

1. **Cloud Scheduler:** Set up a "cron job" that triggers your function once a day to simply call `watch()` again. ⏰
2. **Self-Healing Logic:** Every time your Cloud Function processes a real email, it can check the current time and "re-up" the watch if it's nearing expiration.

---

## 🔥 Why Firestore? (The "Memory" of the Project)

In a serverless environment like **Google Cloud Functions**, your code is **stateless**. This means once the function finishes processing an email, it disappears. Without Firestore, it wouldn't know what it did two minutes ago.

### 1. The "Delta" Strategy (Efficiency)

Gmail doesn't just send you the new email; the notification tells you "something changed."

* **The Problem:** If you don't know where you left off, you'd have to scan your whole inbox every time.
* **The Firestore Solution:** We store the `history_id` of the last email we processed. Next time the bot wakes up, it asks Gmail: *"What happened between **Last_ID** and now?"*

### 2. Preventing Double-Spending (Idempotency)

Sometimes Pub/Sub sends the same notification twice (it happens!). This can happen if two emails arrive at the same time or miliseconds between one and another.

* **The Firestore Solution:** Before doing anything, the bot checks Firestore. If the `history_id` in the notification is older than or equal to the one in our "Memory," the bot says *"I've already seen this"* and shuts down immediately. This saves you money and prevents duplicated email processing.

---

## 🧪 Local Testing: Simulating a Pub/Sub Event

You can test your function logic without the need of deploying in the cloud by simulating a pyub/sub event.

### 1. Using Functions Framework (Recommended)

Run the function locally on your machine, for this we will use the `cloud_function.py` script and  `test_local.py`
script. The latter mimics the pub/sub message structure. Also you can use a real HistoryID, from your `setup_watch/setup_watch.py`
script. 

The `test_local.py` emulates a pub/sub notification and will fetch the emails after HistoryID. Thus After running

**Note**: Take into account that for running the setup watch script you will need a pub/sub topic and subscription
already up and running. (TO DO): Create a testing terraform file that facilitates testing with one single mock-test topic
created.

```bash
# Install framework
pip install functions-framework

# Start local server (target your entry point function: the function name inside cloud_function.py)
functions-framework --target=process_gmail_notification --debug

```

Fire the Trigger: In a second terminal, run your test script:

```bash
python setup_watch/setup_watch.py
# Copy the history ID generated by this script
# Send yourself an email to your own account and then Run
python test_local.py
```

After this you should be able to see your cloud function working in local and forwarding your message to
the other API that you have running. In my case, I created a mock server with flask and connected Via Webhook
with ngrok. Nevertheless you can do it with localhost.

## 🧪 Local Testing: Simulating with specific emails

The approach above is useful when you want to test simple emails. However, what if you wanna try and test
with other type of emails such as bank transactions, you are not going to charge your credit card every
time you want to test something. That's why there are two useful scripts here `test_utils/get_email_sample.py`
and `test_sample_email.py`.

Make sure you have the credentials generated in the first steps, those will serve well here. Add those Credentials
as environment variables in `test_utils/.env`. 

```bash
# test_utils/.env
GMAIL_REFRESH_TOKEN="your refresh token"
GMAIL_CLIENT_ID="your client id"
GMAIL_CLIENT_SECRET="your secret"
```

Now to get an specific email sample you need to follow the next steps:

Go to the browser -> Open Message you want to fetch -> click on the 3 dots -> click in show original -> Copy Message ID.

Use that Message ID when running the following command inside `test_utils/`:

```bash
python get_email_sample.py <Message ID> 
```

A `test_utils/sample_msg.json` file with your message, just as your cloud function would receive it will be created.

Afterwards you can run the following command, it will automatically open the sample message we just fetched
and mock the complete lambda function flow to send it over to another location you define.

```bash
python test_sample_email.py
```

This file mocks the push notification from pub/sub and all the firestore DB calls.

---

## Infrastructure Notes and Learnings

Here is the chronological flow of an email notification. It transitions from a physical action in your inbox to an automated process in Google Cloud.
This can help you understad what is happening under the hood and the rationale behind definitions in `terraform/main.tf`

### 📬 The Gmail-to-Cloud Function Life Cycle

#### 1. The Trigger Event (In your Inbox)

* **Action**: A new email arrives or a label is applied (e.g., your bank sends a transaction alert).
* **Gmail Internal Check**: Gmail checks if there is an active `watch()` request for this user. This is the one
we set in `setup_watch/setup_watch.py`.
* **The Notification**: Gmail’s internal "Push" service identifies your **Pub/Sub Topic** as the destination.

#### 2. The Handshake (Gmail → Pub/Sub)

* **Publisher**: Gmail’s system service account (`gmail-api-push@system...`) sends a message to your `gmail-notifications-topic`.
* **Message Payload**: This is a "lightweight" ping. It **does not** contain the email body. It only contains:
* `emailAddress`: Your email.
* `historyId`: A numerical ID representing the latest state of your mailbox.
* **Acknowledgment**: Pub/Sub receives the message and tells Gmail, "Got it, I'll take it from here."

**Note**: Since this is just a ping, you still need to do process in your cloud function to read new emails arriving after `historyId`.

#### 3. The Routing (Pub/Sub → Eventarc)

* **The Bridge**: Because you are using **Gen 2**, an **Eventarc Trigger** is sitting between Pub/Sub and your function.
* **CloudEvent Conversion**: Eventarc picks up the Pub/Sub message and wraps it in a **CloudEvent** wrapper—a standardized format used for modern serverless architectures.

#### 4. The Invocation (Eventarc → Cloud Run/Function)

* **The Knock**: Eventarc makes an **HTTPS POST** request to your function’s underlying Cloud Run URL.
* **Identity Check**: This is where the **IAM Invoker** roles we set up are tested. Cloud Run checks if Eventarc has the "badge" to enter.
* **Scale Up**: If your function was "cold" (sleeping), Cloud Run spins up a container instance in milliseconds to handle the request.

#### 5. The Execution (Inside your Python Code)

* **Entry Point**: Your `process_gmail_notification(cloud_event)` function begins.
* **Fetching the Data**: Since the ping was lightweight, your code now uses the `historyId` to call the **Gmail API** (via the `readonly` scope) to ask: *"What specifically changed since this ID?"*
* **The Processing**:
1. Your code identifies the new **Message ID**.
2. It forward its to another location.

* **The Database**: `historyId` is saved to **Firestore** to keep track of what we have already processed.

#### 6. Completion & Cleanup

* **Response**: Your function returns an `HTTP 200 OK`.
* **Scale Down**: After a period of inactivity, the Cloud Run instance shuts down to save you money.
* **Ack**: Pub/Sub sees the success and deletes the notification from the queue.

### 📬 The Gmail-to-Cloud Function Life Cycle

---

## 🚧 Common Issues & Workarounds

* **Service Account 404**: Ensure the **Compute Engine API** is enabled. If the default account was deleted, restore it using its Unique ID:
`gcloud beta iam service-accounts undelete [ID]`
* **Permission Denied (Secrets)**: The service account must have `roles/secretmanager.secretAccessor` on the specific secret.
* **deleted_client Error**: Occurs if the OAuth Client ID is removed. Delete `token.json` and re-authenticate with a new `credentials.json`.
