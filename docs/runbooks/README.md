# docs/runbooks — alert runbooks

Each actionable alert links here. A runbook answers one question: **this alert
fired — now what?** It states what the alert means, the blast radius, how to
diagnose, and how to remediate, so a responder can act without archaeology.

Alert rules live as provisioned code in
[`deploy/k8s/base/observability/`](../../deploy/k8s/base/observability); each
rule's `runbook:` annotation points at a file here.

| Alert | Runbook |
|---|---|
| `PostgresBackupFailed` | [backup-failure.md](backup-failure.md) |

More runbooks land alongside the rest of the alert catalog (ingest stall,
consumer lag, replication lag, disk headroom, gateway p95/5xx, …) as that
observability tier is built out (P6b).
