<?php

namespace App\Http\Controllers;

use App\Enums\Role;
use App\Models\Alert;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\Gate;

class AlertController extends Controller
{
    /** The alerts inbox: open alerts for recipients this user may see. */
    public function index(): View
    {
        $user = auth()->user();

        $alerts = Alert::with('careRecipient', 'assessmentResult')
            ->whereNull('acknowledged_at')
            ->when($user->role !== Role::Administrator, fn ($q) => $q->whereHas(
                'careRecipient.assignments',
                fn ($a) => $a->where('user_id', $user->id)->where('active', true),
            ))
            ->orderByDesc('created_at')
            ->get();

        return view('alerts.index', ['alerts' => $alerts]);
    }

    public function acknowledge(Alert $alert): RedirectResponse
    {
        // Acknowledging is a staff write, not a read — 'update' additionally
        // requires isStaff(), so a care recipient cannot clear their own alert
        // out of the care team's inbox.
        Gate::authorize('update', $alert->careRecipient);

        // Idempotent: the first acknowledgement stands; re-posting does not
        // reassign who acknowledged it.
        if ($alert->acknowledged_at === null) {
            $alert->forceFill([
                'acknowledged_by' => auth()->id(),
                'acknowledged_at' => now(),
            ])->save();
        }

        return back()->with('status', 'Alert acknowledged.');
    }
}
