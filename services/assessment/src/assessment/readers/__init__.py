"""VitalsReader adapters. Both are selectable via config (VITALS_READER):
``clickhouse`` (direct read-only query) and ``grpc`` (telemetry GetWindow).
Concrete adapters import their heavy drivers lazily so the rest of the service
loads without them."""
