# Runbook — `PostgresBackupFailed`

## What it means

The most recent PostgreSQL **base-backup attempt failed**: the last-failed
backup timestamp is newer than the last-successful one
(`cnpg_collector_last_failed_backup_timestamp > cnpg_collector_last_available_backup_timestamp`).
The recovery point has stopped advancing.

## Why it matters

This is the **disaster-recovery safety net itself** degrading. Every minute it
stays broken widens the window of data that cannot be recovered — and on a care
platform the threat model includes ransomware, where an intact, recent,
immutable backup is the difference between an incident and a catastrophe. Treat
it as a high-priority page, not a warning. (Strategy:
[../../deploy/k8s/DISASTER-RECOVERY.md](../../deploy/k8s/DISASTER-RECOVERY.md).)

## Diagnose

```bash
NS=maagaparuga
# recent backups — look for phase=failed
kubectl -n $NS get backup --sort-by=.metadata.creationTimestamp
# the failure reason
kubectl -n $NS describe backup <failed-backup-name>
# is continuous WAL archiving also broken?
kubectl -n $NS get cluster maagaparuga-pg \
  -o jsonpath='{.status.conditions[?(@.type=="ContinuousArchiving")]}'
# operator/instance logs around the failure
kubectl -n $NS logs -l cnpg.io/cluster=maagaparuga-pg -c postgres --tail=100 | grep -i barman
```

Common causes, in rough order:

- **Object store unreachable** — wrong `endpointURL`, DNS, network/firewall to
  the backup store.
- **Bad or expired credentials** — the `pg-backup-s3` secret (dev) or the
  provisioned backup identity (cloud).
- **Bucket missing / full / lifecycle-blocked** — destination bucket gone, out
  of space, or an Object-Lock/retention policy rejecting the write.
- **Backup store degraded** — the S3 service itself is down.

## Remediate

1. Fix the underlying cause (reachability / credentials / bucket) found above.
2. Take a fresh base backup and confirm it completes:
   ```bash
   make dev-backup        # dev; in cloud, create a Backup CR against the cluster
   ```
3. The alert **auto-resolves** once a successful backup advances the recovery
   point (`last_available > last_failed`).
4. If the failure suggests the existing backups may be compromised or the store
   was tampered with, **verify recoverability** with a restore drill:
   ```bash
   make dev-restore-verify
   ```

## Escalate / follow up

- If WAL archiving is also failing, the recovery-point loss is continuous, not
  just the nightly snapshot — prioritise accordingly.
- If backups were **deleted** (not just failed to write), that is a security
  event: the backup identity is meant to be write-only (cannot delete). Treat a
  deletion as a possible credential compromise and rotate.
