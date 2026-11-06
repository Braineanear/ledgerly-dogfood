resource "google_compute_network" "main" {
  name                    = var.name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name                     = "${var.name}-subnet"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true
}

# Private service access: range reserved for Google managed services
# (such as Cloud SQL) and the peering connection that uses it.
resource "google_compute_global_address" "private_service_access" {
  name          = "${var.name}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.peering_prefix_length
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_service_access" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]
}
