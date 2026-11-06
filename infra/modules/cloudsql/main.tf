resource "google_sql_database_instance" "main" {
  project             = var.project_id
  region              = var.region
  name                = var.name
  database_version    = "POSTGRES_15"
  deletion_protection = true

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    disk_size         = var.disk_size_gb
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_self_link
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
  }
}

resource "google_sql_database" "main" {
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  name     = var.db_name
}

resource "google_sql_user" "main" {
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  name     = var.db_user
  password = var.db_password
}
