# Integration guide

How to talk to the MaagapAruga platform from outside — for developers integrating
IoMT devices, building clients, or wiring another system to the APIs.

> **MaagapAruga is a research and educational software framework — not a medical
> device.** It ships only fictitious mock data and must not be used with real
> personal or health data. Vitals, scores, and risk levels shown in these
> examples are **illustrative**. See [`DISCLAIMER.md`](https://github.com/marco-montesines/maagaparuga/blob/master/DISCLAIMER.md).

## The three API styles

The platform speaks three API styles, each placed where it earns its keep
([ADR 0010](../adr/0010-three-api-styles.md)):

| Style | Surface | Who uses it | Reference |
|---|---|---|---|
| **gRPC** (+ REST transcode) | Telemetry — vitals ingest + windowed read | IoMT devices / fleets | [telemetry-grpc.md](telemetry-grpc.md), [iomt-devices.md](iomt-devices.md) |
| **REST/JSON** | Media (upload + hybrid search), Assessment (scoring) | Integration & service clients | [rest-apis.md](rest-apis.md) |
| **GraphQL** (BFF) | The web app dashboard aggregate | The web application | [graphql-bff.md](graphql-bff.md) |

- **gRPC-first telemetry.** The Go telemetry service defines its contract in
  protobuf (`proto/maagaparuga/telemetry/v1/vitals.proto`). Devices stream
  vitals over native gRPC. The **same service** is exposed as REST through the
  gateway's `grpc-transcode` plugin — one implementation, two surfaces.
- **REST for media & assessment.** Plain HTTP/JSON FastAPI services, reached
  through the gateway.
- **GraphQL only as a BFF.** A single `/graphql` endpoint in the web app
  aggregates the care record, latest vitals, scores, and media hits into one
  dashboard query. It is not a general-purpose public API.

## The gateway is the single entry point

All external traffic goes through **Apache APISIX** ([ADR 0003](../adr/0003-apisix-api-gateway.md)).
Clients do **not** address services directly. The gateway:

- routes versioned paths to the right service;
- proxies native gRPC and **transcodes** the telemetry service to REST at
  `/v1/vitals*`;
- rewrites the media paths (`/v1/media*`) to the media service's own paths;
- enforces **edge authentication** on the REST API routes (bearer token
  verified against ZITADEL's JWKS).

Public gateway paths at a glance:

| Path | Method(s) | Goes to |
|---|---|---|
| `/v1/vitals` | `POST` | telemetry `PublishVitals` (REST transcode) |
| `/v1/vitals/window` | `GET`, `POST` | telemetry `GetWindow` (REST transcode) |
| `/maagaparuga.telemetry.v1.VitalsService/*` | gRPC | telemetry (native gRPC, incl. streaming) |
| `/v1/media`, `/v1/media/{asset_id}` | `POST`, `GET` | media service (`/media*`) |
| `/v1/media/search` | `GET` | media search (`/search`) |
| `/graphql` | `POST` | web application BFF |

> The exact host depends on the deployment. In local dev the gateway is reached
> on the machine's minikube address; in a cloud deployment it is the configured
> domain. Examples below use `https://<gateway-host>` as a placeholder.

## The shared auth model

One authentication story spans every language and service
([ADR 0009](../adr/0009-zitadel-openfga-identity-authorization.md)):

1. **Authentication — who are you? (ZITADEL, OIDC).** Callers present a
   **ZITADEL-issued JWT** as an `Authorization: Bearer <token>` credential.
   Services verify the signature locally against ZITADEL's JWKS and check the
   issuer, audience, and expiry — no per-request round trip to the IdP. Devices
   authenticate exactly like any other client; they just obtain the token
   through a machine-to-machine flow (see [iomt-devices.md](iomt-devices.md)).

2. **Authorization — may you touch *this* care recipient? (OpenFGA).** A valid
   token is not enough. The services ask **OpenFGA** whether the caller holds
   the required relationship on the specific care recipient. The relations:

   | Relation | Grants | Used by |
   |---|---|---|
   | `viewer` | read a care recipient's data | vitals window read, media read/search |
   | `editor` | write clinical content | media upload |
   | `vitals_writer` | stream/publish vitals (assigned staff **or** a device) | vitals ingest |

   Any non-allow outcome — including a transport or config error — is a
   **denial**. The authorization layer never fails open.

### Dev vs. enforced auth

Each service has a switch so it can run without identity wiring for local demos,
and enforce fully otherwise:

| Service | Env | Dev default | Enforced |
|---|---|---|---|
| telemetry | `AUTH_MODE` | `disabled` (main.go defaults to `jwt`; local `make` targets pass `disabled`) | `jwt` |
| media | `AUTH_MODE` | `disabled` | `jwt` |
| assessment | — | endpoints carry no caller auth today (see [rest-apis.md](rest-apis.md)) | — |

When auth is disabled, the service logs a loud warning at startup and allows
every request. Cloud deployments run with `jwt`.

## Files in this guide

- **[iomt-devices.md](iomt-devices.md)** — the end-to-end walkthrough for
  integrating an IoMT device: obtain a token, get authorized, send vitals over
  gRPC and REST.
- **[telemetry-grpc.md](telemetry-grpc.md)** — `VitalsService` reference: RPCs,
  messages, fields, streaming semantics, REST equivalents.
- **[rest-apis.md](rest-apis.md)** — media + assessment REST reference.
- **[graphql-bff.md](graphql-bff.md)** — the GraphQL schema reference.
