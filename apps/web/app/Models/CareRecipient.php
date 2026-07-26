<?php

namespace App\Models;

use App\Enums\CareContext;
use Database\Factories\CareRecipientFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

class CareRecipient extends Model
{
    /** @use HasFactory<CareRecipientFactory> */
    use HasFactory;

    protected $fillable = [
        'user_id', 'name', 'birthdate', 'phone', 'address', 'care_context',
        'emergency_contact_name', 'emergency_contact_relationship',
        'emergency_contact_phone', 'insurance_provider', 'insurance_number',
    ];

    protected function casts(): array
    {
        return [
            'care_context' => CareContext::class,
            'birthdate' => 'date',
        ];
    }

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return HasMany<CareTeamAssignment, $this> */
    public function assignments(): HasMany
    {
        return $this->hasMany(CareTeamAssignment::class);
    }

    /** @return HasOne<GeneralMedicalInfo, $this> */
    public function medicalInfo(): HasOne
    {
        return $this->hasOne(GeneralMedicalInfo::class);
    }

    /** @return HasMany<Consultation, $this> */
    public function consultations(): HasMany
    {
        return $this->hasMany(Consultation::class)->orderByDesc('consulted_at');
    }

    /** @return HasMany<QuestionnaireResponse, $this> */
    public function questionnaireResponses(): HasMany
    {
        return $this->hasMany(QuestionnaireResponse::class);
    }

    /** @return HasMany<AssessmentResult, $this> */
    public function assessmentResults(): HasMany
    {
        return $this->hasMany(AssessmentResult::class)->orderByDesc('computed_at');
    }

    /** @return HasMany<Alert, $this> */
    public function alerts(): HasMany
    {
        return $this->hasMany(Alert::class)->orderByDesc('created_at');
    }

    /** OpenFGA object identifier for this care recipient. */
    public function fgaObject(): string
    {
        return 'care_recipient:'.$this->id;
    }
}
