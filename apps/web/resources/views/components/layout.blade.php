<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ $title ?? 'MaagapAruga' }}</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 64rem; padding: 0 1rem; color: #1a202c; }
        header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #e2e8f0; padding-bottom: .75rem; margin-bottom: 1.5rem; }
        nav a { margin-right: 1rem; }
        .muted { color: #718096; font-size: .9rem; }
        table { border-collapse: collapse; width: 100%; }
        th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid #edf2f7; }
        .badge { display: inline-block; padding: .1rem .5rem; border-radius: 999px; font-size: .8rem; background: #edf2f7; }
        .badge.high, .badge.extremely_high { background: #fed7d7; }
        .badge.moderate { background: #feebc8; }
        .status { background: #c6f6d5; padding: .4rem .75rem; border-radius: 6px; margin-bottom: 1rem; display: inline-block; }
        footer { margin-top: 3rem; border-top: 1px solid #e2e8f0; padding-top: .75rem; }
    </style>
</head>
<body>
<header>
    <div>
        <strong>MaagapAruga</strong>
        <nav style="display:inline; margin-left:1rem">
            <a href="{{ route('dashboard') }}">Dashboard</a>
            <a href="{{ route('care-recipients.index') }}">Care recipients</a>
            <a href="{{ route('alerts.index') }}">Alerts</a>
        </nav>
    </div>
    <div>
        <span class="muted">{{ auth()->user()?->name }} · {{ auth()->user()?->role->value }}</span>
        @auth
            <form method="POST" action="{{ route('logout') }}" style="display:inline">
                @csrf
                <button type="submit">Sign out</button>
            </form>
        @endauth
    </div>
</header>

@if (session('status'))
    <div class="status">{{ session('status') }}</div>
@endif

{{ $slot }}

<footer class="muted">Research/educational platform — all data is fictitious mock data.</footer>
</body>
</html>
