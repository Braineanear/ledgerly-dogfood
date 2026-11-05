provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_storage_bucket" "main" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }
}
