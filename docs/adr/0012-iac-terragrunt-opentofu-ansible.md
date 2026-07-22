# 0012 — IaC: Terragrunt + OpenTofu/Terraform + Ansible on Hetzner Cloud

Status: **Accepted**

## Context

Two cloud environments (ephemeral staging, always-on production), each a 3-node
Hetzner Cloud cluster, must be reproducible from code: provision nodes/network/firewall,
install k3s, deploy the stack — with cost as a first-class constraint.

## Options considered

- **Terraform/OpenTofu alone** — rejected: per-environment duplication that Terragrunt
  removes (thin per-env config over shared modules — the `modules/` + `live/` pattern).
- **Ansible alone** — rejected: imperative provisioning of cloud resources without
  plan/state semantics.
- **Cloud-provider consoles / manual setup** — rejected outright: not reproducible.
- **Terragrunt + OpenTofu/Terraform (interchangeable, standard HCL) + Ansible** ✅ —
  Terragrunt/OpenTofu provision (server, network, firewall) with remote state +
  locking; the inventory hands off to Ansible, which hardens the host, installs k3s,
  and applies the Kustomize overlay.

Provider: **Hetzner Cloud** — European, inexpensive, hourly billing (enables ephemeral
staging). Hyperscalers rejected for cost and because IaC/Kubernetes/CI skills transfer
regardless of provider; the trade-off is documented, not hidden.

## Decision

`infra/modules/` (readable, commented HCL) + `infra/terragrunt/{staging,production}/`
+ `infra/ansible/`. Staging: same 3-node shape as production, **created for a rehearsal, destroyed
after**. Production: mid-size class (identity stack + media ML). The public **domain is
a variable** (`base_domain`): apex = production, `staging.<base_domain>` = staging, one
Let's Encrypt DNS-01 wildcard certificate. FinOps guardrail: `tools/cost-guard` prices
every plan against `infra/budget.json` in CI and fails on budget breach, disallowed
server types, or missing cost-attribution labels.

## Consequences

- Staging costs money only while it is testing something; every staging deploy is a
  full rehearsal of production (same manifests, different variables).
- No `*.tfstate` or secret-bearing `*.tfvars` in the repository — `*.tfvars.example`
  convention, remote state with locking.
- Revisit when: multi-node or multi-region environments arrive (module boundaries are
  already shaped for node-count variables).
