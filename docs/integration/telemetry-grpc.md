# Telemetry — `VitalsService` reference

The telemetry service ingests raw biotelemetry (vitals) from IoMT devices and
serves windowed reads back to the platform. Its contract is protobuf-first
(`proto/maagaparuga/telemetry/v1/vitals.proto`); the gateway exposes the same
service as REST via `grpc-transcode` ([ADR 0010](../adr/0010-three-api-styles.md)).

For the device-integration walkthrough (tokens, authorization, worked examples),
see [iomt-devices.md](iomt-devices.md). This page is the API reference.

> Research/educational framework — **not a medical device**. All values are
> illustrative and all data is mock.

## Design rule: raw measurements only

Devices send **raw measurements**, never clinical scores. Every early-warning or
risk score is computed server-side by the assessment service from these samples,
so it can always be recomputed and audited. The vitals contract deliberately
carries no `news2_score`, `risk_level`, or similar field.

## Messages

### `VitalsSample`

One point-in-time measurement set from one device. Every measurement is
optional — real devices are single-purpose (a pulse oximeter has no
thermometer), so a sample carries only what that device measured. Optional
scalars distinguish "not measured" from "measured zero".

| Field | # | Type | Notes |
|---|---|---|---|
| `device_id` | 1 | `string` | required |
| `care_recipient_id` | 2 | `string` | required |
| `measured_at` | 3 | `google.protobuf.Timestamp` | required |
| `heart_rate_bpm` | 10 | `optional uint32` | |
| `respiratory_rate` | 11 | `optional uint32` | breaths per minute |
| `spo2_percent` | 12 | `optional double` | blood oxygen saturation |
| `body_temp_c` | 13 | `optional double` | |
| `bp_systolic` | 14 | `optional uint32` | mmHg |
| `bp_diastolic` | 15 | `optional uint32` | mmHg |
| `consciousness` | 16 | `Consciousness` | AVPU scale (enum below) |
| `skin_resistance_ohms` | 20 | `optional double` | galvanic skin response |
| `skin_ph` | 21 | `optional double` | |

### `Consciousness` (AVPU)

A NEWS2 input and the one categorical vitals field.

| Value | # |
|---|---|
| `CONSCIOUSNESS_UNSPECIFIED` | 0 |
| `CONSCIOUSNESS_ALERT` | 1 |
| `CONSCIOUSNESS_VOICE` | 2 |
| `CONSCIOUSNESS_PAIN` | 3 |
| `CONSCIOUSNESS_UNRESPONSIVE` | 4 |

### Validation

A sample is rejected unless it has `device_id`, `care_recipient_id`,
`measured_at`, and **at least one** measurement (a non-`UNSPECIFIED`
`consciousness` counts). Present numeric fields must be finite and within
plausible ranges; the blood-pressure pair must be ordered
(`bp_diastolic < bp_systolic`). Timestamps may be at most ~5 minutes in the
future (clock skew) and at most 24 hours old.

| Field | Plausible range |
|---|---|
| `heart_rate_bpm` | 20 – 300 |
| `respiratory_rate` | 3 – 80 |
| `spo2_percent` | 50.0 – 100.0 |
| `body_temp_c` | 20.0 – 45.0 |
| `bp_systolic` | 40 – 300 |
| `bp_diastolic` | 20 – 200 |
| `skin_resistance_ohms` | 1.0 – 10,000,000.0 |
| `skin_ph` | 3.0 – 9.0 |

On the streaming path an invalid sample is **counted and dropped**, not fatal —
one bad reading from a flaky sensor must not disconnect a whole device. On the
unary path an invalid sample returns `InvalidArgument`.

## RPCs

```protobuf
service VitalsService {
  rpc StreamVitals(stream StreamVitalsRequest) returns (StreamVitalsResponse);
  rpc PublishVitals(PublishVitalsRequest) returns (PublishVitalsResponse);
  rpc GetWindow(GetWindowRequest) returns (GetWindowResponse);
}
```

Every RPC requires an authenticated caller (bearer JWT) unless the service runs
with `AUTH_MODE=disabled`. Authorization is per care recipient (see below). The
gRPC health service is the only unauthenticated method (for Kubernetes probes).

### `StreamVitals` — client-streaming ingest

The device holds one connection and pushes `StreamVitalsRequest` messages
continuously; the server replies once at end-of-stream.

- **Request (streamed):** `StreamVitalsRequest { VitalsSample sample = 1; }`
- **Response (once):** `StreamVitalsResponse { uint64 accepted = 1; uint64 rejected = 2; }`

The server validates each sample and **publishes accepted ones to the message
broker** (NATS JetStream) — it never writes the database on this path. Invalid
samples increment `rejected` and are dropped. Authorization is checked the first
time each distinct `care_recipient_id` appears in the stream and cached for the
rest of the stream; an authorization failure is **terminal** for the stream.

Requires `vitals_writer` on each care recipient written.

### `PublishVitals` — unary single-sample ingest

The one-sample shape, and what REST clients reach through the gateway's
transcoding.

- **Request:** `PublishVitalsRequest { VitalsSample sample = 1; }`
- **Response:** `PublishVitalsResponse { uint64 accepted = 1; uint64 rejected = 2; }`
  (`accepted = 1` on success)

Invalid sample → `InvalidArgument`. Requires `vitals_writer` on the sample's
care recipient.

### `GetWindow` — windowed read

Returns the samples for a care recipient within a time window. Used by the web
BFF and the assessment service.

- **Request:** `GetWindowRequest { string care_recipient_id = 1; google.protobuf.Timestamp from = 2; google.protobuf.Timestamp to = 3; uint32 limit = 4; }`
  - `care_recipient_id` is required.
  - `to` defaults to now; `from` defaults to one hour before `to`. `from` must
    be before `to`.
  - `limit = 0` means the server default.
- **Response:** `GetWindowResponse { repeated VitalsSample samples = 1; }`

Requires `viewer` on the care recipient.

## Native gRPC examples

The gateway proxies native gRPC (including server reflection) at
`/maagaparuga.telemetry.v1.VitalsService/*`. Streaming ingest stays gRPC
end-to-end and cannot be transcoded.

Unary publish with `grpcurl` (mock data; care recipient `1`):

```bash
grpcurl \
  -H "authorization: Bearer $TOKEN" \
  -d '{
        "sample": {
          "device_id": "mock-oximeter-01",
          "care_recipient_id": "1",
          "measured_at": "2026-07-25T12:00:00Z",
          "heart_rate_bpm": 72,
          "spo2_percent": 97.4
        }
      }' \
  <gateway-host>:443 maagaparuga.telemetry.v1.VitalsService/PublishVitals
```

Windowed read:

```bash
grpcurl \
  -H "authorization: Bearer $TOKEN" \
  -d '{"care_recipient_id": "1", "limit": 50}' \
  <gateway-host>:443 maagaparuga.telemetry.v1.VitalsService/GetWindow
```

For a streaming client, generate stubs from the proto and send
`StreamVitalsRequest` messages; the in-repo simulator
(`services/telemetry/internal/simulator`, driven by the `simulate` command) is a
worked reference.

## REST-transcoded equivalents

The gateway maps two REST routes onto the service:

| REST route | Method | RPC |
|---|---|---|
| `/v1/vitals` | `POST` | `PublishVitals` |
| `/v1/vitals/window` | `GET`, `POST` | `GetWindow` |

Both routes are edge-authenticated: an anonymous or invalid bearer gets `401`;
a valid bearer passes through and the telemetry service re-checks it (defence in
depth). The REST body is the RPC's request message as JSON.

**Two transcoding quirks** (from APISIX's `grpc-transcode` / lua-protobuf
mapping — harmless but worth knowing):

- `google.protobuf.Timestamp` is `{"seconds": N, "nanos": N}` in **both**
  directions, not an RFC3339 string.
- proto3 `optional` fields compile to a synthetic oneof, so responses carry an
  extra `"_field": "field"` presence marker.

Publish a sample over REST:

```bash
curl -X POST https://<gateway-host>/v1/vitals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "sample": {
          "device_id": "mock-oximeter-01",
          "care_recipient_id": "1",
          "measured_at": {"seconds": 1785326400, "nanos": 0},
          "heart_rate_bpm": 72,
          "spo2_percent": 97.4
        }
      }'
```

Read a window over REST:

```bash
curl -X POST https://<gateway-host>/v1/vitals/window \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"care_recipient_id": "1", "limit": 50}'
```

See [iomt-devices.md](iomt-devices.md) for how to obtain `$TOKEN` and get a
device authorized as a `vitals_writer`.
