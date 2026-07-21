# apps/web — Web application (Laravel + Octane on FrankenPHP)

The product surface of MaagapAruga: care-recipient records, consultations with
imaging/media attachments, transcriptions, questionnaires, and the alerts
inbox — plus the **GraphQL BFF** (`POST /graphql`) that aggregates the care
record, live vitals, assessment results, and media search hits into single
dashboard queries (ADR 0010).

## Architecture notes

- **Identity**: ZITADEL OIDC (Authorization Code + PKCE) via Socialite —
  there is **no local password store** (ADR 0009). Coarse roles come from the
  ZITADEL project-roles claim.
- **Fine-grained authorization**: OpenFGA relationship checks (fail-closed)
  through a thin HTTP client (`app/Services/OpenFga/`) — the Laravel SDK
  bridge requires an older framework major; the official `evansims/openfga-php`
  SDK powers `php artisan fga:bootstrap` (store + model from `fga/model.fga`).
  `php artisan fga:sync` re-derives all tuples from the database.
- **Task queue**: app-internal async work (transcription indexing into
  OpenSearch, notifications) runs on Laravel queues over Redis — anything
  crossing a service boundary uses NATS instead (see the repository README).
- **Server modes** (`docker/entrypoint.sh`): `SERVER_MODE=octane` (default;
  FrankenPHP worker mode, workers recycled every 500 requests) or
  `SERVER_MODE=classic` (per-request lifecycle, zero worker-state concerns).
- **PHP-functions-in-Go**: `frankenphp-ext/` implements `maagap_fingerprint()`
  natively in Go (built with `docker build --target with-extension`); stock
  builds fall back to `hash('xxh128')` with identical output.

## Local development

```bash
composer install
php artisan test           # Pest, in-memory SQLite
./vendor/bin/pint          # formatting
./vendor/bin/phpstan       # static analysis (larastan)

# Against the minikube stack (make dev + port-forwards):
php artisan migrate:fresh --seed
php artisan fga:bootstrap  # once; then set OPENFGA_STORE_ID/MODEL_ID in .env
php artisan fga:sync
```

All seed data is **fictitious** (see `data/mock/README.md`).
