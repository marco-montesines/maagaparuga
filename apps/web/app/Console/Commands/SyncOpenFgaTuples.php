<?php

namespace App\Console\Commands;

use App\Models\CareRecipient;
use App\Models\CareTeamAssignment;
use App\Services\OpenFga\OpenFgaClient;
use Illuminate\Console\Command;

/**
 * Re-derives every OpenFGA tuple from the database (rows are the source of
 * truth, tuples the enforcement copy). Heals drift after FGA downtime or a
 * store rebuild. Idempotent: writing an existing tuple is harmless.
 */
class SyncOpenFgaTuples extends Command
{
    protected $signature = 'fga:sync';

    protected $description = 'Write all care-team assignment + owner tuples to OpenFGA';

    public function handle(OpenFgaClient $fga): int
    {
        $tuples = [];

        CareTeamAssignment::query()->where('active', true)->get()
            ->each(function (CareTeamAssignment $assignment) use (&$tuples): void {
                $tuples[] = [
                    'user' => 'user:'.$assignment->user_id,
                    'relation' => 'assigned_staff',
                    'object' => 'care_recipient:'.$assignment->care_recipient_id,
                ];
            });

        CareRecipient::query()->whereNotNull('user_id')->get()
            ->each(function (CareRecipient $recipient) use (&$tuples): void {
                $tuples[] = [
                    'user' => 'user:'.$recipient->user_id,
                    'relation' => 'owner',
                    'object' => $recipient->fgaObject(),
                ];
            });

        foreach (array_chunk($tuples, 50) as $chunk) {
            $fga->writeTuples($chunk);
        }

        $this->info(count($tuples).' tuples written.');

        return self::SUCCESS;
    }
}
