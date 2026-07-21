<?php

namespace App\Observers;

use App\Models\CareTeamAssignment;
use App\Services\OpenFga\OpenFgaClient;

/**
 * Keeps OpenFGA tuples in sync with care_team_assignments — the row is the
 * source of truth, the tuple is the enforcement copy.
 */
class CareTeamAssignmentObserver
{
    public function __construct(private readonly OpenFgaClient $fga) {}

    public function created(CareTeamAssignment $assignment): void
    {
        if ($assignment->active) {
            $this->fga->writeTuples([$this->tuple($assignment)]);
        }
    }

    public function updated(CareTeamAssignment $assignment): void
    {
        if ($assignment->wasChanged('active')) {
            $assignment->active
                ? $this->fga->writeTuples([$this->tuple($assignment)])
                : $this->fga->deleteTuples([$this->tuple($assignment)]);
        }
    }

    public function deleted(CareTeamAssignment $assignment): void
    {
        $this->fga->deleteTuples([$this->tuple($assignment)]);
    }

    /** @return array{user: string, relation: string, object: string} */
    private function tuple(CareTeamAssignment $assignment): array
    {
        return [
            'user' => 'user:'.$assignment->user_id,
            'relation' => 'assigned_staff',
            'object' => 'care_recipient:'.$assignment->care_recipient_id,
        ];
    }
}
