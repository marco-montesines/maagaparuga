<x-layout title="Alerts — MaagapAruga">
    <h1>Alerts inbox</h1>
    <p class="muted">Detect early, assess continuously, refer promptly.</p>
    <table>
        <thead><tr><th>Severity</th><th>Care recipient</th><th>Alert</th><th>Raised</th><th></th></tr></thead>
        <tbody>
        @forelse ($alerts as $alert)
            <tr>
                <td><span class="badge {{ $alert->severity->value }}">{{ $alert->severity->value }}</span></td>
                <td><a href="{{ route('care-recipients.show', $alert->careRecipient) }}">{{ $alert->careRecipient->name }}</a></td>
                <td>{{ $alert->title }}<br><span class="muted">{{ $alert->body }}</span></td>
                <td class="muted">{{ $alert->created_at->diffForHumans() }}</td>
                <td>
                    <form method="POST" action="{{ route('alerts.acknowledge', $alert) }}">
                        @csrf
                        <button type="submit">Acknowledge</button>
                    </form>
                </td>
            </tr>
        @empty
            <tr><td colspan="5" class="muted">No open alerts.</td></tr>
        @endforelse
        </tbody>
    </table>
</x-layout>
