<?php

namespace App\Http\Controllers;

use App\Enums\Role;
use App\Models\CareRecipient;
use Illuminate\Contracts\View\View;
use Illuminate\Support\Facades\Gate;

class CareRecipientController extends Controller
{
    /**
     * Listing is filtered database-side by care-team assignment (admins see
     * all). Per-object enforcement still happens through the policy (and
     * therefore OpenFGA) on every show — the list filter is a UX convenience,
     * never the security boundary.
     */
    public function index(): View
    {
        $user = auth()->user();

        $recipients = $user->role === Role::Administrator
            ? CareRecipient::orderBy('name')->get()
            : CareRecipient::whereHas(
                'assignments',
                fn ($q) => $q->where('user_id', $user->id)->where('active', true),
            )->orderBy('name')->get();

        return view('care-recipients.index', ['recipients' => $recipients]);
    }

    public function show(CareRecipient $careRecipient): View
    {
        Gate::authorize('view', $careRecipient);

        $careRecipient->load([
            'medicalInfo',
            'consultations.staff',
            'consultations.attachments',
            'consultations.transcriptions.author',
            'assessmentResults',
            'alerts',
        ]);

        return view('care-recipients.show', [
            'recipient' => $careRecipient,
            'mayWriteDiagnosis' => Gate::allows('writeDiagnosis', $careRecipient),
        ]);
    }
}
