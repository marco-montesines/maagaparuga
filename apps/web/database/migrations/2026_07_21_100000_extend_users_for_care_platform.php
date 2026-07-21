<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * ZITADEL owns credentials (ADR 0009) — there is deliberately NO local
 * password store. `password` becomes nullable and unused; the account is
 * keyed by the OIDC subject. One user table + role enum, never per-role
 * tables (documented anti-pattern from the predecessor systems).
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->string('zitadel_sub')->nullable()->unique();
            $table->string('role')->default('care_recipient')->index();
            $table->date('birthdate')->nullable();
            $table->string('phone', 32)->nullable();
            $table->string('specialization')->nullable();   // doctors
            $table->string('license_id')->nullable();       // doctors
            $table->string('affiliation')->nullable();      // staff clinic/hospital
            $table->string('password')->nullable()->change();
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->dropColumn([
                'zitadel_sub', 'role', 'birthdate', 'phone',
                'specialization', 'license_id', 'affiliation',
            ]);
        });
    }
};
