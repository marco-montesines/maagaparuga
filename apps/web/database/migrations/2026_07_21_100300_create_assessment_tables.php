<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Raw questionnaire responses; scoring is the assessment service's job
        // (it writes assessment_results back here).
        Schema::create('questionnaire_responses', function (Blueprint $table) {
            $table->id();
            $table->foreignId('care_recipient_id')->constrained()->cascadeOnDelete();
            $table->string('instrument')->index();   // e.g. dass21
            $table->json('answers');                 // item id -> value
            $table->timestamp('submitted_at');
            $table->timestamps();
        });

        Schema::create('assessment_results', function (Blueprint $table) {
            $table->id();
            $table->foreignId('care_recipient_id')->constrained()->cascadeOnDelete();
            $table->string('score_type')->index();   // news2, dass21_depression, fuzzy_risk, ...
            $table->decimal('value', 8, 2)->nullable();
            $table->string('risk_level')->nullable()->index();
            $table->string('source')->nullable();    // vitals window / questionnaire ref
            $table->timestamp('computed_at')->index();
            $table->timestamps();
        });

        Schema::create('alerts', function (Blueprint $table) {
            $table->id();
            $table->foreignId('care_recipient_id')->constrained()->cascadeOnDelete();
            $table->foreignId('assessment_result_id')->nullable()->constrained()->nullOnDelete();
            $table->string('severity')->index();     // maps RiskLevel
            $table->string('title');
            $table->text('body')->nullable();
            $table->foreignId('acknowledged_by')->nullable()->constrained('users');
            $table->timestamp('acknowledged_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('alerts');
        Schema::dropIfExists('assessment_results');
        Schema::dropIfExists('questionnaire_responses');
    }
};
