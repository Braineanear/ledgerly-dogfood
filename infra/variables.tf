variable "project_id" {
  description = "Google Cloud project ID for future infrastructure."
  type        = string
}

variable "region" {
  description = "Google Cloud region for future infrastructure."
  type        = string
  default     = "us-central1"
}
