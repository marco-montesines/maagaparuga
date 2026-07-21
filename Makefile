# MaagapAruga — developer entry points.
# `make dev` brings up the full platform on minikube (P1 scope: data layer,
# broker, identity stack, gateway; app services activate as P2-P4 land).

MINIKUBE_MEMORY ?= 7g
MINIKUBE_CPUS   ?= 4
NAMESPACE       := maagaparuga
DEV_OVERLAY     := deploy/k8s/overlays/dev
COMPOSE_STORES  := deploy/compose/stores.compose.yml
TELEMETRY_IMAGE := ghcr.io/marco-montesines/maagaparuga-telemetry:dev

# CloudNativePG operator — pinned release manifest (ADR 0005, 0013).
CNPG_VERSION  ?= 1.30.0
CNPG_MANIFEST := https://github.com/cloudnative-pg/cloudnative-pg/releases/download/v$(CNPG_VERSION)/cnpg-$(CNPG_VERSION).yaml

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: dev
dev: ## Start minikube (if needed), install CNPG operator, deploy the dev overlay
	@minikube status >/dev/null 2>&1 || minikube start --memory=$(MINIKUBE_MEMORY) --cpus=$(MINIKUBE_CPUS)
	kubectl apply --server-side -f $(CNPG_MANIFEST)
	kubectl -n cnpg-system rollout status deployment/cnpg-controller-manager --timeout=120s
	kubectl apply -k $(DEV_OVERLAY)
	@echo "---"
	@kubectl -n $(NAMESPACE) get pods
	@echo "---"
	@echo "Gateway (APISIX): 'make dev-gateway' then http://localhost:9080/healthz"
	@echo "(Linux hosts can also reach NodePort http://$$(minikube ip):30080 directly;"
	@echo " on macOS's docker driver the minikube IP is not host-routable.)"

.PHONY: dev-gateway
dev-gateway: ## Port-forward the APISIX gateway to http://localhost:9080
	kubectl -n $(NAMESPACE) port-forward svc/apisix 9080:9080

# ClusterIPs (10.x.x.x) are virtual, in-cluster-only addresses — from the host,
# always go through a port-forward (on macOS's docker driver even the node IP
# is not routable). Usage: make dev-forward SVC=opensearch PORT=9200
.PHONY: dev-forward
dev-forward: ## Port-forward any service: make dev-forward SVC=opensearch PORT=9200
	kubectl -n $(NAMESPACE) port-forward svc/$(SVC) $(PORT):$(PORT)

.PHONY: dev-expose
dev-expose: ## Port-forward EVERY service to localhost (Ctrl-C stops all)
	@# Clean up stale forwards first — they hold the ports and cause
	@# "address already in use". Well-known ports that other local projects
	@# commonly claim (5432, ...) are mapped to offset ports instead.
	-@pkill -f "kubectl -n $(NAMESPACE) port-forward" 2>/dev/null; sleep 1
	@echo "Forwarding all services to localhost (dev only, Ctrl-C stops all):"
	@echo "  APISIX gateway     http://localhost:9080"
	@echo "  PostgreSQL         localhost:15432   (offset: 5432 often taken by other projects)"
	@echo "  ClickHouse         http://localhost:8123  (native localhost:9001)"
	@echo "  OpenSearch         http://localhost:9200"
	@echo "  Redis              localhost:6379"
	@echo "  SeaweedFS S3       http://localhost:8333  (master http://localhost:9333, filer http://localhost:8888)"
	@echo "  NATS               localhost:4222  (monitor http://localhost:8222)"
	@echo "  ZITADEL            http://localhost:8080"
	@echo "  OpenFGA HTTP       http://localhost:8082  (gRPC localhost:8081)"
	@trap 'kill 0' INT TERM; \
	kubectl -n $(NAMESPACE) port-forward svc/apisix 9080:9080 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/maagaparuga-pg-rw 15432:5432 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/clickhouse 8123:8123 9001:9000 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/opensearch 9200:9200 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/redis 6379:6379 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/seaweedfs 8333:8333 9333:9333 8888:8888 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/nats 4222:4222 8222:8222 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/zitadel 8080:8080 >/dev/null & \
	kubectl -n $(NAMESPACE) port-forward svc/openfga 8082:8080 8081:8081 >/dev/null & \
	wait

.PHONY: dev-simulate
dev-simulate: ## Stream mock IoMT device vitals into the telemetry service (SAMPLES=n, BURST=1)
	kubectl -n $(NAMESPACE) run telemetry-sim-$$RANDOM \
		--rm -i --restart=Never --image=$(TELEMETRY_IMAGE) \
		-- simulate -target telemetry:9090 -total $(or $(SAMPLES),40) \
		$(if $(BURST),-burst,-interval 500ms)

.PHONY: dev-smoke
dev-smoke: ## Post-deploy smoke test: every service answered through its own entry point
	@echo "== gateway"
	@kubectl -n $(NAMESPACE) exec deploy/web -- \
		curl -fsS -m 5 http://apisix:9080/healthz >/dev/null && echo "   APISIX /healthz ok"
	@echo "== web (PHP)"
	@kubectl -n $(NAMESPACE) exec deploy/web -- \
		curl -fsS -m 5 -o /dev/null -w "   /up %{http_code}\n" http://localhost:8080/up
	@kubectl -n $(NAMESPACE) exec deploy/web -- \
		curl -fsS -m 5 -o /dev/null -w "   gateway->web %{http_code}\n" http://apisix:9080/up
	@echo "== telemetry (Go)"
	@kubectl -n $(NAMESPACE) get deploy/telemetry -o jsonpath='{.status.readyReplicas}' | \
		grep -q 1 && echo "   ingest ready"
	@kubectl -n $(NAMESPACE) get deploy/telemetry-writer -o jsonpath='{.status.readyReplicas}' | \
		grep -q 1 && echo "   writer ready"
	@echo "== stores"
	@kubectl -n $(NAMESPACE) exec clickhouse-0 -- \
		clickhouse-client --user $$CH_USER --password $$CH_PASS \
		-q "SELECT count() FROM maagaparuga.vitals" 2>/dev/null \
		| sed 's/^/   vitals rows: /' || echo "   vitals table not created yet"
	@echo "(assessment + media join this suite in P4/P4b)"

.PHONY: dev-status
dev-status: ## Show pods, services, and PVCs in the dev cluster
	kubectl -n $(NAMESPACE) get pods,svc,pvc

.PHONY: dev-wait
dev-wait: ## Block until all deployed pods are ready
	kubectl -n $(NAMESPACE) wait --for=condition=Ready pods --all --timeout=300s

.PHONY: dev-down
dev-down: ## Remove the MaagapAruga stack (keeps minikube + CNPG operator running)
	kubectl delete -k $(DEV_OVERLAY) --ignore-not-found

.PHONY: dev-destroy
dev-destroy: ## Delete the whole minikube cluster
	minikube delete

.PHONY: stores-up
stores-up: ## Data stores only, via Docker Compose (fast iteration while coding one service)
	docker compose -f $(COMPOSE_STORES) up -d

.PHONY: stores-down
stores-down: ## Stop the Compose data stores (volumes preserved)
	docker compose -f $(COMPOSE_STORES) down

.PHONY: proto-check
proto-check: ## Fail if the gateway's inlined proto has drifted from proto/
	@python3 -c "import sys,re; \
	src=[l for l in open('proto/maagaparuga/telemetry/v1/vitals.proto') if l.strip() and not l.strip().startswith('//')]; \
	cfg=open('deploy/k8s/base/apisix/apisix.yaml').read(); \
	inlined=[l.strip() for l in cfg.split('content: |')[1].split('routes:')[0].splitlines() if l.strip()]; \
	a=[l.strip() for l in src]; \
	sys.exit(0) if a==inlined else (print('gateway proto is out of sync with proto/ — re-inline it'), sys.exit(1))"
	@echo "gateway proto in sync"

.PHONY: kustomize-check
kustomize-check: ## Render all overlays to verify they build
	kubectl kustomize $(DEV_OVERLAY) > /dev/null && echo "dev overlay: OK"
