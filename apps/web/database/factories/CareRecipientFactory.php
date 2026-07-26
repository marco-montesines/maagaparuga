<?php

namespace Database\Factories;

use App\Enums\CareContext;
use App\Models\CareRecipient;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<CareRecipient>
 */
class CareRecipientFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'user_id' => null,
            'name' => fake()->firstName().' Demo '.fake()->lastName(),
            'birthdate' => fake()->dateTimeBetween('-90 years', '-1 years'),
            'phone' => '+63 2 8555 0000',
            'address' => 'Demo Street, Barangay Halimbawa, Lungsod ng Kathang-isip',
            'care_context' => fake()->randomElement(CareContext::cases()),
        ];
    }
}
