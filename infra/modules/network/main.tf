# A private Hetzner Cloud Network — the backbone every VM attaches to. All
# system-internal traffic (k3s, Postgres, ClickHouse, OpenSearch, NATS, ...) rides
# this network and never touches the public internet. Hetzner does NOT firewall
# private-network traffic, so cluster-internal ports need no firewall rules.

resource "hcloud_network" "this" {
  name     = var.name
  ip_range = var.ip_range
  labels   = var.labels
}

# A subnet inside the network. type "cloud" is the standard Hetzner Cloud subnet;
# servers get an address from this range when they attach.
resource "hcloud_network_subnet" "this" {
  network_id   = hcloud_network.this.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = var.subnet_range
}
