# Infrastructure as Code — overview

Everything that runs the platform is described as code: the cluster VMs, the
network and firewall, the Kubernetes workloads, and their configuration. Nothing
is clicked into existence. The rationale and rejected alternatives are in
[ADR 0012](../adr/0012-iac-terragrunt-opentofu-ansible.md); the modules and
environments live under [`infra/`](https://github.com/marco-montesines/maagaparuga/blob/master/infra/README.md).

## The toolchain

| Tool | Role |
|---|---|
| **OpenTofu / Terraform** | Provisions cloud resources (VMs, private network, firewall). The two are interchangeable HCL. |
| **Terragrunt** | Keeps the Terraform DRY: one root configuration, thin per-environment stacks, remote state. |
| **Ansible** | Configures the VMs (hardening, k3s install) and applies the app overlay. |
| **Kustomize** | Renders the Kubernetes manifests per environment (base + overlays). |

## Layout

```
infra/
  modules/        OpenTofu modules: network, firewall, server, cluster
  terragrunt/     root.hcl + per-environment stacks (staging, production)
  ansible/        site.yml + roles (common hardening, k3s, deploy)
deploy/k8s/
  base/           the platform manifests
  overlays/       dev · staging · production (Kustomize)
```

## Environments

| Environment | Where | Shape |
|---|---|---|
| dev | local minikube | single node |
| staging | k3s on cloud VMs | multi-node, ephemeral (stood up per rehearsal, then torn down) |
| production | k3s on cloud VMs | multi-node, always-on, high-availability |

Staging is kept inexpensive by being **ephemeral**, not by being smaller — it
mirrors the production shape so a deploy rehearsal exercises the same topology.

## The provisioning flow

```
cd infra/terragrunt && source env.sh          # tokens/state backend (gitignored)
cd staging && terragrunt apply                 # VMs + network + firewall
                                               # → emits an Ansible inventory
cd ../../ansible
ansible-playbook site.yml -e env=staging       # harden → install k3s → deploy overlay
```

See [Deployment](../getting-started/deployment.md) for the full walkthrough,
including the secrets that are provisioned out-of-band.

## Provider portability

The core cluster (Kubernetes + the data layer + the private inter-node network
they need for quorum) is one placement, kept **provider-portable** so the host is
an overlay variable. Satellite concerns are placed independently — for example,
offsite backups target a different provider from the compute so a single account
outage does not take down both. Object-storage and backup endpoints are
configuration, not hard-coded. See
[ADR 0016](../adr/0016-backup-and-disaster-recovery.md).

## Guardrails

- **Versions** are pinned to a known-good latest-stable set
  ([ADR 0013](../adr/0013-latest-stable-pinned-versions.md)).
- **Cost** is checked by `tools/cost-guard`, which flags budget breaches and
  disallowed machine types before an apply — see its
  [README](https://github.com/marco-montesines/maagaparuga/blob/master/tools/cost-guard/README.md) and the
  [FinOps section](https://github.com/marco-montesines/maagaparuga/blob/master/README.md#finops--caring-about-infrastructure-cost) of the
  main README.
- **Node hardening** (SSH on a non-default port, key-only auth, default-deny
  firewall, private-network internal traffic) is applied by the Ansible `common`
  and `k3s` roles.
