# 0013 — Latest stable releases, pinned exactly

Date: 2026-07-20 · Status: **Accepted**

## Context

Component versions are a functional decision here, not hygiene: the vector pipeline
requires the current OpenSearch 3.x generation (ingest-time chunking/embedding, hybrid
search), and equivalents hold across the stack.

## Options considered

- **Floating `latest` tags** — rejected: non-reproducible deploys, surprise breakage.
- **Conservative old-but-stable pins** — rejected: forfeits the exact functionality
  several decisions depend on (ADR 0006, 0008).
- **Latest stable, pinned to exact versions, refreshed by automation** ✅.

## Decision

Every component (container images, charts, language dependencies, actions) is pinned to
an exact current stable version. Automated dependency updates (Dependabot/Renovate)
propose refreshes continuously; CI gates them. GitHub Actions follow the convention:
first-party pinned by major tag, third-party by full commit SHA.

## Consequences

- Reproducible environments with current functionality; upgrades arrive as small,
  reviewable, continuous PRs instead of rare big-bang migrations.
- The cluster overlay and single-node overlay track the same versions — no drift
  between demonstrated shapes.
