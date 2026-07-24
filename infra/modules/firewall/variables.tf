# Inputs for the Hetzner Cloud Firewall module.

variable "name" {
  description = "Firewall name (e.g. maagaparuga-production)."
  type        = string
}

variable "admin_allowed_ips" {
  description = "CIDRs allowed to reach SSH (and ICMP). NO default on purpose — real IPs live in a gitignored tfvars, never committed."
  type        = list(string)

  validation {
    condition     = length(var.admin_allowed_ips) > 0
    error_message = "admin_allowed_ips must not be empty — an open SSH port defeats the firewall."
  }
}

variable "k8s_api_allowed_ips" {
  description = "CIDRs allowed to reach the k8s API (6443). Empty (default) keeps it CLOSED — reach the API via an SSH tunnel."
  type        = list(string)
  default     = []
}

variable "ssh_port" {
  description = "SSH port (non-default, house rule). Ansible + Terragrunt connect here."
  type        = string
  default     = "10022"
}

variable "apply_to_label_selector" {
  description = "Label selector that binds this firewall to the servers (e.g. project=maagaparuga,environment=production)."
  type        = string
}

variable "labels" {
  description = "Labels applied to the firewall."
  type        = map(string)
  default     = {}
}
