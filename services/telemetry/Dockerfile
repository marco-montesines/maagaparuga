# syntax=docker/dockerfile:1
# Telemetry service — one binary, three roles (serve | write | simulate).
# Build from the repository root so the generated protobuf package is in scope:
#   docker build -f services/telemetry/Dockerfile -t maagaparuga-telemetry .

FROM golang:1.26-alpine AS build
WORKDIR /src
COPY services/telemetry/go.mod services/telemetry/go.sum ./
RUN go mod download
COPY services/telemetry/ ./
RUN CGO_ENABLED=0 go build -ldflags="-w -s" -o /out/telemetry ./cmd/telemetry

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/telemetry /telemetry
USER nonroot:nonroot
EXPOSE 9090
ENTRYPOINT ["/telemetry"]
CMD ["serve"]
