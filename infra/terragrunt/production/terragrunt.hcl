# Production — always-on 3-node HA cluster. Its own private range (10.20.x) and,
# ideally, its own Hetzner project/token, isolated from staging.
#
# Secrets (hcloud_token, admin_allowed_ips, ssh_key_names) come from
# secrets.auto.tfvars (gitignored) or environment variables.

include "root" {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  environment  = "production"
  node_count   = 3
  server_type  = "cpx32" # 4 vCPU / 8 GB x86, EUR 35.49/mo (cax21 Arm is cheaper but was out of stock everywhere)
  location     = "nbg1"
  ip_range     = "10.20.0.0/16"
  subnet_range = "10.20.1.0/24"

  # Real DNS via DuckDNS (A record -> a node public IP). Caddy terminates HTTPS
  # with a real Let's Encrypt cert for this hostname.
  domain = "maagaparuga.duckdns.org"
}
