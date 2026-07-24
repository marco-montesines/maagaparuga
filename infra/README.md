# infra — Infrastructure as Code (P6)

Provisions the staging and production clusters on **Hetzner Cloud** with
**OpenTofu/Terraform + Terragrunt**, then hands off to **Ansible** to install k3s
and deploy the app. Standard HCL — runs unchanged under `tofu` or `terraform`.

## Layout

```
modules/
  network/    hcloud_network + subnet (one private network per environment)
  firewall/   hcloud_firewall — default-deny; 80/443 world, SSH 10022 admin-only
  server/     N VMs (one per k3s node), private-network attached, cloud-init -> SSH 10022
  cluster/    composition: network + firewall + servers -> ansible_inventory output
terragrunt/
  terragrunt.hcl          root: S3-compatible remote state + generated hcloud provider
  staging/                3-node, 10.10.x, ephemeral (destroy after a rehearsal)
  production/             3-node, 10.20.x, always-on
ansible/                  common (hardening) + k3s + deploy roles          [next increment]
budget.json               FinOps guardrail (tools/cost-guard) — 3-node budgets
```

Both environments are **3-node** clusters (`node_count`, default 3): node 1 is the
k3s server, nodes 2–3 are agents. k3s binds to the **private** interface; only
APISIX (80/443) and admin SSH (10022) are public.

## Secrets — nothing sensitive is committed

All secrets come from env vars or gitignored `*.tfvars` (see `.gitignore` +
`*.tfvars.example`):

| What | Where |
|---|---|
| Hetzner token (project-scoped) | `HCLOUD_TOKEN` env, or `hcloud_token` in `terragrunt/<env>/secrets.auto.tfvars` |
| State-bucket S3 key (B2 / DO Spaces) | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` + `TG_STATE_*` env |
| Admin SSH IP allow-list | `admin_allowed_ips` in the same tfvars (or `TF_VAR_admin_allowed_ips`) |

The Hetzner token is **project-scoped** — one token = one project. Use a
different project/token per environment for full isolation. The `hcloud` CLI
context is separate from Terraform; Terraform reads `HCLOUD_TOKEN`.

## Usage

```bash
cd infra/terragrunt/production
cp secrets.auto.tfvars.example secrets.auto.tfvars    # fill in (gitignored)
export HCLOUD_TOKEN=...                                # or set it in the tfvars
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... # state bucket (B2/DO)
export TG_STATE_BUCKET=... TG_STATE_ENDPOINT=... TG_STATE_REGION=...

terragrunt init
terragrunt plan             # cost-guard runs this JSON against budget.json in CI
terragrunt apply
terragrunt output -raw ansible_inventory > ../../ansible/inventory.generated.yml
```

For a quick local demo without a remote bucket, comment out the `remote_state`
block in `terragrunt/terragrunt.hcl` (state stays local, gitignored).

OpenSearch and ClickHouse node counts remain variables in the deploy overlays;
the same manifests run single-node in dev and cluster-of-N here.
