<?php

namespace App\GraphQL\Queries;

use App\Models\CareRecipient;
use App\Services\MediaSearch\MediaSearcher;
use Illuminate\Support\Facades\Gate;

class MediaSearchQuery
{
    public function __construct(private readonly MediaSearcher $searcher) {}

    /** @param array{careRecipientId: int|string, query: string} $args */
    public function __invoke(mixed $root, array $args): array
    {
        $recipient = CareRecipient::findOrFail($args['careRecipientId']);

        Gate::authorize('view', $recipient);

        return $this->searcher->search($recipient->id, $args['query']);
    }
}
