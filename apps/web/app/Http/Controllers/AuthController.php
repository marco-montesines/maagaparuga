<?php

namespace App\Http\Controllers;

use App\Enums\Role;
use App\Models\User;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Laravel\Socialite\Facades\Socialite;

/**
 * ZITADEL OIDC login (Authorization Code + PKCE via Socialite). No local
 * credentials exist — ZITADEL owns identity; this controller only maps the
 * OIDC subject + role claim onto the local account row.
 */
class AuthController extends Controller
{
    private const ROLES_CLAIM = 'urn:zitadel:iam:org:project:roles';

    public function redirect(): \Symfony\Component\HttpFoundation\RedirectResponse
    {
        return Socialite::driver('zitadel')->redirect();
    }

    public function callback(Request $request): RedirectResponse
    {
        $oidcUser = Socialite::driver('zitadel')->user();

        $claims = $oidcUser->user ?? [];
        $subject = $oidcUser->getId();
        $email = $oidcUser->getEmail();

        // Match an existing account by OIDC subject first, then by email so a
        // seeded persona (created with an email but no subject yet) is claimed
        // on first login instead of colliding on the unique email and 500ing.
        $user = User::firstWhere('zitadel_sub', $subject)
            ?? ($email !== null ? User::firstWhere('email', $email) : null)
            ?? new User;

        $user->zitadel_sub = $subject;
        $user->name = $oidcUser->getName() ?? $oidcUser->getNickname() ?? $user->name ?? 'Unknown';
        if ($email !== null) {
            $user->email = $email;
        }
        // Only apply a role the identity provider actually asserted. A missing
        // or unparseable roles claim must not silently demote an existing
        // administrator to care recipient (least privilege applies to NEW
        // accounts, not to overwriting a known one).
        $assertedRole = $this->roleFromClaims($claims[self::ROLES_CLAIM] ?? [], $user->exists);
        if ($assertedRole !== null) {
            $user->role = $assertedRole;
        }
        $user->save();

        // Prevent session fixation: adopt a fresh session id at login.
        $request->session()->regenerate();

        Auth::login($user, remember: true);

        return redirect()->intended('/dashboard');
    }

    public function logout(): RedirectResponse
    {
        Auth::logout();
        session()->invalidate();
        session()->regenerateToken();

        // RP-initiated logout at ZITADEL ends the SSO session too.
        $endSession = rtrim((string) config('services.zitadel.base_url'), '/')
            .'/oidc/v1/end_session';

        return redirect()->away($endSession);
    }

    /**
     * ZITADEL project-roles claim -> local Role. The claim maps role keys to
     * org grants; role keys are our Role enum values.
     *
     * Returns null when the claim asserts no recognized role. For a NEW
     * account the caller substitutes the least-privilege default (care
     * recipient); for an EXISTING account null means "leave the stored role
     * untouched" so a claim hiccup can't demote staff.
     */
    private function roleFromClaims(array $rolesClaim, bool $userExists): ?Role
    {
        foreach (Role::cases() as $role) {
            if (array_key_exists($role->value, $rolesClaim)) {
                return $role;
            }
        }

        return $userExists ? null : Role::CareRecipient;
    }
}
