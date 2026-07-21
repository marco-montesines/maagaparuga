<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use OpenFGA\Client;

/**
 * One-shot dev/ops helper: creates an OpenFGA store, compiles fga/model.fga
 * (via the official SDK's DSL transformer), writes the authorization model,
 * and prints the env values to configure. Uses evansims/openfga-php directly —
 * the Laravel bridge package requires illuminate ^12 and can't be used on
 * this Laravel major yet; the runtime hot path stays on the thin fail-closed
 * client (App\Services\OpenFga\OpenFgaClient).
 */
class BootstrapOpenFga extends Command
{
    protected $signature = 'fga:bootstrap {--name=maagaparuga}';

    protected $description = 'Create OpenFGA store + authorization model from fga/model.fga';

    public function handle(): int
    {
        $client = new Client(url: (string) config('openfga.url'));

        $store = $client->createStore(name: (string) $this->option('name'))->unwrap();
        $this->info("store created: {$store->getId()}");

        $dsl = file_get_contents(base_path('fga/model.fga'));
        $model = $client->dsl($dsl)->unwrap();

        $response = $client->createAuthorizationModel(
            store: $store->getId(),
            typeDefinitions: $model->getTypeDefinitions(),
        )->unwrap();

        $this->info("authorization model written: {$response->getModel()}");
        $this->newLine();
        $this->line('Set these (dev overlay / .env):');
        $this->line("  OPENFGA_STORE_ID={$store->getId()}");
        $this->line("  OPENFGA_MODEL_ID={$response->getModel()}");
        $this->line('Then run: php artisan fga:sync');

        return self::SUCCESS;
    }
}
