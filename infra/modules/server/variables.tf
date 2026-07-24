# Inputs for the server (k3s node) module.

variable "name_prefix" {
  description = "Prefix for node names (e.g. maagaparuga-production -> maagaparuga-production-1..N)."
  type        = string
}

variable "node_count" {
  description = "Number of VMs (one per k3s node). 3 = the HA cluster shape."
  type        = number
  default     = 3
}

variable "server_type" {
  description = "Hetzner server type per node (e.g. cx32 = 4 vCPU / 8 GB)."
  type        = string
}

variable "image" {
  description = "OS image (current Ubuntu LTS)."
  type        = string
  default     = "ubuntu-24.04"
}

variable "location" {
  description = "Hetzner location (nbg1/fsn1/hel1 — must match the network zone)."
  type        = string
}

variable "ssh_public_keys" {
  description = "Public SSH keys allowed to log in as the admin user."
  type        = list(string)

  validation {
    condition     = length(var.ssh_public_keys) > 0
    error_message = "Provide at least one SSH public key or you cannot reach the servers."
  }
}

variable "network_id" {
  description = "Private network to attach every node to."
  type        = string
}

variable "subnet_ip_range" {
  description = "Subnet CIDR the nodes draw private IPs from (also creates the subnet dependency)."
  type        = string
}

variable "ssh_port" {
  description = "SSH port cloud-init switches to at first boot (must match the firewall)."
  type        = string
  default     = "10022"
}

variable "labels" {
  description = "Base labels applied to every node (project, environment). The module adds a per-node k3s_role label."
  type        = map(string)
  default     = {}
}
