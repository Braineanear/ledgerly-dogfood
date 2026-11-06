output "bucket_name" {
  description = "Name of the storage bucket."
  value       = google_storage_bucket.main.name
}

output "cloudsql_connection_name" {
  description = "Connection name of the Cloud SQL instance."
  value       = module.cloudsql.instance_connection_name
}

output "cloudsql_private_ip" {
  description = "Private IP address of the Cloud SQL instance."
  value       = module.cloudsql.private_ip_address
}
