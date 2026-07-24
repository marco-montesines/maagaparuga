# Inputs for the cluster composition (one environment = network + firewall + N nodes).

variable "hcloud_token" {
  description = "Hetzner Cloud API token for THIS environment's project. Prefer the HCLOUD_TOKEN env var; never commit it."
  type        = string
  sensitive   = true
  default     = "" # empty -> provider falls back to HCLOUD_TOKEN env var
}

variable "project" {
  description = "Project identifier, used in Hetzner resource names + labels. Kept as bgg-iac until the public flip at P8 (then -> maagaparuga)."
  type        = string
  default     = "bgg-iac"
}

variable "environment" {
  description = "Environment name (staging | production)."
  type        = string
}

variable "node_count" {
  description = "Number of k3s nodes (3 = the HA cluster shape). Also drives store replica placement."
  type        = number
  default     = 3
}

variable "server_type" {
  description = "Hetzner server type per node (cx32 = 4 vCPU / 8 GB)."
  type        = string
  default     = "cx32"
}

variable "image" {
  description = "OS image (current Ubuntu LTS)."
  type        = string
  default     = "ubuntu-24.04"
}

variable "location" {
  description = "Hetzner location (nbg1 | fsn1 | hel1)."
  type        = string
  default     = "nbg1"
}

variable "network_zone" {
  description = "Network zone containing the location."
  type        = string
  default     = "eu-central"
}

variable "ip_range" {
  description = "Private network CIDR (staging and production use different ranges)."
  type        = string
}

variable "subnet_range" {
  description = "Subnet CIDR the nodes attach to (a slice of ip_range)."
  type        = string
}

variable "admin_allowed_ips" {
  description = "CIDRs allowed to reach SSH — real values in a gitignored tfvars."
  type        = list(string)
}

variable "k8s_api_allowed_ips" {
  description = "CIDRs allowed to reach the k8s API (6443). Empty = closed."
  type        = list(string)
  default     = []
}

variable "ssh_public_keys" {
  description = "Admin SSH public keys."
  type        = list(string)
}

variable "ssh_port" {
  description = "SSH port (non-default)."
  type        = string
  default     = "10022"
}

variable "ssh_user" {
  description = "Ansible SSH user. Hetzner Ubuntu images log in as root (key-only after hardening)."
  type        = string
  default     = "root"
}

variable "domain" {
  description = "Base domain for this environment (used by the deploy overlay, surfaced as an output)."
  type        = string
  default     = ""
}
