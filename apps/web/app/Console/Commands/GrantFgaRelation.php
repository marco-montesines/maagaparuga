<?php

namespace App\Console\Commands;

use App\Services\OpenFga\OpenFgaClient;
use Illuminate\Console\Command;

/**
 * Grants a subject (a ZITADEL user id — a person or a service account) an
 * OpenFGA relation on one or more care recipients. The seam for tuples that
 * have no care-record row of their own:
 *   - `device`         → an IoMT emitter may stream a recipient's vitals
 *   - `service_reader` → a trusted internal read-only service (e.g. the
 *                        assessment engine) may read a recipient's vitals
 *
 * Idempotent (writing an existing tuple is a no-op). Used by
 * `make dev-device-auth` and `make dev-assessment-grpc`.
 */
class GrantFgaRelation extends Command
{
    protected $signature = 'fga:grant {subject : ZITADEL user id} {relation : e.g. device, service_reader} {recipients* : care recipient ids}';

    protected $description = 'Grant an FGA relation to a subject on the given care recipients';

    public function handle(OpenFgaClient $fga): int
    {
        $subject = (string) $this->argument('subject');
        $relation = (string) $this->argument('relation');

        /** @var array<int, string> $recipients */
        $recipients = $this->argument('recipients');

        $tuples = array_map(fn (string $id): array => [
            'user' => 'user:'.$subject,
            'relation' => $relation,
            'object' => 'care_recipient:'.$id,
        ], $recipients);

        $fga->writeTuples($tuples);

        $this->info(count($tuples).' '.$relation.' tuple(s) written for user:'.$subject.'.');

        return self::SUCCESS;
    }
}
