variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "project_number" {
  description = "GCP Project Number"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "gmail_user_email" {
  description = "Gmail email address to monitor"
  type        = string
}

variable "gmail_client_id" {
  type      = string
  sensitive = true
}

variable "gmail_client_secret" {
  type      = string
  sensitive = true
}

variable "gmail_refresh_token" {
  type      = string
  sensitive = true
}

variable "gmail_fetching_labels" {
  type      = string
  sensitive = true
}

variable "backend_url" {
  type      = string
  sensitive = true
}