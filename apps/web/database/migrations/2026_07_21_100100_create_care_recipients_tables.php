<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('care_recipients', function (Blueprint $table) {
            $table->id();
            // A recipient may or may not have a login of their own.
            $table->foreignId('user_id')->nullable()->unique()->constrained()->nullOnDelete();
            $table->string('name');
            $table->date('birthdate')->nullable();
            $table->string('phone', 32)->nullable();
            $table->string('address')->nullable();
            $table->string('care_context')->default('general')->index();
            $table->string('emergency_contact_name')->nullable();
            $table->string('emergency_contact_relationship')->nullable();
            $table->string('emergency_contact_phone', 32)->nullable();
            $table->string('insurance_provider')->nullable();
            $table->string('insurance_number')->nullable();
            $table->timestamps();
        });

        Schema::create('care_team_assignments', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->foreignId('care_recipient_id')->constrained()->cascadeOnDelete();
            $table->string('role_at_assignment');
            $table->boolean('active')->default(true)->index();
            $table->timestamps();
            $table->unique(['user_id', 'care_recipient_id']);
        });

        Schema::create('general_medical_infos', function (Blueprint $table) {
            $table->id();
            $table->foreignId('care_recipient_id')->unique()->constrained()->cascadeOnDelete();
            $table->string('blood_type', 8)->nullable();
            $table->decimal('height_cm', 5, 1)->nullable();
            $table->decimal('weight_kg', 5, 1)->nullable();
            $table->text('allergies')->nullable();
            $table->text('surgeries')->nullable();
            $table->text('immunizations')->nullable();
            $table->json('family_history')->nullable();   // {diabetes: bool, asthma: bool, ...}
            $table->text('past_illnesses')->nullable();
            $table->text('treatment_history')->nullable();
            $table->timestamp('last_visit_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('general_medical_infos');
        Schema::dropIfExists('care_team_assignments');
        Schema::dropIfExists('care_recipients');
    }
};
