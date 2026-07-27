<x-layout :title="$recipient->name.' — MaagapAruga'">
    <h1>{{ $recipient->name }}
        <span class="badge">{{ $recipient->care_context->value }}</span>
    </h1>
    <p class="muted">
        Born {{ $recipient->birthdate?->format('Y-m-d') }} ·
        Emergency contact: {{ $recipient->emergency_contact_name }}
        ({{ $recipient->emergency_contact_relationship }}, {{ $recipient->emergency_contact_phone }})
    </p>

    @if ($recipient->medicalInfo)
        <h2>General medical info</h2>
        <table>
            <tr><th>Blood type</th><td>{{ $recipient->medicalInfo->blood_type }}</td>
                <th>Height</th><td>{{ $recipient->medicalInfo->height_cm }} cm</td>
                <th>Weight</th><td>{{ $recipient->medicalInfo->weight_kg }} kg</td></tr>
            <tr><th>Allergies</th><td colspan="5">{{ $recipient->medicalInfo->allergies ?? '—' }}</td></tr>
            <tr><th>Last visit</th><td colspan="5">{{ $recipient->medicalInfo->last_visit_at?->format('Y-m-d') }}</td></tr>
        </table>
    @endif

    <h2>Latest assessments</h2>
    <table>
        <thead><tr><th>Score</th><th>Value</th><th>Risk</th><th>Computed</th></tr></thead>
        <tbody>
        @forelse ($recipient->assessmentResults->take(5) as $result)
            <tr>
                <td>{{ $result->score_type }}</td>
                <td>{{ $result->value }}</td>
                <td><span class="badge {{ $result->risk_level?->value }}">{{ $result->risk_level?->value ?? '—' }}</span></td>
                <td class="muted">{{ $result->computed_at->diffForHumans() }}</td>
            </tr>
        @empty
            <tr><td colspan="4" class="muted">No assessments yet.</td></tr>
        @endforelse
        </tbody>
    </table>

    <h2>Consultations</h2>
    @forelse ($recipient->consultations as $consultation)
        <article style="border:1px solid #e2e8f0; border-radius:8px; padding:1rem; margin-bottom:1rem">
            <p><strong>{{ $consultation->consulted_at->format('Y-m-d H:i') }}</strong>
                · {{ $consultation->staff->name }}
                <span class="muted">
                    pulse {{ $consultation->pulse_bpm }} bpm ·
                    {{ $consultation->temperature_c }} °C ·
                    BP {{ $consultation->bp_systolic }}/{{ $consultation->bp_diastolic }}
                    (MAP {{ $consultation->mean_arterial_pressure }})
                </span>
            </p>
            <p><em>Complaint:</em> {{ $consultation->chief_complaint }}</p>
            @if ($mayWriteDiagnosis || $consultation->diagnosis)
                <p><em>Diagnosis:</em> {{ $consultation->diagnosis ?? '—' }}</p>
                <p><em>Treatment:</em> {{ $consultation->treatment ?? '—' }}</p>
            @endif
            @if ($consultation->attachments->isNotEmpty())
                <p><em>Attachments:</em>
                    @foreach ($consultation->attachments as $attachment)
                        <span class="badge">{{ $attachment->kind->value }}: {{ $attachment->caption ?? $attachment->object_key }}</span>
                    @endforeach
                </p>
            @endif
            @foreach ($consultation->transcriptions as $transcription)
                <details>
                    <summary>Transcription by {{ $transcription->author->name }}</summary>
                    <p>{{ $transcription->body }}</p>
                </details>
            @endforeach
        </article>
    @empty
        <p class="muted">No consultations recorded.</p>
    @endforelse
</x-layout>
