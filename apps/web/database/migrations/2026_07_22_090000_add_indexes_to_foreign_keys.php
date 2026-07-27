<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Laravel's foreignId()->constrained() creates the constraint but NOT an index.
 * MySQL auto-indexes foreign keys; PostgreSQL (our database) does not, so the
 * columns listing pages and cascade deletes filter on would sequential-scan.
 * These indexes cover the query paths in the care-recipient and alert
 * controllers and the cascade-on-delete lookups.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('care_team_assignments', function (Blueprint $table) {
            $table->index('care_recipient_id');
        });
        Schema::table('general_medical_infos', function (Blueprint $table) {
            // care_recipient_id is unique here, already indexed.
        });
        Schema::table('consultations', function (Blueprint $table) {
            $table->index('care_recipient_id');
            $table->index('staff_user_id');
        });
        Schema::table('consultation_attachments', function (Blueprint $table) {
            $table->index('consultation_id');
        });
        Schema::table('transcriptions', function (Blueprint $table) {
            $table->index('consultation_id');
            $table->index('author_user_id');
        });
        Schema::table('questionnaire_responses', function (Blueprint $table) {
            $table->index('care_recipient_id');
        });
        Schema::table('assessment_results', function (Blueprint $table) {
            $table->index('care_recipient_id');
        });
        Schema::table('alerts', function (Blueprint $table) {
            // The inbox filters open alerts per recipient.
            $table->index(['care_recipient_id', 'acknowledged_at']);
        });
    }

    public function down(): void
    {
        Schema::table('care_team_assignments', fn (Blueprint $t) => $t->dropIndex(['care_recipient_id']));
        Schema::table('consultations', function (Blueprint $t) {
            $t->dropIndex(['care_recipient_id']);
            $t->dropIndex(['staff_user_id']);
        });
        Schema::table('consultation_attachments', fn (Blueprint $t) => $t->dropIndex(['consultation_id']));
        Schema::table('transcriptions', function (Blueprint $t) {
            $t->dropIndex(['consultation_id']);
            $t->dropIndex(['author_user_id']);
        });
        Schema::table('questionnaire_responses', fn (Blueprint $t) => $t->dropIndex(['care_recipient_id']));
        Schema::table('assessment_results', fn (Blueprint $t) => $t->dropIndex(['care_recipient_id']));
        Schema::table('alerts', fn (Blueprint $t) => $t->dropIndex(['care_recipient_id', 'acknowledged_at']));
    }
};
