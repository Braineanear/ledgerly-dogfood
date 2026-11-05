terraform {
  required_version = ">= 1.6.0"

  # Partial backend config: the bucket and prefix are supplied at init
  # through -backend-config=backend.hcl.
  backend "gcs" {}

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
}
