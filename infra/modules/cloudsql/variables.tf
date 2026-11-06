variable "project_id" {
  description = "Project that owns the Cloud SQL instance."
  type        = string
}

variable "region" {
  description = "Region for the Cloud SQL instance."
  type        = string
}

variable "name" {
  description = "Name of the Cloud SQL instance."
  type        = string
}

variable "network_self_link" {
  description = "Self link of the VPC network used for the private IP."
  type        = string
}

variable "tier" {
  description = "Machine tier for the instance."
  type        = string
  default     = "db-custom-1-3840"
}

variable "availability_type" {
  description = "ZONAL or REGIONAL (high availability)."
  type        = string
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.availability_type)
    error_message = "availability_type must be ZONAL or REGIONAL."
  }
}

variable "disk_size_gb" {
  description = "Initial disk size in GB."
  type        = number
  default     = 10
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
  description = "Password for the database user."
  type        = string
  sensitive   = true
}
