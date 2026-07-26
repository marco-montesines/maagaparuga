# Operations

How the platform is observed, backed up, and recovered. These pages describe
what exists in the repository; they are not an operational guarantee — this is a
**research and educational** framework running mock data.

## Observability

Telemetry is collected with **OpenTelemetry** and routed to **Prometheus**
(metrics), **Tempo** (traces), and **OpenSearch** (logs), with **Grafana**
providing dashboards and **unified alerting as code** — alert rules live in the
repository, not clicked into a UI. See
[ADR 0011](../adr/0011-observability-stack.md) and the
[Observability section](https://github.com/marco-montesines/maagaparuga/blob/master/README.md#observability--actionable-alerting) of the
main README.

Alerts are actionable by design: each rule carries a severity, a summary that
names the affected component, and a link to the runbook that resolves it.

## Backups & disaster recovery

PostgreSQL uses **continuous backup** (WAL archiving + base backups) to
S3-compatible object storage, with a **verified restore** procedure — a backup
that cannot be restored is treated as no backup. The strategy, the ransomware
controls (immutability/WORM, split write-only credentials, offsite copies), and
the restore drill are documented in:

- [Disaster recovery guide](https://github.com/marco-montesines/maagaparuga/blob/master/deploy/k8s/DISASTER-RECOVERY.md)
- [ADR 0016 — backup & disaster recovery](../adr/0016-backup-and-disaster-recovery.md)

Reproducible drills are available as make targets (`make dev-backup`,
`make dev-restore-verify`).

## Runbooks

Actionable procedures for the alerts that can fire:

- [Runbooks index](../runbooks/README.md)
- [Backup failure](../runbooks/backup-failure.md)

## Related

- [Deployment](../getting-started/deployment.md) — provisioning and rollout
- [Configuration](../getting-started/configuration.md) — environment variables and secrets
- [IaC overview](../iac/overview.md) — the infrastructure that all of this runs on
