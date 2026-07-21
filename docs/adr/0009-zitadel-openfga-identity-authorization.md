# 0009 — ZITADEL (OIDC) + OpenFGA for identity and authorization

Date: 2026-07-20 · Status: **Accepted**

## Context

Six care-team roles need authentication and — more interestingly — *fine-grained*
authorization: not "is this user a caregiver" but "may **this** caregiver view **this**
care recipient's media". Coarse roles and per-resource permissions are different
problems and deserve different tools.

## Options considered

**Identity provider:**

- **In-app framework auth** (argon2id + policies) — zero extra components, ships
  fastest; rejected: demonstrates no standards-based OIDC/SSO architecture, and every
  service would need its own session story.
- **Keycloak** — the enterprise standard with the richest built-in authorization
  engine; rejected: JVM-heavy (~1.5 GB+), the worst fit for a small single VM.
- **Logto / Ory / Authentik** — credible alternatives; not shortlisted: each trades
  away either enterprise signal or operational simplicity without beating ZITADEL for
  this stack.
- **ZITADEL** ✅ — Go binary storing state in the existing PostgreSQL; OIDC with PKCE,
  passkeys, roles/organizations via claims; enforced at the gateway by APISIX's
  `openid-connect` plugin; native-app flows for device clients.

**Fine-grained authorization:**

- **Keycloak Authorization Services** — capable but couples authz to the heaviest IdP
  option.
- **Ory Keto** — Zanzibar-style, viable; OpenFGA chosen for its first-class gRPC API,
  modeling language/tooling, and IdP-agnostic pairing.
- **OpenFGA** ✅ — relationship-based (Google-Zanzibar-style) authorization as data:
  caregiver↔care-recipient assignments, transcriptionist scopes; checked from services
  over gRPC; state in PostgreSQL.

## Decision

ZITADEL owns identity (no local password store anywhere in the platform); OpenFGA owns
resource-level permissions. Coarse role → claim; fine-grained question → OpenFGA check.
Mock personas are seeded into ZITADEL and their relationships into OpenFGA.

## Consequences

- Two additional components (~1 GB combined) — a driver of the mid-size production VM.
- Every service validates the same JWTs (ZITADEL JWKS) — one auth story across three
  languages; OpenFGA checks are also the second real gRPC consumer (ADR 0010).
- Revisit when: an organization deploying this already operates a different IdP —
  everything downstream is standard OIDC, so the IdP is swappable.
