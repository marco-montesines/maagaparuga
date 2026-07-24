# Staging — the full production rehearsal, EPHEMERAL (terragrunt destroy after a
# verification run). Same 3-node shape as production; its own private range
# (10.10.x) and, ideally, its own Hetzner project/token so it can never touch
# production.
#
# Secrets (hcloud_token, admin_allowed_ips, ssh_public_keys) come from
# secrets.auto.tfvars (gitignored) or environment variables.

include "root" {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  environment  = "staging"
  node_count   = 3
  server_type  = "cx32" # 4 vCPU / 8 GB per node
  location     = "nbg1"
  ip_range     = "10.10.0.0/16"
  subnet_range = "10.10.1.0/24"

  # Real DNS via DuckDNS (A record -> a node public IP). Caddy terminates HTTPS
  # with a real Let's Encrypt cert for this hostname.
  domain = "staging-maagaparuga.duckdns.org"
}
