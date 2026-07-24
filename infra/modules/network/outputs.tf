output "network_id" {
  description = "ID of the private network (servers attach to it)."
  value       = hcloud_network.this.id
}

output "subnet_ip_range" {
  description = "The subnet CIDR servers draw their private IPs from."
  value       = hcloud_network_subnet.this.ip_range
}
