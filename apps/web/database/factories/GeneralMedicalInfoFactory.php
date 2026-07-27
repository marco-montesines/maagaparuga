<?php

namespace Database\Factories;

use App\Models\CareRecipient;
use App\Models\GeneralMedicalInfo;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<GeneralMedicalInfo>
 */
class GeneralMedicalInfoFactory extends Factory
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
            'blood_type' => fake()->randomElement(['A+', 'O+', 'B-', 'AB+']),
            'height_cm' => fake()->randomFloat(1, 150, 190),
            'weight_kg' => fake()->randomFloat(1, 45, 95),
            'family_history' => ['diabetes' => false, 'hypertension' => true, 'asthma' => false],
            'past_illnesses' => 'Synthetic sample history for demonstration.',
        ];
    }
}
