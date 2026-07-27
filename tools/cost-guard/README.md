# tools/cost-guard — automated cost guardrail (FinOps)

Maps the [FinOps Foundation](https://www.finops.org/) lifecycle onto this repository:

| Phase | Implementation |
|---|---|
| **Inform** | `cost_guard.py refresh` snapshots live Hetzner Cloud prices into `prices.json` (committed); every `check` prints a per-resource monthly cost table |
| **Optimize** | `infra/budget.json` pins `allowed_server_types` — a plan that reaches for a bigger instance class fails before it can be applied |
| **Operate** | `cost_guard.py check` runs in the pipeline on every infrastructure plan and **blocks the deploy** when the projected monthly cost exceeds the environment's budget; a warning is emitted above the configurable warn threshold |
| **Attribution** | `required_labels` in `infra/budget.json` makes cost-attribution labels (`environment`, `project`) mandatory on every server — plans with unlabeled resources fail |

Zero dependencies (Python standard library only). Pull-request pipelines run `check`
offline from the committed price snapshot — no cloud credentials needed to enforce the
guardrail.

## Usage

```bash
# Inform: refresh the committed price snapshot (needs HCLOUD_TOKEN)
HCLOUD_TOKEN=... python3 tools/cost-guard/cost_guard.py refresh --date 2026-07-20

# Operate: price a plan and enforce the budget (exit code 1 on breach)
cd infra/terragrunt/staging
terragrunt plan -out=tf.plan
terragrunt show -json tf.plan > plan.json
python3 ../../../tools/cost-guard/cost_guard.py check --plan plan.json --env staging
```

Pipeline job (GitHub Actions sketch — final workflow lands with the IaC phase):

```yaml
  cost-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: terragrunt plan -out=tf.plan && terragrunt show -json tf.plan > plan.json
        working-directory: infra/terragrunt/staging
      - run: python3 tools/cost-guard/cost_guard.py check
               --plan infra/terragrunt/staging/plan.json --env staging
```

`::error::` / `::warning::` output lines surface directly as GitHub Actions annotations.

Note: `prices.json` must be generated once via `refresh` before the first `check`; the
file is committed so budget enforcement stays deterministic and credential-free in CI.
