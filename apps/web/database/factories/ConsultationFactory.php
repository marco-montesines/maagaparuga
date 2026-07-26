<?php

namespace Database\Factories;

use App\Models\CareRecipient;
use App\Models\Consultation;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Consultation>
 */
class ConsultationFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'care_recipient_id' => CareRecipient::factory(),
            'staff_user_id' => User::factory(),
            'consulted_at' => now(),
            'pulse_bpm' => fake()->numberBetween(55, 110),
            'temperature_c' => fake()->randomFloat(1, 36, 38),
            'bp_systolic' => fake()->numberBetween(100, 150),
            'bp_diastolic' => fake()->numberBetween(60, 95),
            'chief_complaint' => 'Synthetic sample complaint for demonstration.',
        ];
    }
}
