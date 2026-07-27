<?php

namespace App\Services\MediaSearch;

class FakeMediaSearcher implements MediaSearcher
{
    public function search(int $careRecipientId, string $query, int $limit = 10): array
    {
        return [
            [
                'mediaId' => 'demo-consult-001',
                'objectKey' => 'media/demo/teleconsultation-001.mp4',
                'startMs' => 30_000,
                'endMs' => 47_000,
                'snippet' => '[synthetic] …discussed adjusting the evening medication schedule…',
                'score' => 0.92,
            ],
        ];
    }
}
