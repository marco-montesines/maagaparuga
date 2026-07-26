# Web application GraphQL BFF

The web application exposes a single **GraphQL** endpoint (Laravel Lighthouse)
that aggregates across the polyglot backends: one dashboard query returns the
care record (PostgreSQL), the latest vitals window (telemetry gRPC), assessment
results, and media search hits (OpenSearch hybrid). This is a **backend-for-
frontend**, not a general-purpose public API — it exists to serve the web app's
own dashboard in one round trip ([ADR 0010](../adr/0010-three-api-styles.md)).

The schema is `apps/web/graphql/schema.graphql`.

> Research/educational framework — **not a medical device**. All entities carry
> mock data only.

## Endpoint & authentication

- **Endpoint:** `POST /graphql`, served by the web application.
- **Authentication:** every root field is protected by Lighthouse's `@guard`
  directive, so requests run in an **authenticated web session**. Login is
  ZITADEL OIDC (consumed by the app via Socialite); the browser obtains a
  session by logging in, and the GraphQL calls ride that session. `me` also
  carries `@auth`. Beyond authentication, `careRecipient` is additionally gated
  by a `@can(ability: "view")` policy check, so a signed-in user only resolves
  recipients they are permitted to view.

Because this is the app's own BFF, integration clients should prefer the REST
and gRPC surfaces ([rest-apis.md](rest-apis.md), [telemetry-grpc.md](telemetry-grpc.md)).

## Queries

```graphql
type Query {
  me: User
  careRecipient(id: ID!): CareRecipient
  dashboard(careRecipientId: ID!): Dashboard
  mediaSearch(careRecipientId: ID!, query: String!): [MediaHit!]!
}
```

| Query | Args | Returns | Notes |
|---|---|---|---|
| `me` | — | `User` | the authenticated user |
| `careRecipient` | `id: ID!` | `CareRecipient` | policy-checked (`view`) |
| `dashboard` | `careRecipientId: ID!` | `Dashboard` | the BFF aggregate — record + vitals + scores + alerts in one trip |
| `mediaSearch` | `careRecipientId: ID!`, `query: String!` | `[MediaHit!]!` | hybrid (keyword + semantic) search over transcribed media |

There are **no mutations** defined in the schema — it is a read/aggregation
surface.

## Types

### `Dashboard` (the aggregate)

```graphql
type Dashboard {
  recipient: CareRecipient!
  vitalsWindow: [VitalsSample!]!
  latestAssessments: [AssessmentResult!]!
  openAlerts: [Alert!]!
}
```

### `User`

```graphql
type User { id: ID!  name: String!  email: String  role: String! }
```

### `CareRecipient`

```graphql
type CareRecipient {
  id: ID!
  name: String!
  birthdate: DateTime
  careContext: String!
  medicalInfo: GeneralMedicalInfo
  consultations: [Consultation!]!
  questionnaireResponses: [QuestionnaireResponse!]!
}
```

Related types: `GeneralMedicalInfo` (`bloodType`, `heightCm`, `weightKg`,
`allergies`, `familyHistory`, `lastVisitAt`), `Consultation` (`consultedAt`,
`staff`, `chiefComplaint`, `diagnosis`, `treatment`, `prescription`,
`attachments`, `transcriptions`), `ConsultationAttachment` (`kind`, `objectKey`,
`caption`), `Transcription` (`body`, `author`), `QuestionnaireResponse`
(`instrument`, `submittedAt`).

### `VitalsSample` (from the telemetry read API)

```graphql
type VitalsSample {
  measuredAt: DateTime!
  heartRateBpm: Int
  spo2Percent: Float
  bpSystolic: Int
  bpDiastolic: Int
  temperatureC: Float
  respiratoryRate: Int
}
```

### `AssessmentResult`

```graphql
type AssessmentResult {
  id: ID!
  scoreType: String!
  value: Float
  riskLevel: String
  computedAt: DateTime!
}
```

### `Alert`

```graphql
type Alert {
  id: ID!
  severity: String!
  title: String!
  body: String
  acknowledgedAt: DateTime
  createdAt: DateTime!
}
```

### `MediaHit` (a search hit, links back to the exact media timestamp)

```graphql
type MediaHit {
  mediaId: String!
  objectKey: String!
  startMs: Int!
  endMs: Int!
  snippet: String!
  score: Float!
}
```

## Example operations

Dashboard for a mock care recipient (id `1`):

```graphql
query Dashboard {
  dashboard(careRecipientId: "1") {
    recipient { id name careContext }
    vitalsWindow { measuredAt heartRateBpm spo2Percent }
    latestAssessments { scoreType value riskLevel computedAt }
    openAlerts { severity title createdAt }
  }
}
```

Hybrid media search:

```graphql
query Search {
  mediaSearch(careRecipientId: "1", query: "shortness of breath") {
    mediaId objectKey startMs endMs snippet score
  }
}
```

Sent over HTTP (within an authenticated session):

```bash
curl -X POST https://<gateway-host>/graphql \
  -H "Content-Type: application/json" \
  --cookie "$SESSION_COOKIE" \
  -d '{"query": "{ dashboard(careRecipientId: \"1\") { recipient { name } openAlerts { title } } }"}'
```
