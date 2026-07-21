<?php

use App\Http\Controllers\AlertController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\CareRecipientController;
use Illuminate\Support\Facades\Route;

Route::get('/', fn () => view('welcome'));

// ZITADEL OIDC (Authorization Code + PKCE) — no local credentials anywhere.
Route::get('/auth/redirect', [AuthController::class, 'redirect'])->name('login');
Route::get('/auth/callback', [AuthController::class, 'callback']);
Route::post('/auth/logout', [AuthController::class, 'logout'])
    ->middleware('auth')->name('logout');

Route::middleware('auth')->group(function (): void {
    Route::view('/dashboard', 'dashboard')->name('dashboard');

    Route::get('/care-recipients', [CareRecipientController::class, 'index'])
        ->name('care-recipients.index');
    Route::get('/care-recipients/{careRecipient}', [CareRecipientController::class, 'show'])
        ->name('care-recipients.show');

    Route::get('/alerts', [AlertController::class, 'index'])->name('alerts.index');
    Route::post('/alerts/{alert}/acknowledge', [AlertController::class, 'acknowledge'])
        ->name('alerts.acknowledge');
});
