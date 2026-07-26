<?php

namespace App\Models;

use Database\Factories\QuestionnaireResponseFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class QuestionnaireResponse extends Model
{
    /** @use HasFactory<QuestionnaireResponseFactory> */
    use HasFactory;

    protected $fillable = ['care_recipient_id', 'instrument', 'answers', 'submitted_at'];

    protected function casts(): array
    {
        return [
            'answers' => 'array',
            'submitted_at' => 'datetime',
        ];
    }

    /** @return BelongsTo<CareRecipient, $this> */
    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }
}
