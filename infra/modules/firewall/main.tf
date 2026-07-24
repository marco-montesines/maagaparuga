# Hetzner Cloud Firewall — the ONLY inbound gate (house rule: no host ufw).
# Hetzner firewalls are DEFAULT-DENY inbound: only the rules listed below are
# allowed, everything else (NodePorts, etcd, kubelet, store ports, ...) is
# rejected at the edge. Private-network traffic is NOT filtered by Hetzner, so
# cluster-internal ports need no rules here. Outbound is left unrestricted.

resource "hcloud_firewall" "this" {
  name   = var.name
  labels = var.labels

  # Public web traffic -> APISIX (the only app entry point).
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTP -> APISIX (redirects to HTTPS)"
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTPS -> APISIX"
  }

  # SSH on the non-default port, admin source IPs only.
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = var.ssh_port
    source_ips  = var.admin_allowed_ips
    description = "SSH (admin allow-list only)"
  }

  # ICMP (ping) from admin IPs — handy for reachability checks, harmless.
  rule {
    direction   = "in"
    protocol    = "icmp"
    source_ips  = var.admin_allowed_ips
    description = "ICMP (admin allow-list only)"
  }

  # k8s API (6443) — OFF unless explicit IPs are provided. Default path is a
  # `ssh -L` tunnel, so the API is never publicly reachable.
  dynamic "rule" {
    for_each = length(var.k8s_api_allowed_ips) > 0 ? [1] : []
    content {
      direction   = "in"
      protocol    = "tcp"
      port        = "6443"
      source_ips  = var.k8s_api_allowed_ips
      description = "k8s API (kubectl, allow-list only)"
    }
  }

  # Bind the firewall to every server carrying these labels.
  apply_to {
    label_selector = var.apply_to_label_selector
  }
}
