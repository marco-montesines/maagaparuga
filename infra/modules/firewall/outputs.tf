output "firewall_id" {
  description = "ID of the firewall (bound to servers by label selector)."
  value       = hcloud_firewall.this.id
}
