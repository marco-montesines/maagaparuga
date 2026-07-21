<x-layout title="Care recipients — MaagapAruga">
    <h1>Care recipients</h1>
    <table>
        <thead>
        <tr><th>Name</th><th>Care context</th><th>Birthdate</th><th></th></tr>
        </thead>
        <tbody>
        @forelse ($recipients as $recipient)
            <tr>
                <td>{{ $recipient->name }}</td>
                <td><span class="badge">{{ $recipient->care_context->value }}</span></td>
                <td>{{ $recipient->birthdate?->format('Y-m-d') }}</td>
                <td><a href="{{ route('care-recipients.show', $recipient) }}">Open record</a></td>
            </tr>
        @empty
            <tr><td colspan="4" class="muted">No care recipients assigned to you.</td></tr>
        @endforelse
        </tbody>
    </table>
</x-layout>
