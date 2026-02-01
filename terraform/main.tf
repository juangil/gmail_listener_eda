
# PROVIDER & PROJECT DATA
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "project" {}

# ENABLE APIs (The Foundation)
resource "google_project_service" "gcp_services" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "eventarc.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
    "gmail.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# FORCE SERVICE IDENTITIES
# This block forces Google to create the "Robot" accounts immediately
# Adding this prevents issues when creatinng the connection between
# Pub/Sub and the cloud gen 2 Function
resource "google_project_service_identity" "eventarc_identity" {
  provider = google-beta
  project  = var.project_id
  service  = "eventarc.googleapis.com"
  depends_on = [google_project_service.gcp_services]
}

resource "google_project_service_identity" "pubsub_identity" {
  provider = google-beta
  project  = var.project_id
  service  = "pubsub.googleapis.com"
  depends_on = [google_project_service.gcp_services]
}

# CREATE SERVICE ACCOUNT (The Identity)
resource "google_service_account" "function_account" {
  account_id   = "gmail-processor-sa"
  display_name = "Gmail Processor Service Account"
}

# CREATE BUCKET TO STORE CODE
resource "google_storage_bucket" "email_listener_code_bucket" {
  name     = "${var.project_id}-gcf-source" # Buckets must be globally unique
  location = var.region
  force_destroy = true # Allows terraform to delete the bucket even if it has files
}

# SECRET MANAGER: Store the Refresh Token
resource "google_secret_manager_secret" "gmail_secrets" {
  for_each  = toset(["client-id", "client-secret", "refresh-token", "fetching-labels"])
  secret_id = "gmail-${each.key}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.gcp_services]
}

# CREATE SECRETS: for the backend
resource "google_secret_manager_secret" "backend_secrets" {
  for_each  = toset(["url"])
  secret_id = "backend-${each.key}"
  replication {
    auto {}
  }

  depends_on = [google_project_service.gcp_services]
}

# Add the actual data (versions) to those secrets
resource "google_secret_manager_secret_version" "gmail_secret_versions" {
  secret = google_secret_manager_secret.gmail_secrets["client-id"].id
  secret_data = var.gmail_client_id
}

resource "google_secret_manager_secret_version" "client_secret_version" {
  secret = google_secret_manager_secret.gmail_secrets["client-secret"].id
  secret_data = var.gmail_client_secret
}

resource "google_secret_manager_secret_version" "refresh_token_version" {
  secret = google_secret_manager_secret.gmail_secrets["refresh-token"].id
  secret_data = var.gmail_refresh_token
}

resource "google_secret_manager_secret_version" "fetching_labels_version" {
  secret = google_secret_manager_secret.gmail_secrets["fetching-labels"].id
  secret_data = var.gmail_fetching_labels
}

resource "google_secret_manager_secret_version" "backend_url_version" {
  secret = google_secret_manager_secret.backend_secrets["url"].id
  secret_data = var.backend_url
}

# Just add this if you are using an api key to access your backend
/*resource "google_secret_manager_secret_version" "backend_api_key" {
  secret = google_secret_manager_secret.backend_secrets["backend-api-key"].id
  secret_data = var.backend-api-key
}*/

# Enabling service account to access secrets
resource "google_secret_manager_secret_iam_member" "client_secret_access" {
  for_each  = toset(["client-id", "client-secret", "refresh-token"])
  project   = var.project_id
  secret_id = google_secret_manager_secret.gmail_secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.function_account.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_secret_access" {
  for_each  = toset(["url"])
  project   = var.project_id
  secret_id = google_secret_manager_secret.backend_secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.function_account.email}"
}

# CREATE FIRESTORE DB
resource "google_firestore_database" "database" {
  project     = data.google_project.project.project_id
  name        = "(default)"
  location_id = var.region # Match your function's location
  type        = "FIRESTORE_NATIVE"
  
  # Ensures the API is enabled before creating the DB
  depends_on = [google_project_service.gcp_services]
}

# Grant Firestore Permissions to your Service Account
resource "google_project_iam_member" "sa_firestore_user" {
  project = data.google_project.project.project_id
  role    = "roles/datastore.user" # Core role for Firestore access 🗝️
  member  = "serviceAccount:${google_service_account.function_account.email}"
}

# ROBOT & FUNCTION PERMISSIONS (The "403 Killers")
# These allow the Google-managed robots to talk to your function

# The "Everything" Loop for your Service Account
resource "google_project_iam_member" "function_iam_roles" {
  for_each = toset([
    "roles/datastore.user",              # Firestore
    "roles/secretmanager.secretAccessor", # Secrets
    "roles/cloudbuild.builds.builder",   # Execute Build
    "roles/artifactregistry.writer",     # Save Image
    "roles/storage.objectViewer",        # Read Source ZIP
    "roles/logging.logWriter",           # Write Logs
    "roles/run.invoker"                  # Allow Triggering (Gen 2)
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.function_account.email}"
}

# ROBOT IMPERSONATION (The "Handshake")
# Cloud Build needs to "Act As" your Service Account
resource "google_service_account_iam_member" "cloudbuild_act_as" {
  service_account_id = google_service_account.function_account.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

# Allow Pub/Sub to create tokens for your Service Account
resource "google_service_account_iam_member" "pubsub_token_creator" {
  service_account_id = google_service_account.function_account.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Allow Eventarc to invoke Cloud Run
resource "google_project_iam_member" "eventarc_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

# PUB/SUB & TRIGGER SETUP
resource "google_pubsub_topic" "gmail_notifications" {
  name = "gmail-notifications-topic"
  depends_on = [google_project_service.gcp_services]
}

resource "google_pubsub_topic_iam_member" "gmail_publisher" {
  topic  = google_pubsub_topic.gmail_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
}

# THE CLOUD FUNCTION (GEN 2)
resource "google_cloudfunctions2_function" "email_processor" {
  name     = "gmail-intel-processor-v5"
  location = var.region

  build_config {
    runtime     = "python310"
    entry_point = "process_gmail_notification"
    service_account = google_service_account.function_account.id # Fixes Build 404
    
    source {
      storage_source {
        bucket = google_storage_bucket.email_listener_code_bucket.name
        object = google_storage_bucket_object.email_listener_function_zip_object.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256Mi"
    timeout_seconds       = 60
    service_account_email = google_service_account.function_account.email
    ingress_settings      = "ALLOW_ALL" # Fixes Eventarc 403
    
    # Secrets from your specific configuration
    secret_environment_variables {
      key        = "GMAIL_CLIENT_ID"
      project_id = var.project_id
      secret     = google_secret_manager_secret.gmail_secrets["client-id"].secret_id
      version    = "latest"
    }
  
    secret_environment_variables {
      key        = "GMAIL_CLIENT_SECRET"
      project_id = var.project_id
      secret     = google_secret_manager_secret.gmail_secrets["client-secret"].secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "GMAIL_REFRESH_TOKEN"
      project_id = var.project_id
      secret     = google_secret_manager_secret.gmail_secrets["refresh-token"].secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "EMAIL_FETCHING_LABELS"
      project_id = var.project_id
      secret     = google_secret_manager_secret.gmail_secrets["fetching-labels"].secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "BACKEND_URL"
      project_id = var.project_id
      secret     = google_secret_manager_secret.backend_secrets["url"].secret_id
      version    = "latest"
    }
  
    /*secret_environment_variables {
      key        = "BACKEND_API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.backend_secrets["api-key"].secret_id
      version    = "latest"
    }*/

  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.gmail_notifications.id
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.function_account.email # Essential for Gen 2
  }

  depends_on = [
    google_project_service.gcp_services,
    google_project_iam_member.function_iam_roles
  ]
}

# Zip the local source code
data "archive_file" "email_listener_function_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../cloud_function" # Points to the folder containing main.py
  output_path = "${path.module}/function-source.zip"

  # List the files and directories to ignore
  excludes = [
    "__pycache__",
    ".env",
    ".pytest_cache", # If you have tests
    "venv",          # If your virtual environment is inside src
    "*.pyc"          # Any compiled python files
  ]
}

# Upload the zip to the bucket
resource "google_storage_bucket_object" "email_listener_function_zip_object" {
  name   = "source.zip#${data.archive_file.email_listener_function_zip.output_md5}" # Appending MD5 forces an update when code changes
  bucket = google_storage_bucket.email_listener_code_bucket.name
  source = data.archive_file.email_listener_function_zip.output_path
}
