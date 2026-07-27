<?php

namespace App\Enums;

/** Fuzzy risk bands (SEDS-inspired concept). High and above triggers an alert. */
enum RiskLevel: string
{
    case VeryLow = 'very_low';
    case Low = 'low';
    case Moderate = 'moderate';
    case High = 'high';
    case ExtremelyHigh = 'extremely_high';

    public function triggersAlert(): bool
    {
        return in_array($this, [self::High, self::ExtremelyHigh], true);
    }
}
