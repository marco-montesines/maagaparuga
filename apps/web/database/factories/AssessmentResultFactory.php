<?php

namespace Database\Factories;

use App\Enums\RiskLevel;
use App\Models\AssessmentResult;
use App\Models\CareRecipient;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<AssessmentResult>
 */
class AssessmentResultFactory extends Factory
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
            'score_type' => 'news2',
            'value' => fake()->randomFloat(2, 0, 20),
            'risk_level' => fake()->randomElement(RiskLevel::cases()),
            'source' => 'synthetic-vitals-window',
            'computed_at' => now(),
        ];
    }
}
