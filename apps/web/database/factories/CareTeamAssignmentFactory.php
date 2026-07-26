<?php

namespace Database\Factories;

use App\Enums\Role;
use App\Models\CareRecipient;
use App\Models\CareTeamAssignment;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<CareTeamAssignment>
 */
class CareTeamAssignmentFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'user_id' => User::factory(),
            'care_recipient_id' => CareRecipient::factory(),
            'role_at_assignment' => Role::Nurse->value,
            'active' => true,
        ];
    }
}
