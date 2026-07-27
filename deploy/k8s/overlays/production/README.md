# production overlay

Applied by the Ansible `deploy` role (`kubectl apply -k overlays/production`) once
the cluster is up. `kubectl kustomize` builds this with no secrets; the pods stay
pending until you provision the secrets below (nothing sensitive is committed).

## Hostname + real HTTPS (DuckDNS + Caddy + Let's Encrypt)

The public hostname is `maagaparuga.duckdns.org` (staging: `staging-maagaparuga.duckdns.org`).
Point its DuckDNS **A record at a node's public IP** (DuckDNS UI, or the update URL
`https://www.duckdns.org/update?domains=maagaparuga&token=<token>&ip=<node-ip>`).

`Caddy` is the public edge: on first traffic it obtains a **real Let's Encrypt
cert** (HTTP-01 — needs the A record + open :80, both satisfied) and auto-renews
it, terminating HTTPS and proxying to APISIX. Test with LE **staging** first
(uncomment `acme_ca` in `caddy.yaml`) to avoid rate limits, then switch to real.

In-cluster, add a CoreDNS rewrite (`maagaparuga.duckdns.org` -> the `caddy`
service) so the single-host OIDC issuer resolves to the TLS edge for services too
(same idea as dev's `make dev-dns`).

## Secrets to provision at deploy (real values, never committed)

Create these before/right after `apply` — from a gitignored `secrets/*.env`, a
`kubectl create secret` script, or SealedSecrets:

| Secret | Keys | Notes |
|---|---|---|
| `maagaparuga-pg-app`, `pg-zitadel-credentials`, `pg-openfga-credentials` | DB creds | strong per-install passwords |
| `openfga-datastore` | `uri` | postgres DSN for OpenFGA |
| `clickhouse-credentials`, `opensearch-credentials`, `redis-credentials` | user/pass | |
| `seaweedfs-s3-config` | `s3-config.json` | object-store identities |
| `zitadel-masterkey` | `masterkey` | exactly 32 bytes |
| `web-secrets` | `APP_KEY`, `ZITADEL_CLIENT_*`, `OPENFGA_STORE_ID`, `OPENFGA_MODEL_ID` | filled by the bootstrap step |
| `telemetry-secrets` | `DEVICE_CLIENT_*` | from bootstrap (device-auth) |
| `media-s3` | `S3_ACCESS_KEY`, `S3_SECRET_KEY` | media object store |
| `grafana-admin` | user/pass | |
| **`pg-backup-s3`** | `ACCESS_KEY_ID`, `ACCESS_SECRET_KEY` | **Backblaze B2 app key** (offsite WORM backups → `s3://maagaparuga-pg-backups/`) |

Then run the bootstrap (`make dev-bootstrap` equivalent against this cluster:
ZITADEL project/clients + `fga:bootstrap` + inject store/model), device-auth, and
media-auth so `AUTH_MODE=jwt` has its issuer + OpenFGA ids.

## Staged hardening (tracked)

- **OpenSearch security plugin** — off by design (OpenSearch is cluster-internal
  only: ClusterIP, no edge route, firewall default-deny, so access is governed by
  network isolation). Enabling it (in-cluster TLS + per-client auth) is optional
  defense-in-depth, deferred + documented.
- **True multi-node** OpenSearch / ClickHouse / NATS / SeaweedFS clustering
  (single-node today; Postgres is already 3-instance HA).

(TLS is done — Caddy serves a real Let's Encrypt cert at the edge.)
