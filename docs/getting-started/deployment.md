# Deployment — staging & production on Hetzner (k3s)

Deploying to a real cluster uses **Terragrunt + OpenTofu/Terraform** to provision the
Hetzner Cloud nodes, then **Ansible** to install k3s and apply the Kubernetes overlay.
The infrastructure code is standard HCL, so `tofu` and `terraform` are interchangeable.
For the local single-node bring-up see [installation.md](installation.md).

## Environments

| Environment | Where | Kubernetes | Shape |
|---|---|---|---|
| **dev** | local machine | minikube (single node) | not covered here — see [installation.md](installation.md) |
| **staging** | Hetzner Cloud | k3s, **3-node**, **ephemeral** | a full rehearsal of production, then torn down |
| **production** | Hetzner Cloud | k3s, **3-node HA**, always on | no single-VM point of failure |

Staging mirrors production's shape exactly (same node count, same manifests) so it
rehearses the things that only exist across nodes — pod anti-affinity separating
replicas, cross-node networking, rolling updates. What keeps it cheap is
**ephemerality**: Hetzner bills hourly, so a 3-node staging that lives for the ~hour of a
rehearsal and is then destroyed costs a few VM-hours. Node count is a Terragrunt variable,
so the same code scales further.

## Prerequisites

Before the first deploy you need:

- **A Hetzner Cloud project + API token** (Read & Write), project-scoped. Use a
  **different project/token per environment** for full isolation.
- **An S3-compatible bucket for Terraform remote state** — a **Backblaze B2** or
  **DigitalOcean Spaces** bucket. State never lives in the repo.
- **An SSH key already uploaded to the Hetzner project** (referenced by name, not
  created — Hetzner rejects duplicates).
- **Your admin source IP(s)** — the only addresses allowed to reach SSH (port 10022).
- **A DNS hostname** you control (the repository uses DuckDNS) whose A record you can
  point at a node's public IP.
- **A registry pull token** for the private application images (GHCR `read:packages`),
  while the image packages are private.

`tofu` (or `terraform`), `terragrunt`, and `ansible` must be installed locally.

## Configure the environment

All credentials come from environment variables or gitignored `*.tfvars` — copy the
committed examples and fill them in:

```bash
cd infra/terragrunt
cp env.sh.example env.sh                                   # gitignored — fill in tokens
cp production/secrets.auto.tfvars.example production/secrets.auto.tfvars
```

`env.sh` collects the Hetzner token (`HCLOUD_TOKEN`), the state-bucket S3 key (mapped
onto `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), and the state-bucket location
(`TG_STATE_BUCKET` / `TG_STATE_ENDPOINT` / `TG_STATE_REGION`). `secrets.auto.tfvars`
holds the Terraform *variables*: `hcloud_token` (or leave it to the env var),
`admin_allowed_ips`, and `ssh_key_names`.

The per-environment shape (node count, server type, location, private-network ranges, and
the `domain`) lives in `infra/terragrunt/<env>/terragrunt.hcl`.

## Provision the cluster (Terragrunt → OpenTofu/Terraform)

```bash
cd infra/terragrunt
source env.sh
cd production                         # or: staging

terragrunt init
terragrunt plan                       # priced against infra/budget.json by cost-guard in CI
terragrunt apply                      # network + firewall + 3 VMs, cloud-init -> SSH on 10022
terragrunt output -raw ansible_inventory > ../../ansible/inventory.generated.yml
```

`terragrunt apply` stands up, per environment: a **dedicated private network**
(distinct address range), a **default-deny Hetzner firewall** (only 80/443 world-facing
and SSH on **10022** restricted to your admin allow-list), and **N VMs** (node 1 is the
k3s server, nodes 2–3 are agents), each attached to the private network. The last command
exports the Ansible inventory Terragrunt generated (it sets `ansible_port: 10022` and the
node private IPs).

> For a quick local demo with no remote bucket, comment out the `remote_state` block in
> `infra/terragrunt/root.hcl` — state then stays in the gitignored `.terragrunt-cache`.

## Configure & deploy (Ansible)

```bash
cd infra/ansible
ansible-playbook site.yml -e env=production            # or: -e env=staging
```

`site.yml` runs three roles in order:

1. **common** — base hardening on every node: key-only SSH on port 10022, `fail2ban`,
   the OpenSearch `vm.max_map_count` sysctl, etc.
2. **k3s** — installs k3s (server on node 1, agents on nodes 2–3), bound to the private
   interface.
3. **deploy** — copies the `deploy/k8s` tree to the server, installs the CloudNativePG
   operator (pinned ≤ 1.30.x), creates the GHCR image-pull secret if a token is supplied,
   and applies the overlay matching `env` (`kubectl apply -k deploy/k8s/overlays/<env>`).

The GHCR token is passed out-of-band, e.g. `-e ghcr_pull_token=...` (or a vault) — it is
left empty in `group_vars/all.yml` and never committed. If the image packages are made
public, the pull-secret step is skipped.

## Provision secrets & bootstrap

The overlay ships **no real secrets** — `kubectl kustomize` builds cleanly, but the pods
stay pending until you create them. Provision the secrets listed in the table in
[`deploy/k8s/overlays/production/README.md`](https://github.com/marco-montesines/maagaparuga/blob/master/deploy/k8s/overlays/production/README.md)
(database credentials, `openfga-datastore`, ClickHouse / OpenSearch / Redis credentials,
`seaweedfs-s3-config`, `zitadel-masterkey`, `web-secrets`, `telemetry-secrets`,
`media-s3`, `grafana-admin`, the `pg-backup-s3` offsite backup key, and `ghcr-pull`) —
from gitignored `secrets/*.env`, a `kubectl create secret` script, or SealedSecrets.

Then run the bootstrap against the cluster (the same steps `make dev-bootstrap`,
`dev-device-auth`, and `dev-media-auth` perform locally): configure the ZITADEL
project/clients, run `php artisan fga:bootstrap`, and inject the resulting
`OPENFGA_STORE_ID` / `OPENFGA_MODEL_ID` + client credentials + `OIDC_AUDIENCE` so
`AUTH_MODE=jwt` has its issuer and OpenFGA ids. See
[configuration.md](configuration.md#authentication-and-authorization) for what these values
are.

## HTTPS at the edge

The public hostname resolves (DuckDNS A record → a node's public IP) and **Caddy** is the
public edge: on first traffic it obtains a real Let's Encrypt certificate (HTTP-01,
auto-renewed), terminates HTTPS, and reverse-proxies to APISIX (which stays internal). A
CoreDNS rewrite maps the hostname to the Caddy service in-cluster, so the single-host OIDC
issuer resolves for services too. Test with Let's Encrypt **staging** first (uncomment
`acme_ca` in `deploy/k8s/overlays/production/caddy.yaml`) to avoid rate limits, then
switch to real.

## Tearing down (ephemeral staging)

Staging is meant to be destroyed after a rehearsal:

```bash
cd infra/terragrunt/staging
source ../env.sh
terragrunt destroy
```

You pay for staging only while it is actually testing something.

## Provider portability

Hetzner Cloud is the **core compute** provider, but the design deliberately keeps the
replaceable pieces behind open interfaces so no single provider is load-bearing:

- **Compute engine** — OpenTofu and Terraform are interchangeable; the same HCL modules
  run under either.
- **Terraform remote state** — any S3-compatible bucket: Backblaze B2 or DigitalOcean
  Spaces, selected purely by the `TG_STATE_*` / `AWS_*` variables. Keeping state with a
  provider separate from Hetzner means it survives loss of the Hetzner project.
- **Offsite backups** — the `pg-backup-s3` target is an IaC choice, decoupled from where
  the core infra runs; the repository points it at Backblaze B2 (a different provider,
  with Object-Lock/WORM for ransomware resistance).
- **Object storage** — SeaweedFS provides the in-cluster S3 data lake, but every client
  reaches it through the S3 API; repointing `S3_ENDPOINT` + credentials swaps it for any
  managed S3-compatible service without touching service code.

## Cost guardrail (FinOps)

Every `terragrunt plan` is priced against [`infra/budget.json`](https://github.com/marco-montesines/maagaparuga/blob/master/infra/budget.json)
by [`tools/cost-guard`](https://github.com/marco-montesines/maagaparuga/blob/master/tools/cost-guard/README.md), which **fails the pipeline** if
the projected monthly cost exceeds the environment's budget or a plan reaches for a server
type outside the allow-list. Every cloud resource must carry `environment` and `project`
labels, enforced by the guardrail. See the root
[README](https://github.com/marco-montesines/maagaparuga/blob/master/README.md#finops--caring-about-infrastructure-cost) for the full FinOps
model.
