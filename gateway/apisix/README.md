# gateway/apisix — Apache APISIX (standalone mode)

Single entry point for the platform: routing to the web application and services,
edge authentication, gRPC proxying + REST transcoding — and (still to come) TLS
termination, rate limiting, and security headers. Runs in standalone mode
(YAML-driven configuration, no etcd) to stay lightweight on a single small VM.

The live configuration is the ConfigMap in
[`deploy/k8s/base/apisix/apisix.yaml`](../../deploy/k8s/base/apisix/apisix.yaml)
(routes + the compiled gRPC descriptor set); this directory holds the standalone
config as it moves toward a per-environment layout.

**Status (P5 partial, 2026-07-23):** routing live; **edge authentication** enforced
on the REST telemetry routes via the `openid-connect` plugin (bearer-only + JWKS
against ZITADEL) — anonymous/invalid → `401`, valid token validated *and* forwarded
so the service re-checks. Web app + ZITADEL login stay open (browser sessions, not
bearer tokens). Native gRPC *streaming* edge-auth is a known limitation (openid-connect
doesn't reject it) — gated at the telemetry service instead. **Still to do:** TLS
(per-env cert), rate limiting, security headers, the `/graphql` route. See the
platform README for the overview and the build plan for the full P5 scope.
