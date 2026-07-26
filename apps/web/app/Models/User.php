<?php

namespace App\Models;

use App\Enums\Role;
use Database\Factories\UserFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;

/**
 * One account table for all six roles (never per-role tables — a documented
 * anti-pattern from the predecessor systems). Authentication is delegated to
 * ZITADEL — `zitadel_sub` is the identity key; there is no usable local
 * password.
 */
class User extends Authenticatable
{
    /** @use HasFactory<UserFactory> */
    use HasFactory, Notifiable;

    protected $fillable = [
        'name', 'email', 'zitadel_sub', 'role', 'birthdate', 'phone',
        'specialization', 'license_id', 'affiliation',
    ];

    protected $hidden = ['password', 'remember_token'];

    protected function casts(): array
    {
        return [
            'role' => Role::class,
            'birthdate' => 'date',
        ];
    }

    /** @return HasOne<CareRecipient, $this> */
    public function careRecipientProfile(): HasOne
    {
        return $this->hasOne(CareRecipient::class);
    }

    /** @return HasMany<CareTeamAssignment, $this> */
    public function assignments(): HasMany
    {
        return $this->hasMany(CareTeamAssignment::class);
    }

    /** OpenFGA subject identifier for this user. */
    public function fgaUser(): string
    {
        return 'user:'.$this->id;
    }
}
