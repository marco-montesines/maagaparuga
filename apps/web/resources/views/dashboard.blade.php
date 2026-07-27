<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MaagapAruga — Dashboard</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; color: #1a202c; }
        header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #e2e8f0; padding-bottom: .75rem; }
        .muted { color: #718096; font-size: .9rem; }
        code { background: #f7fafc; padding: .1rem .3rem; border-radius: 4px; }
    </style>
</head>
<body>
<header>
    <h1>MaagapAruga</h1>
    <div>
        <span class="muted">{{ auth()->user()->name }} · {{ auth()->user()->role->value }}</span>
        <form method="POST" action="{{ route('logout') }}" style="display:inline">
            @csrf
            <button type="submit">Sign out</button>
        </form>
    </div>
</header>

<p>Signed in via ZITADEL. The dashboard UI consumes the GraphQL BFF at
    <code>POST /graphql</code> — try the <code>dashboard(careRecipientId: …)</code> query.</p>

<p class="muted">Research/educational platform — all data is fictitious mock data.</p>
</body>
</html>
