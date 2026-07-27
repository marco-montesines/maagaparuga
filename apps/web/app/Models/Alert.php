<?php

namespace App\Models;

use App\Enums\RiskLevel;
use Database\Factories\AlertFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * The alerts inbox — "detect early, assess continuously, refer promptly".
 * Created when an assessment result crosses the risk threshold.
 *
 * @property RiskLevel $severity
 */
class Alert extends Model
{
    /** @use HasFactory<AlertFactory> */
    use HasFactory;

    protected $fillable = [
        'care_recipient_id', 'assessment_result_id', 'severity',
        'title', 'body', 'acknowledged_by', 'acknowledged_at',
    ];

    protected function casts(): array
    {
        return [
            'severity' => RiskLevel::class,
            'acknowledged_at' => 'datetime',
        ];
    }

    /** @return BelongsTo<CareRecipient, $this> */
    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }

    /** @return BelongsTo<AssessmentResult, $this> */
    public function assessmentResult(): BelongsTo
    {
        return $this->belongsTo(AssessmentResult::class);
    }

    /** @return BelongsTo<User, $this> */
    public function acknowledgedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'acknowledged_by');
    }
}
