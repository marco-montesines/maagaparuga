<?php

use App\Enums\Role;
use App\Models\Alert;
use App\Models\CareRecipient;
use App\Models\User;
use Database\Seeders\DatabaseSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;

uses(RefreshDatabase::class);

beforeEach(function () {
    // Keep the suite hermetic: seeding triggers the transcription-indexing
    // job (sync queue in tests would call OpenSearch over the network).
    \Illuminate\Support\Facades\Queue::fake();
});

it('seeds the fictitious care domain', function () {
    $this->seed(DatabaseSeeder::class);

    expect(User::count())->toBe(7)
        ->and(CareRecipient::count())->toBe(4)
        ->and(Alert::count())->toBeGreaterThan(0);

    // Mock-data rules: example.com emails only, "Demo" marker names.
    User::all()->each(function (User $user) {
        expect($user->email)->toEndWith('@example.com');
        expect($user->name)->toContain('Demo');
    });
});

it('keeps diagnosis writing doctor-only at the role level', function () {
    expect(Role::Doctor->mayWriteDiagnosis())->toBeTrue()
        ->and(Role::Nurse->mayWriteDiagnosis())->toBeFalse()
        ->and(Role::Administrator->mayWriteDiagnosis())->toBeFalse();
});

it('fails closed when OpenFGA is not configured', function () {
    $this->seed(DatabaseSeeder::class);

    $nurse = User::where('role', Role::Nurse->value)->firstOrFail();
    $recipient = CareRecipient::firstOrFail();

    // No FGA store configured in tests -> fine-grained checks must DENY,
    // even though the nurse is assigned in the database.
    expect($nurse->can('view', $recipient))->toBeFalse();
});

it('lets administrators view without relationship checks', function () {
    $this->seed(DatabaseSeeder::class);

    $admin = User::where('role', Role::Administrator->value)->firstOrFail();

    expect($admin->can('view', CareRecipient::firstOrFail()))->toBeTrue();
});
