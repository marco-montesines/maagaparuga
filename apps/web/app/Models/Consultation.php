<?php

namespace App\Models;

use Database\Factories\ConsultationFactory;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Consultation extends Model
{
    /** @use HasFactory<ConsultationFactory> */
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

    /** @return BelongsTo<CareRecipient, $this> */
    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }

    /** @return BelongsTo<User, $this> */
    public function staff(): BelongsTo
    {
        return $this->belongsTo(User::class, 'staff_user_id');
    }

    /** @return HasMany<ConsultationAttachment, $this> */
    public function attachments(): HasMany
    {
        return $this->hasMany(ConsultationAttachment::class);
    }

    /** @return HasMany<Transcription, $this> */
    public function transcriptions(): HasMany
    {
        return $this->hasMany(Transcription::class);
    }

    /**
     * Mean arterial pressure, derived — never stored.
     *
     * @return Attribute<float|null, never>
     */
    protected function meanArterialPressure(): Attribute
    {
        // larastan Attribute-accessor false positive: it reports the correct
        // Attribute<float|null, never> return as mismatching itself.
        // @phpstan-ignore-next-line
        return Attribute::get(function (): ?float {
            if ($this->bp_systolic === null || $this->bp_diastolic === null) {
                return null;
            }

            return round(($this->bp_systolic + 2 * $this->bp_diastolic) / 3, 1);
        });
    }
}
