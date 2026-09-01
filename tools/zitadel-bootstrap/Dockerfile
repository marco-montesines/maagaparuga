# syntax=docker/dockerfile:1
# One-time install configurator for ZITADEL. Run as a Kubernetes Job that
# mounts the same machine-key PVC ZITADEL writes on first-instance init.
# Build from this directory:
#   docker build -t maagaparuga-zitadel-bootstrap .

FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-w -s" -o /out/bootstrap .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/bootstrap /bootstrap
USER nonroot:nonroot
ENTRYPOINT ["/bootstrap"]
