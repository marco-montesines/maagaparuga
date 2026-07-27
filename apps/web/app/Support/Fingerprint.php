<?php

namespace App\Support;

/**
 * Content fingerprints — used as OpenSearch document ids so re-indexing the
 * same transcription is idempotent.
 *
 * When the FrankenPHP build includes the Go-native extension (see
 * apps/web/frankenphp/), `maagap_fingerprint` is implemented in Go — the
 * PHP-functions-in-Go showcase bridge. Stock PHP falls back to xxh128.
 */
class Fingerprint
{
    public static function make(string $content): string
    {
        if (function_exists('maagap_fingerprint')) {
            return maagap_fingerprint($content);
        }

        return hash('xxh128', $content);
    }
}
