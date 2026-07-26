<?php

namespace App\Models;

use Database\Factories\CareTeamAssignmentFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Staff <-> care-recipient assignment (generalizes the old doctor/patient m:n
 * to any staff role). Mirrored into OpenFGA as
 * `user:{user_id} assigned_staff care_recipient:{care_recipient_id}` —
 * the row is the source of truth, the FGA tuple is the enforcement copy.
 */
class CareTeamAssignment extends Model
{
    /** @use HasFactory<CareTeamAssignmentFactory> */
    use HasFactory;

    protected $fillable = ['user_id', 'care_recipient_id', 'role_at_assignment', 'active'];

    protected function casts(): array
    {
        return ['active' => 'boolean'];
    }

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return BelongsTo<CareRecipient, $this> */
    public function careRecipient(): BelongsTo
    {
        return $this->belongsTo(CareRecipient::class);
    }
}
