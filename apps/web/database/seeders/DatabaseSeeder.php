<?php

namespace Database\Seeders;

use App\Enums\CareContext;
use App\Enums\RiskLevel;
use App\Enums\Role;
use App\Models\Alert;
use App\Models\AssessmentResult;
use App\Models\CareRecipient;
use App\Models\CareTeamAssignment;
use App\Models\Consultation;
use App\Models\GeneralMedicalInfo;
use App\Models\QuestionnaireResponse;
use App\Models\Transcription;
use App\Models\User;
use Illuminate\Database\Seeder;

/**
 * Fictitious personas per data/mock/README.md: "Demo" marker middle names,
 * example.com emails, reserved fictional phone ranges, invented
 * non-resolvable addresses. NEVER replace with real personal or health data.
 */
class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        $staff = $this->seedStaff();
        $recipients = $this->seedRecipients();
        $this->assign($staff, $recipients);
        $this->seedClinicalContent($staff, $recipients);
    }

    /** @return array<string, User> */
    private function seedStaff(): array
    {
        $mk = fn (string $name, string $email, Role $role, array $extra = []) => User::updateOrCreate(
            ['email' => $email],
            array_merge(['name' => $name, 'role' => $role->value], $extra),
        );

        return [
            'admin' => $mk('Amara Demo Santos', 'admin@example.com', Role::Administrator),
            'doctor1' => $mk('Dr. Liwayway Demo Reyes', 'l.reyes@example.com', Role::Doctor, [
                'specialization' => 'internal_medicine', 'license_id' => 'DEMO-MD-0001',
                'affiliation' => 'Demo Community Clinic', 'phone' => '+63 2 8555 0101',
            ]),
            'doctor2' => $mk('Dr. Bayani Demo Cruz', 'b.cruz@example.com', Role::Doctor, [
                'specialization' => 'geriatrics', 'license_id' => 'DEMO-MD-0002',
                'affiliation' => 'Demo Community Clinic', 'phone' => '+63 2 8555 0102',
            ]),
            'nurse' => $mk('Nurse Ligaya Demo Bautista', 'l.bautista@example.com', Role::Nurse, [
                'affiliation' => 'Demo Community Clinic', 'phone' => '+63 2 8555 0103',
            ]),
            'transcriptionist' => $mk('Katala Demo Villanueva', 'k.villanueva@example.com', Role::Transcriptionist),
            'provider1' => $mk('Tala Demo Ocampo', 't.ocampo@example.com', Role::CareProvider, [
                'phone' => '+63 2 8555 0104',
            ]),
            'provider2' => $mk('Diwa Demo Salazar', 'd.salazar@example.com', Role::CareProvider, [
                'phone' => '+63 2 8555 0105',
            ]),
        ];
    }

    /** @return array<int, CareRecipient> */
    private function seedRecipients(): array
    {
        $rows = [
            ['Lola Demo Magbanua', '1946-03-14', CareContext::Elderly],
            ['Ambrosio Demo Dela Vega', '1958-11-02', CareContext::TerminallyIll],
            ['Marikit Demo Adarna', '1994-06-21', CareContext::Autistic],
            ['Crisanto Demo Lakandula', '1971-01-30', CareContext::Sick],
        ];

        return collect($rows)->map(function (array $row, int $i) {
            $recipient = CareRecipient::updateOrCreate(
                ['name' => $row[0]],
                [
                    'birthdate' => $row[1],
                    'care_context' => $row[2]->value,
                    'phone' => '+63 2 8555 02'.str_pad((string) $i, 2, '0', STR_PAD_LEFT),
                    'address' => ($i + 1).' Demo Street, Barangay Halimbawa, Lungsod ng Kathang-isip',
                    'emergency_contact_name' => 'Kaanak Demo Halimbawa',
                    'emergency_contact_relationship' => 'child',
                    'emergency_contact_phone' => '+63 2 8555 0999',
                    'insurance_provider' => 'Demo Health Insurance Co.',
                    'insurance_number' => 'DEMO-INS-'.str_pad((string) ($i + 1), 4, '0', STR_PAD_LEFT),
                ],
            );

            GeneralMedicalInfo::updateOrCreate(
                ['care_recipient_id' => $recipient->id],
                [
                    'blood_type' => ['A+', 'O+', 'B-', 'AB+'][$i],
                    'height_cm' => 150 + $i * 5,
                    'weight_kg' => 52 + $i * 6,
                    'allergies' => $i % 2 === 0 ? 'penicillin (synthetic sample)' : null,
                    'family_history' => ['diabetes' => $i % 2 === 0, 'hypertension' => true, 'asthma' => false],
                    'past_illnesses' => 'Synthetic sample history for demonstration.',
                    'last_visit_at' => now()->subDays(7 + $i * 3),
                ],
            );

            return $recipient;
        })->all();
    }

    /**
     * @param  array<string, User>  $staff
     * @param  array<int, CareRecipient>  $recipients
     */
    private function assign(array $staff, array $recipients): void
    {
        $pairs = [
            ['doctor1', 0], ['doctor1', 1], ['doctor2', 2], ['doctor2', 3],
            ['nurse', 0], ['nurse', 1], ['nurse', 2], ['nurse', 3],
            ['provider1', 0], ['provider1', 1], ['provider2', 2], ['provider2', 3],
            ['transcriptionist', 0], ['transcriptionist', 1],
        ];

        foreach ($pairs as [$who, $idx]) {
            CareTeamAssignment::updateOrCreate(
                ['user_id' => $staff[$who]->id, 'care_recipient_id' => $recipients[$idx]->id],
                ['role_at_assignment' => $staff[$who]->role->value, 'active' => true],
            );
        }
    }

    /**
     * @param  array<string, User>  $staff
     * @param  array<int, CareRecipient>  $recipients
     */
    private function seedClinicalContent(array $staff, array $recipients): void
    {
        foreach ($recipients as $i => $recipient) {
            $consultation = Consultation::updateOrCreate(
                ['care_recipient_id' => $recipient->id, 'staff_user_id' => $staff['doctor1']->id],
                [
                    'consulted_at' => now()->subDays(5 + $i),
                    'pulse_bpm' => 68 + $i * 4,
                    'temperature_c' => 36.5,
                    'bp_systolic' => 118 + $i * 3,
                    'bp_diastolic' => 76 + $i * 2,
                    'chief_complaint' => 'Synthetic sample complaint for demonstration.',
                    'diagnosis' => 'Synthetic sample diagnosis — fictitious.',
                    'treatment' => 'Synthetic sample treatment plan.',
                    'prescription' => 'Synthetic sample prescription.',
                ],
            );

            Transcription::updateOrCreate(
                ['consultation_id' => $consultation->id, 'author_user_id' => $staff['transcriptionist']->id],
                ['body' => '[synthetic transcript] Consultation notes for demonstration purposes only.'],
            );

            QuestionnaireResponse::updateOrCreate(
                ['care_recipient_id' => $recipient->id, 'instrument' => 'dass21'],
                [
                    'answers' => collect(range(1, 21))->mapWithKeys(fn ($q) => ["q$q" => ($q + $i) % 4])->all(),
                    'submitted_at' => now()->subDays(2),
                ],
            );

            $result = AssessmentResult::updateOrCreate(
                ['care_recipient_id' => $recipient->id, 'score_type' => 'news2'],
                [
                    'value' => [2, 6, 1, 4][$i],
                    'risk_level' => [RiskLevel::Low, RiskLevel::High, RiskLevel::VeryLow, RiskLevel::Moderate][$i]->value,
                    'source' => 'synthetic-vitals-window',
                    'computed_at' => now()->subHours(3),
                ],
            );

            $risk = $result->risk_level;
            if ($risk?->triggersAlert()) {
                Alert::updateOrCreate(
                    ['care_recipient_id' => $recipient->id, 'assessment_result_id' => $result->id],
                    [
                        'severity' => $risk->value,
                        'title' => 'Early-warning score above threshold',
                        'body' => 'Synthetic alert generated from mock data — review the vitals window.',
                    ],
                );
            }
        }
    }
}
