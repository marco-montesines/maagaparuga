<?php

namespace Database\Factories;

use App\Models\Consultation;
use App\Models\Transcription;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Transcription>
 */
class TranscriptionFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'consultation_id' => Consultation::factory(),
            'author_user_id' => User::factory(),
            'body' => '[synthetic transcript] Consultation notes for demonstration purposes only.',
        ];
    }
}
