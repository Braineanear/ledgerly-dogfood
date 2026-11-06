output "instance_connection_name" {
  description = "Connection name of the Cloud SQL instance."
  value       = google_sql_database_instance.main.connection_name
}

output "private_ip_address" {
  description = "Private IP address of the Cloud SQL instance."
  value       = google_sql_database_instance.main.private_ip_address
}

output "database_name" {
  description = "Name of the created database."
  value       = google_sql_database.main.name
}
