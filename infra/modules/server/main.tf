# One VM per k3s node. Node 0 is the k3s server (control plane), nodes 1..N-1 are
# agents — the `k3s_role` label lets the Ansible inventory tell them apart. Every
# node attaches to the private network with a stable IP; the public interface
# exists only for APISIX (80/443) and admin SSH (the firewall enforces that).

resource "hcloud_server" "node" {
  count = var.node_count
  # The name becomes the OS hostname + k8s node name (RFC 1123). The project is
  # already lowercase (maagaparuga), so no case handling needed.
  name        = "${var.name_prefix}-${count.index + 1}"
  image       = var.image
  server_type = var.server_type
  location    = var.location
  ssh_keys    = var.ssh_key_names # existing keys in the project, by name

  labels = merge(var.labels, {
    # First node runs the control plane; the rest join as agents.
    k3s_role = count.index == 0 ? "server" : "agent"
  })

  # Attach to the private network with a stable IP (.10, .11, .12, ...).
  # Referencing subnet_ip_range makes each server wait for the subnet.
  network {
    network_id = var.network_id
    ip         = cidrhost(var.subnet_ip_range, 10 + count.index)
  }

  # Public IPv4 for APISIX + admin SSH; IPv6 too (free, and future-friendly).
  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    ssh_port = var.ssh_port
  })
}
