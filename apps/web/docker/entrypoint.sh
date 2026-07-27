#!/bin/sh
set -e

# Queue worker role: same image, app-internal task queue (Redis) —
# transcription indexing, notifications. Plain CLI loop, no worker-mode
# concerns apply here.
if [ "$1" = "queue" ]; then
    exec php artisan queue:work --tries=5 --max-time=3600
fi

case "${SERVER_MODE:-octane}" in
    octane)
        # Worker mode with the worker-mode discipline: bounded worker
        # lifetime (recycled every OCTANE_MAX_REQUESTS requests).
        # Custom Caddyfile: the stock Octane stub enables the brotli
        # encoder, which the FrankenPHP Docker build doesn't bundle.
        exec php artisan octane:start \
            --server=frankenphp \
            --host=0.0.0.0 \
            --port=8080 \
            --caddyfile=/app/docker/Caddyfile \
            --max-requests="${OCTANE_MAX_REQUESTS:-500}"
        ;;
    classic)
        # Per-request lifecycle — zero worker-state concerns. The Go
        # extension (when compiled in) works identically in this mode.
        exec frankenphp php-server --listen :8080 --root public/
        ;;
    *)
        echo "unknown SERVER_MODE '${SERVER_MODE}' (octane|classic)" >&2
        exit 1
        ;;
esac
