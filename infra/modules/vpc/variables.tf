variable "name" {
  description = "Name prefix for the network and related resources."
  type        = string
}

variable "region" {
  description = "Region of the subnet."
  type        = string
}

variable "subnet_cidr" {
  description = "Primary IPv4 CIDR range of the subnet."
  type        = string
}

variable "peering_prefix_length" {
  description = "Prefix length of the private service access range reserved for Google managed services."
  type        = number
  default     = 16
}
