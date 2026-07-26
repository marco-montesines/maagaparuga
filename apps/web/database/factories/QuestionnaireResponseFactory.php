<?php

namespace Database\Factories;

use App\Models\CareRecipient;
use App\Models\QuestionnaireResponse;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<QuestionnaireResponse>
 */
class QuestionnaireResponseFactory extends Factory
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
            'instrument' => 'dass21',
            'answers' => collect(range(1, 21))
                ->mapWithKeys(fn (int $q): array => ["q$q" => fake()->numberBetween(0, 3)])
                ->all(),
            'submitted_at' => now(),
        ];
    }
}
