<?php

namespace App\GraphQL\Queries;

use App\Models\CareRecipient;
use App\Services\Telemetry\VitalsReader;
use Illuminate\Support\Facades\Gate;

/**
 * The BFF aggregate (ADR 0010): one query, four backends —
 * PostgreSQL record + telemetry vitals + assessment results + open alerts.
 */
class DashboardQuery
{
    public function __construct(private readonly VitalsReader $vitals) {}

    /** @param array{careRecipientId: int|string} $args */
    public function __invoke(mixed $root, array $args): array
    {
        $recipient = CareRecipient::findOrFail($args['careRecipientId']);

        Gate::authorize('view', $recipient);

        return [
            'recipient' => $recipient,
            'vitalsWindow' => $this->vitals->latestWindow($recipient->id),
            'latestAssessments' => $recipient->assessmentResults()->limit(10)->get(),
            'openAlerts' => $recipient->alerts()->whereNull('acknowledged_at')->get(),
        ];
    }
}
