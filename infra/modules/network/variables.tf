# Inputs for the private-network module.

variable "name" {
  description = "Network name (e.g. maagaparuga-production)."
  type        = string
}

variable "ip_range" {
  description = "The whole private network CIDR (e.g. 10.20.0.0/16). Staging and production use different ranges so they can never be confused."
  type        = string
}

variable "subnet_range" {
  description = "The subnet CIDR the servers attach to (a slice of ip_range, e.g. 10.20.1.0/24)."
  type        = string
}

variable "network_zone" {
  description = "Hetzner network zone (must contain the server location). eu-central covers nbg1/fsn1/hel1."
  type        = string
  default     = "eu-central"
}

variable "labels" {
  description = "Labels applied to the network (environment, project, ...)."
  type        = map(string)
  default     = {}
}
