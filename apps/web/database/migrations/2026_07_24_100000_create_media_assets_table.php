<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Catalogue of mock media uploads. The binary lives in the object store
        // (claim-check); this row holds only metadata. The media service owns the
        // lifecycle column; transcript segments live in OpenSearch, not here.
        Schema::create('media_assets', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('care_recipient_id')->constrained()->cascadeOnDelete();
            $table->string('kind')->index();          // xray, ultrasound_2d, ..., teleconsult
            $table->string('filename');
            $table->string('content_type');
            $table->unsignedBigInteger('size_bytes');
            $table->string('object_key');             // bucket-relative key
            $table->string('status')->index();        // uploaded, processing, indexed, skipped, failed
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('media_assets');
    }
};
