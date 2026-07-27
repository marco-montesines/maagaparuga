<?php

namespace App\Jobs;

use App\Models\Transcription;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * App-internal task (Laravel queue on Redis — see the queue-vs-broker rule):
 * pushes a transcription into OpenSearch for full-text search over care notes.
 *
 * The OpenSearch document id is the transcription's own id, so re-indexing an
 * edited note REPLACES it (no stale ghost of retracted clinical text lingering
 * in search), and two notes with identical text never collide onto one
 * document.
 */
class IndexTranscription implements ShouldQueue
{
    use Queueable;

    public int $tries = 5;

    /** Back off between retries; a transient OpenSearch blip shouldn't hammer it. */
    public array $backoff = [10, 30, 120];

    public function __construct(public readonly int $transcriptionId) {}

    public function handle(): void
    {
        $transcription = Transcription::with('consultation')->find($this->transcriptionId);

        if ($transcription === null || $transcription->consultation === null) {
            // The row (or its parent) was deleted before indexing ran — nothing
            // to index, and retrying will not change that.
            return;
        }

        $url = rtrim((string) config('services.opensearch.url'), '/');

        $response = Http::timeout(5)
            ->put("{$url}/transcriptions/_doc/{$transcription->id}", [
                'transcription_id' => $transcription->id,
                'consultation_id' => $transcription->consultation_id,
                'care_recipient_id' => $transcription->consultation->care_recipient_id,
                'author_user_id' => $transcription->author_user_id,
                'body' => $transcription->body,
                'created_at' => $transcription->created_at?->toIso8601String(),
            ]);

        // A 4xx is a request/mapping problem that retrying cannot fix — fail
        // the job now (loudly) instead of burning all retries in silence.
        if ($response->clientError()) {
            $this->fail(new \RuntimeException(
                "OpenSearch rejected transcription {$transcription->id}: HTTP {$response->status()}",
            ));

            return;
        }

        $response->throw(); // 5xx -> exception -> retry with backoff

        $transcription->forceFill(['indexed_at' => now()])->saveQuietly();
    }

    public function failed(Throwable $e): void
    {
        Log::error('transcription indexing failed', [
            'transcription_id' => $this->transcriptionId,
            'error' => $e->getMessage(),
        ]);
    }
}
