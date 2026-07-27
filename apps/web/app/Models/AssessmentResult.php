<?php

namespace App\Models;

use App\Enums\RiskLevel;
use Database\Factories\AssessmentResultFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Written by the assessment service (NEWS2, DASS21 subscales, fuzzy risk).
 *
 * @property RiskLevel $risk_level
 */
class AssessmentResult extends Model
{
    /** @use HasFactory<AssessmentResultFactory> */
    use HasFactory;

    protected $fillable = [
        'care_recipient_id', 'score_type', 'value', 'risk_level', 'source', 'computed_at',
    ];

    protected function casts(): array
    {
        return [
            'risk_level' => RiskLevel::class,
            'value' => 'decimal:2',
            'computed_at' => 'datetime',
        ];
    }

    /** @return BelongsTo<CareRecipient, $this> */
    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }
}
