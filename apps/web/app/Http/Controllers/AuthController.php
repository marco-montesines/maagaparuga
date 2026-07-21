<?php

namespace App\Http\Controllers;

use App\Enums\Role;
use App\Models\User;
use Illuminate\Http\RedirectResponse;
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

    public function redirect(): RedirectResponse
    {
        return Socialite::driver('zitadel')->redirect();
    }

    public function callback(): RedirectResponse
    {
        $oidcUser = Socialite::driver('zitadel')->user();

        $claims = $oidcUser->user ?? [];
        $role = $this->roleFromClaims($claims[self::ROLES_CLAIM] ?? []);

        $user = User::updateOrCreate(
            ['zitadel_sub' => $oidcUser->getId()],
            [
                'name' => $oidcUser->getName() ?? $oidcUser->getNickname() ?? 'Unknown',
                'email' => $oidcUser->getEmail(),
                'role' => $role,
            ],
        );

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
     * org grants; role keys are our Role enum values. Least-privilege default:
     * an authenticated user with no recognized role is a care recipient.
     */
    private function roleFromClaims(array $rolesClaim): Role
    {
        foreach (Role::cases() as $role) {
            if (array_key_exists($role->value, $rolesClaim)) {
                return $role;
            }
        }

        return Role::CareRecipient;
    }
}
