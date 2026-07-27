# 0001 — Record architecture decisions as ADRs

Status: **Accepted**

## Context

MaagapAruga is a production-grade, open-source care platform whose value lies as much
in *why* it is built this way as in what it does. Several major choices here went
against the "default famous option" (no Kafka, no Loki, no Keycloak, no dedicated
vector database, no service mesh) — decisions like that are only defensible if the
reasoning is written down where a reader can audit it.

## Options considered

- **No decision records** — reasoning lives in commit messages and heads. Rejected:
  evaporates immediately.
- **One monolithic ARCHITECTURE.md** — rejected: goes stale as a whole, buries
  individual decisions, has no lifecycle (accepted/superseded).
- **ADRs (this)** — one dated record per decision with options, rejections, and
  revisit triggers; superseded records stay in place and link forward.

## Decision

Record every significant architectural decision as a numbered, dated,
lightweight-MADR-style file in `docs/adr/`. Each ADR must name the **rejected
alternatives and the reasons**, and state the **conditions that would reopen the
decision**.

## Consequences

- The README carries only the summary ("The decided stack at a glance" and "Why this
  architecture") and links here for depth.
- Changing a decision means writing a new ADR that supersedes the old one — the history
  of reasoning is preserved.
