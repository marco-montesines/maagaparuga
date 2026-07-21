<?php

namespace App\Services\Telemetry;

/** Deterministic synthetic vitals (seeded per recipient) until P3's gRPC client lands. */
class FakeVitalsReader implements VitalsReader
{
    public function latestWindow(int $careRecipientId, int $samples = 12): array
    {
        mt_srand($careRecipientId * 7919);
        $now = now();
        $window = [];

        for ($i = $samples - 1; $i >= 0; $i--) {
            $window[] = [
                'measuredAt' => $now->copy()->subMinutes(5 * $i)->toDateTimeImmutable(),
                'heartRateBpm' => 62 + mt_rand(0, 30),
                'spo2Percent' => round(95 + mt_rand(0, 40) / 10, 1),
                'bpSystolic' => 105 + mt_rand(0, 30),
                'bpDiastolic' => 65 + mt_rand(0, 20),
                'temperatureC' => round(36.2 + mt_rand(0, 15) / 10, 1),
                'respiratoryRate' => 13 + mt_rand(0, 6),
            ];
        }

        return $window;
    }
}
