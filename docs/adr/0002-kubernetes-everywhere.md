# 0002 — Kubernetes in every environment (minikube / k3s)

Status: **Accepted**

## Context

The platform runs in three environments: a developer machine, an ephemeral staging VM,
and a production VM — each a single small host. We want every environment to run the
*same* deployment artifacts so that a staging deploy is a genuine rehearsal of
production.

## Options considered

- **Docker Compose on the cloud VMs** — simplest single-host option; rejected because it
  forks the deployment model (Compose in the cloud, something else locally), has no
  resource-limit/health/restart semantics comparable to Kubernetes, and demonstrates
  less transferable practice.
- **Full Kubernetes distribution (kubeadm)** — rejected: control-plane overhead and
  operational surface far beyond what single-node hosts need.
- **Kubernetes everywhere via minikube (dev) + k3s (cloud)** ✅ — one manifest set
  (Kustomize base + per-environment overlays), k3s is a CNCF-certified lightweight
  distribution that fits a small VM.

## Decision

Kustomize base + overlays in `deploy/k8s/`; minikube locally, single-node k3s on the
cloud VMs, installed by Ansible. Node counts and sizes are overlay variables.

## Consequences

- Identical manifests everywhere; environment differences are variables, not forks.
- The production 3-node cluster can run an HA control plane (3 servers) or a single
  server node with 2 agents — a per-environment sizing choice, not a code change.
- Revisit when: multiple nodes per environment become the norm (k3s scales to
  multi-node; beyond that, a managed Kubernetes service becomes the comparison).
