# Per-node facts the cluster module turns into an Ansible inventory.

output "nodes" {
  description = "One object per node: name, public IPv4, private IP, and k3s role."
  value = [
    for i, s in hcloud_server.node : {
      name       = s.name
      public_ip  = s.ipv4_address
      private_ip = tolist(s.network)[0].ip
      role       = i == 0 ? "server" : "agent"
    }
  ]
}

output "server_node" {
  description = "The control-plane node (k3s server) — first node."
  value = {
    name       = hcloud_server.node[0].name
    public_ip  = hcloud_server.node[0].ipv4_address
    private_ip = tolist(hcloud_server.node[0].network)[0].ip
  }
}
