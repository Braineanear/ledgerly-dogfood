variable "project_id" {
  description = "Google Cloud project ID for the infrastructure."
  type        = string
}

variable "region" {
  description = "Google Cloud region for the infrastructure."
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "Name of the storage bucket. Must be globally unique."
  type        = string
}
