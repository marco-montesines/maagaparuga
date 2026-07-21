# infra — Infrastructure as Code

Planned layout:

- `terragrunt/staging`, `terragrunt/production` — per-environment configuration
  (one small Hetzner Cloud VM each).
- `modules/` — OpenTofu/Terraform modules: server, private network, firewall.
  Standard HCL — runs unchanged with either `tofu` or `terraform`.
- `ansible/` — provisioning (Docker CE) and deployment (compose render + `up -d`)
  playbooks; consumes the inventory emitted by the Terragrunt output.

OpenSearch and ClickHouse node counts are variables: single-node on the demo VMs,
cluster-of-N supported by the same templates.

Status: skeleton only — detailed IaC documentation will be added as the modules land.
