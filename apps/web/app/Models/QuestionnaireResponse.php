<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class QuestionnaireResponse extends Model
{
    use HasFactory;

    protected $fillable = ['care_recipient_id', 'instrument', 'answers', 'submitted_at'];

    protected function casts(): array
    {
        return [
            'answers' => 'array',
            'submitted_at' => 'datetime',
        ];
    }

    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }
}
