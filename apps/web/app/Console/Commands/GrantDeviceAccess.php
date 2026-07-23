<?php

namespace App\Console\Commands;

use App\Services\OpenFga\OpenFgaClient;
use Illuminate\Console\Command;

/**
 * Grants an IoMT device (a ZITADEL service-account subject) the `device`
 * relation on one or more care recipients, so its telemetry stream is
 * authorized to write vitals — and nothing else (see fga/model.fga:
 * `vitals_writer` = assigned_staff or device).
 *
 * Device→recipient assignments have no database table of their own (a device
 * is provisioned in the identity provider, not the care record), so this is the
 * seam that writes those tuples. Idempotent: writing an existing tuple is a
 * no-op. Used by `make dev-device-auth`, and available in any environment to
 * enroll a real (mock) device against real (mock) recipients.
 */
class GrantDeviceAccess extends Command
{
    protected $signature = 'fga:device {subject : ZITADEL user id of the device service account} {recipients* : care recipient ids}';

    protected $description = 'Authorize a device subject to stream vitals for the given care recipients';

    public function handle(OpenFgaClient $fga): int
    {
        $subject = (string) $this->argument('subject');

        /** @var array<int, string> $recipients */
        $recipients = $this->argument('recipients');

        $tuples = array_map(fn (string $id): array => [
            'user' => 'user:'.$subject,
            'relation' => 'device',
            'object' => 'care_recipient:'.$id,
        ], $recipients);

        $fga->writeTuples($tuples);

        $this->info(count($tuples).' device tuple(s) written for user:'.$subject.'.');

        return self::SUCCESS;
    }
}
