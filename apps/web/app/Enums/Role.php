<?php

namespace App\Enums;

/**
 * The six care-team roles. Coarse role comes from ZITADEL claims; anything
 * finer-grained ("may THIS provider see THIS recipient?") is answered by
 * OpenFGA relationships, never by role checks alone.
 */
enum Role: string
{
    case Administrator = 'administrator';
    case Doctor = 'doctor';
    case Nurse = 'nurse';
    case Transcriptionist = 'transcriptionist';
    case CareProvider = 'care_provider';
    case CareRecipient = 'care_recipient';

    /** Roles allowed to author a diagnosis/treatment (doctors only — nurses read/print/send). */
    public function mayWriteDiagnosis(): bool
    {
        return $this === self::Doctor;
    }

    public function isStaff(): bool
    {
        return $this !== self::CareRecipient;
    }
}
