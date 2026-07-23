# Disaster recovery & backup strategy

This is a research/educational platform, not a certified system — but it is
designed with the backup and ransomware-resistance controls a real care
platform needs, because "how would this survive an incident?" is a first-class
design question, not an afterthought.

> Decision record: [ADR 0016](../../docs/adr/0016-backup-and-disaster-recovery.md)
> (options considered + rejected). This document is the operational strategy;
> the alert runbook is [docs/runbooks/backup-failure.md](../../docs/runbooks/backup-failure.md).

## Principles

- **3-2-1-1-0**: ≥3 copies, on ≥2 media/systems, ≥1 offsite, ≥1 **immutable or
  offline**, with **0 restore errors** (backups are verified, not assumed).
- **Right tool per data class** — a live database is not a pile of files.
- **Least privilege for backups** — a credential that can *write* a backup must
  not be able to *delete* or *overwrite* it. Ransomware that owns the app must
  not be able to reach the restore point.
- **Tested restore over promised backup** — recoverability is proven on a
  cadence, not the day of the incident.

## What backs up what

| Data | Tool | Why | Model |
|------|------|-----|-------|
| **PostgreSQL** (care records, users, ZITADEL, OpenFGA) | **CNPG / barman** — base backup + continuous WAL archiving | Consistent, gives **PITR** (restore to any second). WAL *is* the incremental. | implemented |
| **Object storage** (SeaweedFS: media, attachments, telemetry archive) | **restic** → immutable offsite bucket | Incremental, deduplicated, **client-side encrypted**, append-only repo | design (P6) |
| **ClickHouse** (vitals time-series) | `clickhouse-backup` → S3 | Engine-native consistent snapshots | design (P6) |
| **OpenSearch** (search / vectors / logs) | Snapshot API → S3 repo | Re-derivable, but snapshotted to shorten RTO | design (P6) |

Postgres is the **system of record**; the others are largely re-derivable from
it + object storage, which is why Postgres PITR is the priority and is done
first. `restic` is deliberately *not* used for Postgres — running it over a live
data directory produces a torn, unrecoverable copy; it is the right tool for the
**object/file layer** and as the encrypted, ransomware-resistant offsite layer.

## Ransomware resistance

Ransomware today targets backups first. Controls, in priority order:

1. **Immutability (WORM)** — object-store **Object Lock** in *compliance* mode
   (or restic append-only repos): a backup, once written, cannot be modified or
   deleted before its retention expires, **even with admin credentials**. This
   is the single most important control and the one dev cannot fully model
   (in-cluster SeaweedFS shares the node) — cloud overlays (P6) target storage
   with real Object Lock (AWS S3 / Backblaze B2 / Wasabi).
2. **Separate, write-only credentials** — the cluster's backup credential can
   `PutObject` but not `DeleteObject`/`PutBucketLifecycle`. Deletion/expiry is a
   separate identity the app never holds. (Dev uses a full-access dev key for
   simplicity; P6 splits it.)
3. **Client-side encryption** — backups encrypted before they leave the cluster
   (restic native; barman `encryption`), so an offsite copy leaks nothing.
4. **Offsite / off-node** — dev backs up to in-cluster SeaweedFS on the *same
   node*: this proves the mechanism, **not** DR. P6 repoints
   `destinationPath`/`endpointURL` at durable, off-cluster storage.
5. **MFA-delete / air-gapped pull** — expiry requires MFA; ideally a separate,
   isolated system *pulls* backups so a full cluster compromise cannot reach
   them.
6. **Monitoring** — a failed/absent backup is an actionable alert (Grafana
   unified alerting), not a surprise at restore time.

## Restore (verified)

Postgres restore is a **new cluster** bootstrapped from the object store —
never an in-place overwrite (the corrupt/encrypted volume is left untouched for
forensics). Full-cluster recovery has been verified end-to-end: a recovery
cluster came up healthy and contained every database (app, zitadel, openfga)
with matching row counts.

```yaml
# Recovery Cluster: restores latest, or PITR with recovery.recoveryTarget.
spec:
  bootstrap:
    recovery:
      source: pg-origin
      # recoveryTarget: { targetTime: "2026-07-23 12:40:00+00" }   # PITR
  externalClusters:
    - name: pg-origin
      barmanObjectStore:
        serverName: maagaparuga-pg          # source cluster's backup path
        destinationPath: s3://pg-backups/
        endpointURL: http://seaweedfs:8333
        s3Credentials: { accessKeyId: {name: pg-backup-s3, key: ACCESS_KEY_ID},
                         secretAccessKey: {name: pg-backup-s3, key: ACCESS_SECRET_KEY} }
        wal: { compression: gzip }
```

- `make dev-backup` — take an on-demand base backup now.
- `make dev-restore-verify` — **restore drill**: spins a recovery cluster from
  the object store, checks it is healthy + row counts match, then tears it down.
  Run it on a cadence so "0 restore errors" stays true.

## Targets (RPO / RTO)

- **RPO** (data loss window): minutes — bounded by WAL archive frequency, not
  the nightly base backup.
- **RTO** (time to restore): the recovery cluster above reached healthy in well
  under a minute at dev scale; real RTO is set by data volume + network in P6.

## Status

- **Done:** Postgres continuous backup (WAL + base) to S3, retention, daily
  `ScheduledBackup`, and a **verified full restore**.
- **P6:** object-store Object Lock/immutability, split write-only credentials,
  client-side encryption, off-node/offsite target, restic for the object layer,
  ClickHouse/OpenSearch backups, and scheduled restore drills wired to alerting.
