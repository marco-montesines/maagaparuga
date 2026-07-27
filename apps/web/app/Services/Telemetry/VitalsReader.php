<?php

namespace App\Services\Telemetry;

/**
 * Windowed vitals reads from the telemetry service. The real implementation
 * calls the Go service's gRPC read API; until then a fake supplies
 * clearly-synthetic samples so the BFF contract is exercised end to end.
 */
interface VitalsReader
{
    /**
     * @return array<int, array{
     *   measuredAt: \DateTimeInterface,
     *   heartRateBpm: int|null,
     *   spo2Percent: float|null,
     *   bpSystolic: int|null,
     *   bpDiastolic: int|null,
     *   temperatureC: float|null,
     *   respiratoryRate: int|null,
     * }>
     */
    public function latestWindow(int $careRecipientId, int $samples = 12): array;
}
