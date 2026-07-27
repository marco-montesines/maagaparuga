# One environment's cluster: a private network, a default-deny firewall, and N
# nodes attached to the network. The three child modules are deliberately small
# and single-purpose so each is easy to read on its own.

locals {
  name   = "${var.project}-${var.environment}"
  labels = { project = var.project, environment = var.environment }
}

module "network" {
  source       = "../network"
  name         = local.name
  ip_range     = var.ip_range
  subnet_range = var.subnet_range
  network_zone = var.network_zone
  labels       = local.labels
}

module "firewall" {
  source                  = "../firewall"
  name                    = local.name
  admin_allowed_ips       = var.admin_allowed_ips
  k8s_api_allowed_ips     = var.k8s_api_allowed_ips
  ssh_port                = var.ssh_port
  apply_to_label_selector = "project=${var.project},environment=${var.environment}"
  labels                  = local.labels
}

module "servers" {
  source          = "../server"
  name_prefix     = local.name
  node_count      = var.node_count
  server_type     = var.server_type
  image           = var.image
  location        = var.location
  ssh_key_names   = var.ssh_key_names
  network_id      = module.network.network_id
  subnet_ip_range = module.network.subnet_ip_range
  ssh_port        = var.ssh_port
  labels          = local.labels
}
