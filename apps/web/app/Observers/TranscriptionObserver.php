<?php

namespace App\Observers;

use App\Jobs\IndexTranscription;
use App\Models\Transcription;

class TranscriptionObserver
{
    public function created(Transcription $transcription): void
    {
        IndexTranscription::dispatch($transcription->id);
    }

    public function updated(Transcription $transcription): void
    {
        if ($transcription->wasChanged('body')) {
            IndexTranscription::dispatch($transcription->id);
        }
    }
}
