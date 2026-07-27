<?php

/**
 * IDE / documentation stubs for the maagap FrankenPHP extension.
 * The real implementation lives in extension.go (compiled into FrankenPHP).
 * Stock PHP builds fall back to hash('xxh128', ...) — see
 * App\Support\Fingerprint.
 *
 * @generate-class-entries
 */

/**
 * 128-bit content fingerprint (xxHash3-128, lowercase hex) — used as
 * idempotent document ids for search indexing.
 */
function maagap_fingerprint(string $data): string {}
