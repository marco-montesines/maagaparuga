<?php

namespace App\Jobs;

use App\Models\Transcription;
use App\Support\Fingerprint;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;

/**
 * App-internal task (Laravel queue on Redis — see the queue-vs-broker rule):
 * pushes a transcription into OpenSearch for full-text search over care
 * notes. Doc id = content fingerprint -> idempotent re-index.
 */
class IndexTranscription implements ShouldQueue
{
    use Queueable;

    public int $tries = 5;

    public function __construct(public readonly int $transcriptionId) {}

    public function handle(): void
    {
        $transcription = Transcription::with('consultation')->find($this->transcriptionId);

        if ($transcription === null) {
            return;
        }

        $url = rtrim((string) config('services.opensearch.url'), '/');
        $docId = Fingerprint::make($transcription->body);

        Http::timeout(5)
            ->put("{$url}/transcriptions/_doc/{$docId}", [
                'transcription_id' => $transcription->id,
                'consultation_id' => $transcription->consultation_id,
                'care_recipient_id' => $transcription->consultation->care_recipient_id,
                'author_user_id' => $transcription->author_user_id,
                'body' => $transcription->body,
                'created_at' => $transcription->created_at?->toIso8601String(),
            ])
            ->throw();

        $transcription->forceFill(['indexed_at' => now()])->saveQuietly();
    }
}
