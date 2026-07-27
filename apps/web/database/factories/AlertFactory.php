<?php

namespace Database\Factories;

use App\Enums\RiskLevel;
use App\Models\Alert;
use App\Models\AssessmentResult;
use App\Models\CareRecipient;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Alert>
 */
class AlertFactory extends Factory
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
            'assessment_result_id' => AssessmentResult::factory(),
            'severity' => fake()->randomElement(RiskLevel::cases()),
            'title' => 'Early-warning score above threshold',
            'body' => 'Synthetic alert generated from mock data for demonstration.',
        ];
    }
}
