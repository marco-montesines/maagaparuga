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
        Gate::authorize('view', $alert->careRecipient);

        $alert->forceFill([
            'acknowledged_by' => auth()->id(),
            'acknowledged_at' => now(),
        ])->save();

        return back()->with('status', 'Alert acknowledged.');
    }
}
