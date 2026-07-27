<?php

namespace Database\Factories;

use App\Enums\AttachmentKind;
use App\Models\Consultation;
use App\Models\ConsultationAttachment;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<ConsultationAttachment>
 */
class ConsultationAttachmentFactory extends Factory
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
            'kind' => fake()->randomElement(AttachmentKind::cases()),
            'object_key' => 'demo/'.fake()->uuid(),
            'caption' => 'Synthetic attachment for demonstration.',
        ];
    }
}
