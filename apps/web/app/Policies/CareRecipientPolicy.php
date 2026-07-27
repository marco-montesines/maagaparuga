<?php

namespace App\Policies;

use App\Enums\Role;
use App\Models\CareRecipient;
use App\Models\User;
use App\Services\OpenFga\OpenFgaClient;

/**
 * Coarse role gates + fine-grained OpenFGA relationship checks (ADR 0009).
 * Administrators bypass relationship checks; everyone else must hold the
 * relevant relation on the specific care recipient.
 */
class CareRecipientPolicy
{
    public function __construct(private readonly OpenFgaClient $fga) {}

    public function view(User $user, CareRecipient $recipient): bool
    {
        if ($user->role === Role::Administrator) {
            return true;
        }

        return $this->fga->check($user->fgaUser(), 'viewer', $recipient->fgaObject());
    }

    public function update(User $user, CareRecipient $recipient): bool
    {
        if ($user->role === Role::Administrator) {
            return true;
        }

        return $user->role->isStaff()
            && $this->fga->check($user->fgaUser(), 'editor', $recipient->fgaObject());
    }

    /** Diagnosis/treatment content is doctor-only (nurses read/print/send). */
    public function writeDiagnosis(User $user, CareRecipient $recipient): bool
    {
        return $user->role->mayWriteDiagnosis()
            && $this->fga->check($user->fgaUser(), 'editor', $recipient->fgaObject());
    }
}
