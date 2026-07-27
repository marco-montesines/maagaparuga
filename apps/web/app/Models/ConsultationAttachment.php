<?php

namespace App\Models;

use App\Enums\AttachmentKind;
use Database\Factories\ConsultationAttachmentFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * References into the S3 data lake (claim-check: the binary never lives in
 * PostgreSQL). `media_id` links to the media-service catalog once the media
 * pipeline has processed the object (transcript + embeddings).
 */
class ConsultationAttachment extends Model
{
    /** @use HasFactory<ConsultationAttachmentFactory> */
    use HasFactory;

    protected $fillable = ['consultation_id', 'kind', 'object_key', 'media_id', 'caption'];

    protected function casts(): array
    {
        return ['kind' => AttachmentKind::class];
    }

    /** @return BelongsTo<Consultation, $this> */
    public function consultation(): BelongsTo
    {
        return $this->belongsTo(Consultation::class);
    }
}
