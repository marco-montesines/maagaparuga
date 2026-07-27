# 0003 — Apache APISIX as the API gateway

Status: **Accepted**

## Context

One public entry point must terminate TLS, route to four backends, enforce OIDC
authentication, rate-limit, proxy gRPC, and expose a gRPC service as REST — fully open source, on
nodes sized for a 3-node cluster.

## Options considered

- **Kong** — long the OSS default; rejected because many practically-needed features
  (advanced auth, RBAC, analytics) have moved to the Enterprise edition, weakening the
  fully-open-source story.
- **Traefik** — excellent edge router/ingress; rejected as the *gateway* because API
  policy features (rich auth, transformation, gRPC↔REST transcoding) are thinner —
  it is a reverse proxy first, not an API-management layer.
- **Envoy Gateway** — powerful and CNCF-backed; rejected: higher complexity with no
  needed capability beyond APISIX.
- **KrakenD** — very fast aggregation gateway; rejected: less flexible plugin model.
- **Apache APISIX** ✅ — ASF top-level project, Apache-2.0, NGINX/OpenResty core,
  standalone YAML mode (no etcd — fits one VM), `openid-connect` plugin, native gRPC
  proxying plus `grpc-transcode`, rate limiting, Prometheus plugin.

## Decision

APISIX in standalone mode, configuration in `gateway/apisix/`, one config file per
environment concern. TLS terminates here (Let's Encrypt wildcard for the configured
base domain).

## Consequences

- OIDC enforcement, gRPC transcoding, and metrics come from maintained plugins rather
  than custom code.
- Revisit when: a service mesh or Kubernetes Gateway API adoption changes where these
  responsibilities live.
