# Contributing

Thanks for your interest in MaagapAruga. This is an open-source **research and
educational** care-platform framework (Apache-2.0). Contributions of code, docs,
and issue reports are welcome.

## Ground rules

- **Mock data only.** Never contribute or reference real personal or health data.
  All data is fictitious/synthetic — see [`data/mock/README.md`](data/mock/README.md).
- **No secrets.** Do not commit credentials, tokens, or `.env` files. Secret
  scanning runs in CI.
- **Not a medical device.** Keep wording accurate — this is a research/educational
  framework (see [DISCLAIMER.md](DISCLAIMER.md)), not a certified product.

## Getting set up

The platform runs on Kubernetes; local development uses minikube. See the
documentation to get going:

- [Installation](docs/getting-started/installation.md) — `make dev` and friends
- [Configuration](docs/getting-started/configuration.md)
- [Architecture overview](docs/architecture/overview.md) and the
  [decision records](docs/adr/README.md)

## Development workflow

1. Create a branch off `master`.
2. Make your change, with tests where it makes sense.
3. Run the same checks CI runs, for the language you touched:
   - **PHP** (`apps/web`): `./vendor/bin/pint --test`, `./vendor/bin/phpstan analyse`, `./vendor/bin/pest`
   - **Go** (`services/telemetry`): `golangci-lint run`, `go test ./...`
   - **Python** (`services/*`): `ruff check .`, `mypy src`, `pytest`
   - **Proto**: `buf lint`
   - **IaC**: `tofu fmt -check -recursive infra`, `ansible-lint` (in `infra/ansible`)
4. Open a pull request and fill in the template. CI (lint, type-check, tests,
   and security scans) must be green, and the change needs a review before merge.

## Commit messages

Use clear, conventional-style messages (`feat:`, `fix:`, `docs:`, `chore:`, …).
Keep each PR focused on one change.

## License

By contributing you agree that your contributions are licensed under the
project's [Apache-2.0 License](LICENSE).
