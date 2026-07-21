<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Consultation extends Model
{
    use HasFactory;

    protected $fillable = [
        'care_recipient_id', 'staff_user_id', 'consulted_at',
        'pulse_bpm', 'temperature_c', 'bp_systolic', 'bp_diastolic',
        'chief_complaint', 'diagnosis', 'treatment', 'prescription',
    ];

    protected function casts(): array
    {
        return [
            'consulted_at' => 'datetime',
            'temperature_c' => 'decimal:1',
        ];
    }

    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }

    public function staff(): BelongsTo
    {
        return $this->belongsTo(User::class, 'staff_user_id');
    }

    public function attachments(): HasMany
    {
        return $this->hasMany(ConsultationAttachment::class);
    }

    public function transcriptions(): HasMany
    {
        return $this->hasMany(Transcription::class);
    }

    /** Mean arterial pressure, derived — never stored. */
    protected function meanArterialPressure(): Attribute
    {
        return Attribute::get(function (): ?float {
            if ($this->bp_systolic === null || $this->bp_diastolic === null) {
                return null;
            }

            return round(($this->bp_systolic + 2 * $this->bp_diastolic) / 3, 1);
        });
    }
}
