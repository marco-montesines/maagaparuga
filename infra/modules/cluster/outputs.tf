# Handoff to Ansible + the operator. `ansible_inventory` is a ready-to-write YAML
# inventory; `terragrunt output -raw ansible_inventory > inventory.generated.yml`.

output "nodes" {
  description = "All nodes: name, public IPv4, private IP, k3s role."
  value       = module.servers.nodes
}

output "server_public_ip" {
  description = "Public IP of the control-plane node (SSH / kubeconfig fetch)."
  value       = module.servers.server_node.public_ip
}

output "server_private_ip" {
  description = "Private IP the k3s API is advertised on (agents join here)."
  value       = module.servers.server_node.private_ip
}

output "domain" {
  description = "Base domain for this environment (consumed by the deploy overlay)."
  value       = var.domain
}

output "ansible_inventory" {
  description = "YAML inventory for the Ansible playbooks (k3s_server + k3s_agents groups)."
  value = yamlencode({
    all = {
      vars = {
        ansible_user            = var.ssh_user
        ansible_port            = tonumber(var.ssh_port)
        ansible_ssh_common_args = "-o StrictHostKeyChecking=accept-new"
        # k3s binds to the private interface; agents join on the private IP.
        k3s_server_private_ip = module.servers.server_node.private_ip
      }
      children = {
        k3s_server = {
          hosts = {
            for n in module.servers.nodes : n.name => {
              ansible_host = n.public_ip
              private_ip   = n.private_ip
            } if n.role == "server"
          }
        }
        k3s_agents = {
          hosts = {
            for n in module.servers.nodes : n.name => {
              ansible_host = n.public_ip
              private_ip   = n.private_ip
            } if n.role == "agent"
          }
        }
      }
    }
  })
}
