<?php

namespace App\Models;

use Database\Factories\GeneralMedicalInfoFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class GeneralMedicalInfo extends Model
{
    /** @use HasFactory<GeneralMedicalInfoFactory> */
    use HasFactory;

    protected $fillable = [
        'care_recipient_id', 'blood_type', 'height_cm', 'weight_kg',
        'allergies', 'surgeries', 'immunizations', 'family_history',
        'past_illnesses', 'treatment_history', 'last_visit_at',
    ];

    protected function casts(): array
    {
        return [
            'family_history' => 'array',
            'height_cm' => 'decimal:1',
            'weight_kg' => 'decimal:1',
            'last_visit_at' => 'datetime',
        ];
    }

    /** @return BelongsTo<CareRecipient, $this> */
    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }
}
