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
        // Authorize before revealing existence: findOrFail first would let an
        // unauthorized caller tell "exists" (403) from "does not exist" (404)
        // and enumerate care recipients. find() + a single authorize collapses
        // both to the same 403.
        $recipient = CareRecipient::find($args['careRecipientId']);

        Gate::authorize('view', $recipient ?? new CareRecipient);

        abort_if($recipient === null, 404);

        return $this->searcher->search($recipient->id, $args['query']);
    }
}
