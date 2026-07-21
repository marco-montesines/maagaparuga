<?php

namespace App\Services\OpenFga;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Thin client over OpenFGA's documented HTTP API: check + tuple writes are
 * the only operations the web app needs. Fine-grained questions ("may THIS
 * user see THIS care recipient?") are always answered here, never by role
 * checks alone (ADR 0009).
 *
 * Fail-closed by design: transport errors deny access and log loudly.
 */
class OpenFgaClient
{
    public function __construct(
        private readonly string $url,
        private readonly ?string $storeId,
        private readonly ?string $modelId,
        private readonly float $timeout,
    ) {}

    public static function fromConfig(): self
    {
        // Empty env values must mean "unconfigured", not "store named ''".
        $storeId = config('openfga.store_id');
        $modelId = config('openfga.model_id');

        return new self(
            url: rtrim((string) config('openfga.url'), '/'),
            storeId: $storeId === '' ? null : $storeId,
            modelId: $modelId === '' ? null : $modelId,
            timeout: (float) config('openfga.timeout_seconds'),
        );
    }

    public function check(string $user, string $relation, string $object): bool
    {
        if ($this->storeId === null) {
            Log::warning('openfga: no store configured, denying', compact('user', 'relation', 'object'));

            return false;
        }

        try {
            $response = Http::timeout($this->timeout)
                ->post("{$this->url}/stores/{$this->storeId}/check", array_filter([
                    'tuple_key' => compact('user', 'relation', 'object'),
                    'authorization_model_id' => $this->modelId,
                ]));

            return $response->successful() && $response->json('allowed') === true;
        } catch (\Throwable $e) {
            Log::error('openfga: check failed, denying', ['error' => $e->getMessage()]);

            return false;
        }
    }

    /** @param array<int, array{user: string, relation: string, object: string}> $tuples */
    public function writeTuples(array $tuples): void
    {
        $this->mutateTuples(writes: $tuples, deletes: []);
    }

    /** @param array<int, array{user: string, relation: string, object: string}> $tuples */
    public function deleteTuples(array $tuples): void
    {
        $this->mutateTuples(writes: [], deletes: $tuples);
    }

    private function mutateTuples(array $writes, array $deletes): void
    {
        if ($this->storeId === null) {
            Log::warning('openfga: no store configured, tuple mutation skipped');

            return;
        }

        $payload = array_filter([
            'writes' => $writes === [] ? null : ['tuple_keys' => $writes],
            'deletes' => $deletes === [] ? null : ['tuple_keys' => $deletes],
            'authorization_model_id' => $this->modelId,
        ]);

        try {
            Http::timeout($this->timeout)
                ->post("{$this->url}/stores/{$this->storeId}/write", $payload)
                ->throw();
        } catch (\Throwable $e) {
            // Enforcement stays fail-closed on check(); a lost tuple write only
            // (over-)restricts. `php artisan fga:sync` re-derives all tuples
            // from care_team_assignments to heal any drift.
            Log::error('openfga: tuple write failed', ['error' => $e->getMessage()]);
        }
    }
}
