output "network_id" {
  description = "ID of the VPC network."
  value       = google_compute_network.main.id
}

output "network_self_link" {
  description = "Self link of the VPC network. Resolves only after the peering connection exists."
  value       = google_compute_network.main.self_link

  depends_on = [google_service_networking_connection.private_service_access]
}

output "subnet_id" {
  description = "ID of the subnet."
  value       = google_compute_subnetwork.main.id
}

output "peering_range_name" {
  description = "Name of the reserved private service access range."
  value       = google_compute_global_address.private_service_access.name
}
