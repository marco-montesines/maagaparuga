# 0016 — Backups & disaster recovery (ransomware-resistant, tested restore)

Status: **Accepted** · Builds on [ADR 0005](0005-right-store-per-workload.md)
(data layer), [ADR 0015](0015-seaweedfs-object-storage.md) (object store),
[ADR 0011](0011-observability-stack.md) (the backup-failure alert), and
[ADR 0012](0012-iac-terragrunt-opentofu-ansible.md) (IaC provisions the DR
substrate).

## Context

A reliability audit surfaced that **no stateful store had any backup** — a
platform that claims operational competence with an object store three services
away and no recovery path is an obvious hole. For a care platform the bar is
higher than "we take backups": recoverability is a *design* concern, and the
threat model explicitly includes **ransomware, which targets backups first** —
an attacker who reaches the cluster will try to encrypt or delete the restore
points before anyone notices. So the decision is not just "back up Postgres" but
a strategy: the right tool per data class, controls that survive a full cluster
compromise, and a restore that is *proven*, not assumed.

## Options considered

**How to back up PostgreSQL** (the system of record — care records, plus ZITADEL
and OpenFGA state):

| Option | Assessment |
|---|---|
| `pg_dump` on a schedule ❌ | Logical dump: no point-in-time recovery, slow and heavy at size, a snapshot only as fresh as the last run |
| `restic`/file copy over the data directory ❌ | A live PostgreSQL data dir copied file-by-file is **torn and unrecoverable** — no crash consistency. Wrong tool for a running database |
| **CNPG / barman: base backups + continuous WAL archiving** ✅ | Consistent backups plus **point-in-time recovery** to any second (the WAL *is* the incremental). Native to the operator already running (ADR 0005). |

**CNPG barman: in-tree vs the Barman Cloud Plugin:**

| Option | Assessment |
|---|---|
| Barman Cloud **Plugin** (CNPG-I) | The upstream direction; needs a separate plugin operator (+ cert-manager) install. The right long-term target |
| **In-tree `barmanObjectStore`** ✅ (for now) | Zero extra install, works today. **Deprecated upstream, removed in CNPG 1.31** — so CNPG is **held at ≤1.30** (Makefile note) until migrated. Accepted as the pragmatic start |

**Object / file layer** (SeaweedFS: media, attachments, telemetry archive):
**`restic`** ✅ — incremental, deduplicated, **client-side encrypted**,
append-only repositories. (Plain sync/copy ❌ — no dedup, no encryption, no
append-only protection.)

**Ransomware resistance** (the decisive axis):

| Option | Assessment |
|---|---|
| Retention policy alone ❌ | A retention window an attacker with credentials can shorten or delete is not protection |
| **Object-Lock / WORM + write-only backup identity** ✅ | A backup, once written, **cannot be altered or deleted before retention expires — even with stolen admin credentials**; the platform's backup credential can *write* but not *delete*, so a compromised cluster cannot wipe its own restore points |

**Backup target location:** in-cluster/same-node proves the *mechanism* only (it
shares the failure domain — not DR). The target must be **durable, off-node,
immutable, and on a *different provider*** from the core infra — so a compromise
or outage of the primary cloud account cannot take the platform *and* its
backups at once (the "offsite" leg of 3-2-1-1-0). Provisioned by IaC.

| Offsite provider | Assessment |
|---|---|
| Same provider, another bucket/region ❌ | Solves node loss, not provider-account compromise or provider outage — still one basket |
| **DigitalOcean Spaces** ❌ | Different provider ✓, simple, cheap — but **no S3 Object Lock / WORM** (verified 2026), so a stolen full key can still delete backups; only client-side (restic) protection is possible |
| **Backblaze B2** ✅ | **Different provider ✓ AND Object-Lock / WORM ✓**, typically the cheapest S3-compatible option — satisfies cross-provider separation *and* immutability at once |
| Wasabi | Also different-provider + Object-Lock; flat no-egress pricing — the alternative if that pricing model fits better |

## Decision

**Layered by data class**, with recoverability treated as first-class:

- **PostgreSQL** → CNPG **base backups + continuous WAL archiving** to S3
  (in-tree `barmanObjectStore`, held at CNPG ≤1.30), `retentionPolicy`, a daily
  `ScheduledBackup`. **Point-in-time recovery.** Restore is always into a **new**
  cluster (the corrupt volume is left intact for forensics), and is **verified by
  a drill** (`make dev-restore-verify` recovers a throwaway cluster and checks row
  counts) — the 0 in 3-2-1-1-0.
- **Object / file layer** → `restic` (encrypted, append-only, incremental).
- **ClickHouse / OpenSearch** → engine-native snapshots to S3 (largely
  re-derivable from Postgres + objects; snapshotted mainly to shorten RTO).

**Ransomware controls, in priority order:** Object-Lock/WORM immutable storage;
separate **write-only** backup identity; client-side encryption; **off-node /
offsite** copies (3-2-1-1-0); MFA-delete or air-gapped pull; and a
**`PostgresBackupFailed` alert** (ADR 0011) so a degraded safety net pages
instead of surprising you at restore time
([runbook](../runbooks/backup-failure.md)).

**Offsite target: Backblaze B2** — a *different provider* from the Hetzner core
(so the primary account/provider and the backups never share a blast radius) that
*also* supports Object-Lock/WORM. DigitalOcean Spaces was considered for the
cross-provider separation but rejected as the sole target because it has no Object
Lock. `restic` still provides client-side encryption + append-only on top.

**The DR substrate is provisioned by IaC** (ADR 0012): the immutable off-provider
bucket, its Object-Lock/lifecycle policy, and the write-only backup identity are
version-controlled infrastructure per environment — reproducible and auditable,
not a manual runbook. This decouples cleanly from the core-infra provider choice
(the cluster + private network is one placement decision; the backup target is
another) — a hybrid, provider-portable topology. Full strategy:
[deploy/k8s/DISASTER-RECOVERY.md](https://github.com/marco-montesines/maagaparuga/blob/master/deploy/k8s/DISASTER-RECOVERY.md).

## Consequences

- **Verified today (dev):** Postgres continuous archiving + on-demand backup, and
  a **full restore** (recovery cluster, matching row counts across app / ZITADEL /
  OpenFGA databases). The backup-failure alert fires and auto-resolves.
- **Version constraint:** CNPG is pinned/held at ≤1.30 until the cluster migrates
  to the Barman Cloud Plugin; the auto-version-bump (ADR 0013) must not cross 1.31
  before then. A concrete instance of ADR 0013's "is upstream alive / stable"
  review gate.
- **Dev is not DR:** local backups land in-cluster on the same node — they prove
  the mechanism. Real disaster recovery depends on the **cloud overlays**
  repointing at durable, immutable, off-node storage (**P6**).
- **Not yet implemented:** ClickHouse (`clickhouse-backup`) and OpenSearch
  (snapshot API) backups, the restic object-layer job, and the immutable-storage +
  split-credential provisioning — all scheduled with the cloud overlays (P6);
  designed in the DR doc.
- **Revisit when:** CNPG forces the plugin migration (≤1.31 boundary); a second
  provider/account is added for true air-gap; or restore drills are wired into
  scheduled CI so "0 restore errors" is continuously proven.
