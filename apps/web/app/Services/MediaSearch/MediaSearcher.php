<?php

namespace App\Services\MediaSearch;

/**
 * Hybrid (BM25 + k-NN) media search. The real implementation queries
 * OpenSearch with an app-side query embedding; until then a fake returns
 * clearly-synthetic hits so the BFF contract is exercised.
 */
interface MediaSearcher
{
    /**
     * @return array<int, array{
     *   mediaId: string, objectKey: string, startMs: int, endMs: int,
     *   snippet: string, score: float,
     * }>
     */
    public function search(int $careRecipientId, string $query, int $limit = 10): array;
}
