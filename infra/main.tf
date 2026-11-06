provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "sqladmin" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "servicenetworking" {
  service            = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

module "vpc" {
  source = "./modules/vpc"

  name        = "ledgerly"
  region      = var.region
  subnet_cidr = var.subnet_cidr

  depends_on = [
    google_project_service.compute,
    google_project_service.servicenetworking,
  ]
}

module "cloudsql" {
  source = "./modules/cloudsql"

  project_id        = var.project_id
  region            = var.region
  name              = "ledgerly"
  network_self_link = module.vpc.network_self_link
  tier              = var.db_tier
  db_name           = var.db_name
  db_user           = var.db_user
  db_password       = var.db_password

  depends_on = [
    module.vpc,
    google_project_service.sqladmin,
  ]
}

resource "google_storage_bucket" "main" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }

    condition {
      age = 90
    }
  }
}
