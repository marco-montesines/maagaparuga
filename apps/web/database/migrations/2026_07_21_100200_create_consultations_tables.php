<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('consultations', function (Blueprint $table) {
            $table->id();
            $table->foreignId('care_recipient_id')->constrained()->cascadeOnDelete();
            $table->foreignId('staff_user_id')->constrained('users');
            $table->timestamp('consulted_at')->index();
            // Vitals snapshot at consultation time (live streams go to ClickHouse
            // via the telemetry service — this is the clinical point-in-time record).
            $table->unsignedSmallInteger('pulse_bpm')->nullable();
            $table->decimal('temperature_c', 4, 1)->nullable();
            $table->unsignedSmallInteger('bp_systolic')->nullable();
            $table->unsignedSmallInteger('bp_diastolic')->nullable();
            $table->text('chief_complaint')->nullable();
            $table->text('diagnosis')->nullable();     // writable by doctors only (policy)
            $table->text('treatment')->nullable();
            $table->text('prescription')->nullable();
            $table->timestamps();
        });

        Schema::create('consultation_attachments', function (Blueprint $table) {
            $table->id();
            $table->foreignId('consultation_id')->constrained()->cascadeOnDelete();
            $table->string('kind')->index();
            $table->string('object_key');            // S3 data-lake key (claim-check)
            $table->string('media_id')->nullable();  // media-service catalog ref
            $table->string('caption')->nullable();
            $table->timestamps();
        });

        Schema::create('transcriptions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('consultation_id')->constrained()->cascadeOnDelete();
            $table->foreignId('author_user_id')->constrained('users');
            $table->text('body');
            $table->timestamp('indexed_at')->nullable();  // set when pushed to OpenSearch
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('transcriptions');
        Schema::dropIfExists('consultation_attachments');
        Schema::dropIfExists('consultations');
    }
};
