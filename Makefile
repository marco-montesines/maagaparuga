
# MaagapAruga — developer entry points.
# `make dev` brings up the full platform on minikube (P1 scope: data layer,
# broker, identity stack, gateway; app services activate as P2-P4 land).

BUF ?= $(shell command -v buf 2>/dev/null || echo $(HOME)/go/bin/buf)

MINIKUBE_MEMORY ?= 7g
MINIKUBE_CPUS   ?= 4
NAMESPACE       := maagaparuga
DEV_OVERLAY     := deploy/k8s/overlays/dev
COMPOSE_STORES  := deploy/compose/stores.compose.yml
TELEMETRY_IMAGE := ghcr.io/marco-montesines/maagaparuga-telemetry:dev
WEB_IMAGE       := ghcr.io/marco-montesines/maagaparuga-web:dev
MEDIA_IMAGE     := ghcr.io/marco-montesines/maagaparuga-media:dev

# CloudNativePG operator — pinned release manifest (ADR 0005, 0013).
# HOLD at <=1.30.x: Postgres backups use the in-tree barmanObjectStore, which
# CNPG removes in 1.31.0. Bumping past 1.30 needs migrating cluster.yaml to the
# Barman Cloud Plugin first (see the backup notes in the deploy docs). Do not let the
# auto-version-bump cross 1.31 until that migration lands.
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
	@CID=$$(kubectl -n $(NAMESPACE) get secret telemetry-secrets -o jsonpath='{.data.DEVICE_CLIENT_ID}' 2>/dev/null | base64 -d); \
	SEC=$$(kubectl -n $(NAMESPACE) get secret telemetry-secrets -o jsonpath='{.data.DEVICE_CLIENT_SECRET}' 2>/dev/null | base64 -d); \
	ISS=$$(kubectl -n $(NAMESPACE) get cm telemetry-config -o jsonpath='{.data.OIDC_ISSUER}' 2>/dev/null); \
	AUD=$$(kubectl -n $(NAMESPACE) get cm telemetry-config -o jsonpath='{.data.OIDC_AUDIENCE}' 2>/dev/null); \
	kubectl -n $(NAMESPACE) run telemetry-sim-$$RANDOM \
		--rm -i --restart=Never --image=$(TELEMETRY_IMAGE) \
		--env="OIDC_ISSUER=$$ISS" --env="OIDC_AUDIENCE=$$AUD" \
		--env="DEVICE_CLIENT_ID=$$CID" --env="DEVICE_CLIENT_SECRET=$$SEC" \
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

.PHONY: dev-bootstrap
dev-bootstrap: ## Configure ZITADEL + OpenFGA and inject client id/secret + store ids into the running cluster
	@echo "Running ZITADEL bootstrap Job (project, roles, web client, telemetry SA, mock users)..."
	kubectl -n $(NAMESPACE) delete job zitadel-bootstrap --ignore-not-found >/dev/null 2>&1 || true
	kubectl apply -k $(DEV_OVERLAY) >/dev/null
	kubectl -n $(NAMESPACE) wait --for=condition=complete job/zitadel-bootstrap --timeout=120s
	@echo "Bootstrapping OpenFGA store + model and injecting into web-secrets..."
	@OUT="$$(kubectl -n $(NAMESPACE) exec deploy/web -- php artisan fga:bootstrap 2>/dev/null | grep OPENFGA_)"; \
	STORE=$$(printf '%s' "$$OUT" | sed -n 's/.*OPENFGA_STORE_ID=\([A-Za-z0-9]*\).*/\1/p'); \
	MODEL=$$(printf '%s' "$$OUT" | sed -n 's/.*OPENFGA_MODEL_ID=\([A-Za-z0-9]*\).*/\1/p'); \
	if [ -n "$$STORE" ]; then \
		kubectl -n $(NAMESPACE) patch secret web-secrets --type merge \
			-p "{\"stringData\":{\"OPENFGA_STORE_ID\":\"$$STORE\",\"OPENFGA_MODEL_ID\":\"$$MODEL\"}}" >/dev/null; \
		kubectl -n $(NAMESPACE) rollout restart deployment/web >/dev/null; \
		kubectl -n $(NAMESPACE) rollout status deployment/web --timeout=180s; \
		echo "OpenFGA store $$STORE wired into web — fga:grant + dev-device-auth + dev-media-auth now work."; \
	else echo "WARN: could not parse the OpenFGA store id from fga:bootstrap"; fi
	@echo "---"
	@echo "Still manual (runtime values, never committed): the ZITADEL web client"
	@echo "id/secret + telemetry audience from"
	@echo "  kubectl -n $(NAMESPACE) logs job/zitadel-bootstrap"
	@echo "Then 'make dev-seed' to load mock data."

.PHONY: dev-seed
dev-seed: ## Load mock data (users already seeded by bootstrap; this adds records + vitals + FGA tuples) — usable in ANY env to validate a deployment
	kubectl -n $(NAMESPACE) exec deploy/web -- php artisan migrate --force
	kubectl -n $(NAMESPACE) exec deploy/web -- php artisan db:seed --force
	kubectl -n $(NAMESPACE) exec deploy/web -- php artisan fga:sync
	$(MAKE) dev-simulate SAMPLES=48

.PHONY: dev-device-auth
dev-device-auth: ## Turn ON device (IoMT) auth: telemetry verifies device tokens + OpenFGA authorizes the device (needs dev-bootstrap first)
	@LOG="$$(kubectl -n $(NAMESPACE) logs job/zitadel-bootstrap 2>/dev/null)"; \
	PROJ=$$(printf '%s' "$$LOG" | sed -n 's/.*"telemetry_project_id": "\([^"]*\)".*/\1/p'); \
	SUB=$$(printf '%s' "$$LOG"  | sed -n 's/.*"telemetry_user_id": "\([^"]*\)".*/\1/p'); \
	CID=$$(printf '%s' "$$LOG"  | sed -n 's/.*"telemetry_client_id": "\([^"]*\)".*/\1/p'); \
	SEC=$$(printf '%s' "$$LOG"  | sed -n 's/.*"telemetry_client_secret": "\([^"]*\)".*/\1/p'); \
	STORE=$$(kubectl -n $(NAMESPACE) exec deploy/web -- printenv OPENFGA_STORE_ID 2>/dev/null); \
	MODEL=$$(kubectl -n $(NAMESPACE) exec deploy/web -- printenv OPENFGA_MODEL_ID 2>/dev/null); \
	if [ -z "$$PROJ" ] || [ -z "$$SEC" ] || [ -z "$$STORE" ]; then \
		echo "missing bootstrap output (project/secret/store) — run 'make dev-bootstrap' first"; exit 1; fi; \
	echo "Injecting device credentials (runtime-only, never committed)..."; \
	kubectl -n $(NAMESPACE) patch secret telemetry-secrets --type merge \
		-p "{\"stringData\":{\"DEVICE_CLIENT_ID\":\"$$CID\",\"DEVICE_CLIENT_SECRET\":\"$$SEC\"}}" >/dev/null; \
	echo "Authorizing the device to stream vitals for mock recipients 1-4..."; \
	kubectl -n $(NAMESPACE) exec deploy/web -- php artisan fga:grant $$SUB device 1 2 3 4; \
	echo "Flipping telemetry to AUTH_MODE=jwt (audience=$$PROJ)..."; \
	kubectl -n $(NAMESPACE) patch configmap telemetry-config --type merge \
		-p "{\"data\":{\"AUTH_MODE\":\"jwt\",\"OIDC_AUDIENCE\":\"$$PROJ\",\"OPENFGA_STORE_ID\":\"$$STORE\",\"OPENFGA_MODEL_ID\":\"$$MODEL\"}}" >/dev/null; \
	kubectl -n $(NAMESPACE) rollout restart deployment/telemetry >/dev/null; \
	kubectl -n $(NAMESPACE) rollout status deployment/telemetry --timeout=120s
	@echo "Device auth ON. 'make dev-simulate' now streams as an authenticated device."

.PHONY: dev-assessment-grpc
dev-assessment-grpc: ## Switch the assessment vitals reader from ClickHouse to the telemetry gRPC API (needs a bootstrap that provisions the assessment SA + service_reader model)
	@LOG="$$(kubectl -n $(NAMESPACE) logs job/zitadel-bootstrap 2>/dev/null)"; \
	PROJ=$$(printf '%s' "$$LOG" | sed -n 's/.*"telemetry_project_id": "\([^"]*\)".*/\1/p'); \
	SUB=$$(printf '%s' "$$LOG"  | sed -n 's/.*"assessment_user_id": "\([^"]*\)".*/\1/p'); \
	CID=$$(printf '%s' "$$LOG"  | sed -n 's/.*"assessment_client_id": "\([^"]*\)".*/\1/p'); \
	SEC=$$(printf '%s' "$$LOG"  | sed -n 's/.*"assessment_client_secret": "\([^"]*\)".*/\1/p'); \
	ISS=$$(kubectl -n $(NAMESPACE) get cm telemetry-config -o jsonpath='{.data.OIDC_ISSUER}' 2>/dev/null); \
	if [ -z "$$PROJ" ] || [ -z "$$SEC" ] || [ -z "$$SUB" ]; then \
		echo "missing assessment SA in bootstrap output — rebuild the bootstrap image + 'make dev-bootstrap' first"; exit 1; fi; \
	echo "Authorizing the assessment service to READ vitals for mock recipients 1-4 (service_reader, read-only)..."; \
	kubectl -n $(NAMESPACE) exec deploy/web -- php artisan fga:grant $$SUB service_reader 1 2 3 4; \
	echo "Minting the assessment M2M token (client_credentials, audience=$$PROJ)..."; \
	TOKEN=$$(kubectl -n $(NAMESPACE) exec deploy/web -- curl -s -m10 \
		-u "$$CID:$$SEC" \
		-d grant_type=client_credentials \
		--data-urlencode "scope=openid urn:zitadel:iam:org:project:id:$$PROJ:aud" \
		"$$ISS/oauth/v2/token" \
		| sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'); \
	if [ -z "$$TOKEN" ]; then echo "token mint failed (is the assessment SA active?)"; exit 1; fi; \
	echo "Injecting the bearer + flipping VITALS_READER=grpc (runtime-only, never committed)..."; \
	kubectl -n $(NAMESPACE) set env deployment/assessment \
		VITALS_READER=grpc TELEMETRY_GRPC=telemetry:9090 TELEMETRY_TOKEN="$$TOKEN" >/dev/null; \
	kubectl -n $(NAMESPACE) rollout status deployment/assessment --timeout=120s
	@echo "Assessment now reads vitals over gRPC. 'make dev-assessment' scores through that path."
	@echo "(the token expires — re-run to refresh; 'kubectl set env deployment/assessment VITALS_READER=clickhouse TELEMETRY_TOKEN-' reverts to the tokenless default.)"

.PHONY: dev-backup
dev-backup: ## Take an on-demand Postgres base backup now (WAL archives continuously between backups)
	@NAME=ondemand-$$(kubectl -n $(NAMESPACE) get backup -o name 2>/dev/null | wc -l | tr -d ' '); \
	printf 'apiVersion: postgresql.cnpg.io/v1\nkind: Backup\nmetadata:\n  name: %s\n  namespace: $(NAMESPACE)\nspec:\n  method: barmanObjectStore\n  cluster:\n    name: maagaparuga-pg\n' "$$NAME" | kubectl apply -f -; \
	echo "Watching backup $$NAME ..."; \
	for i in $$(seq 1 24); do PH=$$(kubectl -n $(NAMESPACE) get backup $$NAME -o jsonpath='{.status.phase}' 2>/dev/null); \
	  echo "  phase=$$PH"; case "$$PH" in completed) break;; failed) exit 1;; esac; sleep 5; done

.PHONY: dev-restore-verify
dev-restore-verify: ## Restore DRILL: recover a throwaway cluster from the S3 backup, check row counts match, tear it down
	@echo "Source app.users: $$(kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -d app -tAc 'select count(*) from users;' 2>/dev/null | tr -d ' ')"
	@printf 'apiVersion: postgresql.cnpg.io/v1\nkind: Cluster\nmetadata:\n  name: maagaparuga-pg-restore\n  namespace: $(NAMESPACE)\nspec:\n  instances: 1\n  imageName: ghcr.io/cloudnative-pg/postgresql:18.4\n  storage: {size: 2Gi}\n  resources: {requests: {cpu: 100m, memory: 256Mi}, limits: {memory: 512Mi}}\n  bootstrap: {recovery: {source: pg-origin}}\n  externalClusters:\n    - name: pg-origin\n      barmanObjectStore:\n        serverName: maagaparuga-pg\n        destinationPath: s3://pg-backups/\n        endpointURL: http://seaweedfs:8333\n        s3Credentials: {accessKeyId: {name: pg-backup-s3, key: ACCESS_KEY_ID}, secretAccessKey: {name: pg-backup-s3, key: ACCESS_SECRET_KEY}}\n        wal: {compression: gzip}\n' | kubectl apply -f - >/dev/null
	@echo "Restoring..."; \
	for i in $$(seq 1 36); do R=$$(kubectl -n $(NAMESPACE) get cluster maagaparuga-pg-restore -o jsonpath='{.status.readyInstances}' 2>/dev/null); \
	  [ "$$R" = "1" ] && break; sleep 5; done; \
	echo "Restored app.users: $$(kubectl -n $(NAMESPACE) exec maagaparuga-pg-restore-1 -c postgres -- psql -U postgres -d app -tAc 'select count(*) from users;' 2>/dev/null | tr -d ' ')"; \
	kubectl -n $(NAMESPACE) delete cluster maagaparuga-pg-restore >/dev/null 2>&1; echo "drill cluster torn down (S3 backups retained)"

.PHONY: dev-assessment
dev-assessment: ## Demo the assessment service end-to-end: seed a questionnaire, stream vitals, score (NEWS2/DASS-21/risk), show results + alerts (recipient 1)
	@echo "Seeding a DASS-21 questionnaire for care recipient 1..."
	@printf '%s\n' \
	  "INSERT INTO questionnaire_responses (care_recipient_id, instrument, answers, submitted_at, created_at, updated_at)" \
	  "VALUES (1, 'dass21', '{\"1\":2,\"2\":1,\"3\":3,\"4\":1,\"5\":3,\"6\":2,\"7\":1,\"8\":2,\"9\":1,\"10\":3,\"11\":2,\"12\":2,\"13\":3,\"14\":2,\"15\":1,\"16\":3,\"17\":3,\"18\":2,\"19\":1,\"20\":1,\"21\":3}', now(), now(), now());" \
	  | kubectl -n $(NAMESPACE) exec -i maagaparuga-pg-1 -c postgres -- psql -U postgres -d app -q >/dev/null
	@echo "Streaming fresh vitals..."
	@$(MAKE) --no-print-directory dev-simulate SAMPLES=48 >/dev/null 2>&1 || true
	@sleep 3
	@echo "Scoring recipient 1 (NEWS2, DASS-21, fuzzy risk):"
	@for kind in news2 dass21 risk; do \
	  printf "  %-7s -> HTTP " "$$kind"; \
	  kubectl -n $(NAMESPACE) exec deploy/web -- curl -s -m12 -o /dev/null -w '%{http_code}\n' -X POST "http://assessment:8000/assess/1/$$kind" 2>/dev/null; \
	done
	@echo "== assessment_results =="
	@kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -d app -c \
	  "SELECT score_type, value, risk_level FROM assessment_results WHERE care_recipient_id=1 AND computed_at > now() - interval '2 minutes' ORDER BY id;"
	@echo "== alerts (human-review inbox) =="
	@kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -d app -c \
	  "SELECT severity, title FROM alerts WHERE care_recipient_id=1 AND created_at > now() - interval '2 minutes' ORDER BY id;"

.PHONY: web-rebuild
web-rebuild: ## Rebuild the web app image from apps/web and roll the deployment (dev has no live code mount)
	eval $$(minikube docker-env) && docker build -t $(WEB_IMAGE) apps/web
	kubectl -n $(NAMESPACE) rollout restart deployment/web
	kubectl -n $(NAMESPACE) rollout status deployment/web --timeout=180s

.PHONY: media-rebuild
media-rebuild: ## Rebuild the media image (ffmpeg + faster-whisper + MiniLM) and roll api + worker
	eval $$(minikube docker-env) && docker build -t $(MEDIA_IMAGE) services/media
	kubectl -n $(NAMESPACE) rollout restart deployment/media deployment/media-worker
	kubectl -n $(NAMESPACE) rollout status deployment/media --timeout=300s
	kubectl -n $(NAMESPACE) rollout status deployment/media-worker --timeout=300s

.PHONY: dev-media
dev-media: ## Demo the media pipeline end-to-end: synthesize mock consultations, transcribe, index, hybrid-search (recipient 1)
	@echo "Seeding synthetic media (espeak-ng TTS consultations + imaging placeholders)..."
	@kubectl -n $(NAMESPACE) run media-sim-$$RANDOM --rm -i --restart=Never \
		--image=$(MEDIA_IMAGE) --image-pull-policy=IfNotPresent \
		-- simulate --recipient 1 --url http://media:8000
	@echo "Waiting for the worker to transcribe + index (faster-whisper, CPU)..."
	@for i in $$(seq 1 40); do \
	  N=$$(kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -d app -tAc \
	    "SELECT count(*) FROM media_assets WHERE care_recipient_id=1 AND status='indexed';" 2>/dev/null | tr -d ' '); \
	  echo "  indexed consultations: $${N:-0}"; [ "$${N:-0}" -ge 1 ] && break; sleep 6; done
	@echo "== media_assets (catalog) =="
	@kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -d app -c \
	  "SELECT kind, status, filename FROM media_assets WHERE care_recipient_id=1 ORDER BY created_at DESC LIMIT 10;"
	@echo "== hybrid search: 'shortness of breath' =="
	@kubectl -n $(NAMESPACE) exec deploy/web -- curl -s -m15 \
	  "http://media:8000/search?q=shortness+of+breath&care_recipient_id=1&limit=3"; echo

.PHONY: dev-media-auth
dev-media-auth: ## Turn ON media authorization: service verifies caller JWT + per-recipient OpenFGA (grants a caller assigned_staff on 1-4, flips AUTH_MODE=jwt) — needs dev-bootstrap
	@LOG="$$(kubectl -n $(NAMESPACE) logs job/zitadel-bootstrap 2>/dev/null)"; \
	SUB=$$(printf '%s' "$$LOG" | sed -n 's/.*"telemetry_user_id": "\([^"]*\)".*/\1/p'); \
	CID=$$(printf '%s' "$$LOG" | sed -n 's/.*"telemetry_client_id": "\([^"]*\)".*/\1/p'); \
	SEC=$$(printf '%s' "$$LOG" | sed -n 's/.*"telemetry_client_secret": "\([^"]*\)".*/\1/p'); \
	STORE=$$(kubectl -n $(NAMESPACE) exec deploy/web -- printenv OPENFGA_STORE_ID 2>/dev/null); \
	MODEL=$$(kubectl -n $(NAMESPACE) exec deploy/web -- printenv OPENFGA_MODEL_ID 2>/dev/null); \
	if [ -z "$$SUB" ] || [ -z "$$STORE" ]; then \
		echo "missing bootstrap SA/store — run 'make dev-bootstrap' first"; exit 1; fi; \
	echo "Granting the caller assigned_staff (=> viewer + editor) on recipients 1-4..."; \
	kubectl -n $(NAMESPACE) exec deploy/web -- php artisan fga:grant $$SUB assigned_staff 1 2 3 4; \
	echo "Flipping media to AUTH_MODE=jwt + injecting OpenFGA store/model..."; \
	kubectl -n $(NAMESPACE) set env deployment/media \
		AUTH_MODE=jwt OPENFGA_STORE_ID=$$STORE OPENFGA_MODEL_ID=$$MODEL >/dev/null; \
	kubectl -n $(NAMESPACE) rollout status deployment/media --timeout=180s; \
	TOKEN=$$(kubectl -n $(NAMESPACE) exec deploy/web -- curl -s -m10 -u "$$CID:$$SEC" \
		-d grant_type=client_credentials --data-urlencode "scope=openid" \
		"http://maagaparuga.test:9080/oauth/v2/token" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'); \
	printf "authorized (recipient 1, granted)   -> HTTP "; \
	kubectl -n $(NAMESPACE) exec deploy/web -- curl -s -o /dev/null -w '%{http_code}\n' -m12 \
		-H "Authorization: Bearer $$TOKEN" "http://apisix:9080/v1/media/search?q=breath&care_recipient_id=1"; \
	printf "denied     (recipient 5, no grant)  -> HTTP "; \
	kubectl -n $(NAMESPACE) exec deploy/web -- curl -s -o /dev/null -w '%{http_code}\n' -m12 \
		-H "Authorization: Bearer $$TOKEN" "http://apisix:9080/v1/media/search?q=breath&care_recipient_id=5"
	@echo "Media authz ON. Revert: kubectl -n $(NAMESPACE) set env deployment/media AUTH_MODE=disabled"

.PHONY: dev-dns
dev-dns: ## Make the cluster resolve maagaparuga.test -> the APISIX gateway (single-host OIDC issuer)
	@python3 -c "import json,subprocess as sp; \
	cf=sp.check_output(['kubectl','-n','kube-system','get','cm','coredns','-o','jsonpath={.data.Corefile}']).decode(); \
	cf=cf if 'maagaparuga.test' in cf else cf.replace('.:53 {\n', '.:53 {\n    rewrite name maagaparuga.test apisix.$(NAMESPACE).svc.cluster.local\n',1); \
	sp.run(['kubectl','-n','kube-system','patch','cm','coredns','--type','merge','-p',json.dumps({'data':{'Corefile':cf}})],check=True)"
	kubectl -n kube-system rollout restart deployment/coredns
	@echo "Add to /etc/hosts once:  127.0.0.1 maagaparuga.test"
	@echo "Then 'make dev-gateway' and open http://maagaparuga.test:9080"

.PHONY: dev-reinit-zitadel
dev-reinit-zitadel: ## Re-initialize ZITADEL (needed when the external domain changes; DEV ONLY, wipes its DB)
	kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -c "DROP DATABASE IF EXISTS zitadel WITH (FORCE);"
	kubectl -n $(NAMESPACE) exec maagaparuga-pg-1 -c postgres -- psql -U postgres -c "CREATE DATABASE zitadel OWNER zitadel;"
	-kubectl -n $(NAMESPACE) delete job zitadel-bootstrap --ignore-not-found
	kubectl apply -k $(DEV_OVERLAY)
	kubectl -n $(NAMESPACE) delete pod -l app.kubernetes.io/name=zitadel --ignore-not-found

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

.PHONY: gateway-proto
gateway-proto: ## Regenerate the gateway's compiled descriptor set from proto/
	@cd proto && $(BUF) build -o /tmp/maagaparuga-descriptors.pb
	@python3 -c "import base64,pathlib,re; \
	b64=base64.b64encode(pathlib.Path('/tmp/maagaparuga-descriptors.pb').read_bytes()).decode(); \
	p=pathlib.Path('deploy/k8s/base/apisix/apisix.yaml'); s=p.read_text(); \
	s=re.sub(r'(?<=        content: \")[A-Za-z0-9+/=]+(?=\")', b64, s); \
	p.write_text(s); print('gateway descriptor set updated')"

.PHONY: proto-check
proto-check: ## Fail if the gateway's descriptor set is stale relative to proto/
	@cd proto && $(BUF) build -o /tmp/maagaparuga-check.pb
	@python3 -c "import base64,pathlib,re,sys; \
	want=base64.b64encode(pathlib.Path('/tmp/maagaparuga-check.pb').read_bytes()).decode(); \
	s=pathlib.Path('deploy/k8s/base/apisix/apisix.yaml').read_text(); \
	m=re.search(r'(?<=        content: \")[A-Za-z0-9+/=]+(?=\")', s); \
	sys.exit(0) if m and m.group(0)==want else (print('gateway descriptor set is stale -- run: make gateway-proto'), sys.exit(1))"
	@echo "gateway descriptor set in sync"

.PHONY: kustomize-check
kustomize-check: ## Render all overlays to verify they build
	kubectl kustomize $(DEV_OVERLAY) > /dev/null && echo "dev overlay: OK"
