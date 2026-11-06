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

variable "subnet_cidr" {
  description = "Primary IPv4 CIDR range of the VPC subnet."
  type        = string
  default     = "10.10.0.0/24"
}

variable "db_tier" {
  description = "Machine tier of the Cloud SQL instance."
  type        = string
  default     = "db-custom-1-3840"
}

variable "db_name" {
  description = "Name of the database to create."
  type        = string
  default     = "ledgerly"
}

variable "db_user" {
  description = "Name of the database user to create."
  type        = string
  default     = "ledgerly"
}

variable "db_password" {
  description = "Password for the database user. Supply it via TF_VAR_db_password; never commit it."
  type        = string
  sensitive   = true
}
