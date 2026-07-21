<?php

namespace App\Providers;

use App\Models\CareRecipient;
use App\Models\CareTeamAssignment;
use App\Models\Transcription;
use App\Observers\CareTeamAssignmentObserver;
use App\Observers\TranscriptionObserver;
use App\Policies\CareRecipientPolicy;
use App\Services\MediaSearch\FakeMediaSearcher;
use App\Services\MediaSearch\MediaSearcher;
use App\Services\OpenFga\OpenFgaClient;
use App\Services\Telemetry\FakeVitalsReader;
use App\Services\Telemetry\VitalsReader;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\ServiceProvider;
use SocialiteProviders\Manager\SocialiteWasCalled;
use SocialiteProviders\Zitadel\ZitadelExtendSocialite;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(OpenFgaClient::class, fn () => OpenFgaClient::fromConfig());

        // Fakes until the real backends land: P3 swaps in the telemetry gRPC
        // client, P4b the OpenSearch hybrid searcher. The GraphQL BFF contract
        // stays identical when they do.
        $this->app->bind(
            VitalsReader::class,
            FakeVitalsReader::class,
        );
        $this->app->bind(
            MediaSearcher::class,
            FakeMediaSearcher::class,
        );
    }

    public function boot(): void
    {
        Event::listen(SocialiteWasCalled::class, ZitadelExtendSocialite::class);

        Gate::policy(CareRecipient::class, CareRecipientPolicy::class);

        CareTeamAssignment::observe(CareTeamAssignmentObserver::class);
        Transcription::observe(TranscriptionObserver::class);
    }
}
