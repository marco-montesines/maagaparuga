<?php

// Thin OpenFGA HTTP-API client configuration (ADR 0009).
// NOTE: the official Laravel SDK (evansims/openfga-laravel) requires
// illuminate ^12 as of v1.0.0 — swap this thin client for it once it
// supports the current Laravel major.
return [
    'url' => env('OPENFGA_URL', 'http://openfga:8080'),
    'store_id' => env('OPENFGA_STORE_ID'),
    'model_id' => env('OPENFGA_MODEL_ID'),

    // Fail-closed: when OpenFGA is unreachable, permission checks DENY.
    'timeout_seconds' => (float) env('OPENFGA_TIMEOUT', 2.0),
];
