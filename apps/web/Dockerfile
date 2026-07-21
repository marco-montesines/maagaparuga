# syntax=docker/dockerfile:1
# MaagapAruga web app — Laravel + Octane on FrankenPHP (ADR 0004).
#
# Two build targets:
#   standard        (default) stock FrankenPHP — maagap_fingerprint() falls
#                   back to PHP's hash('xxh128'), everything else identical
#   with-extension  FrankenPHP recompiled with the Go-native maagap extension
#                   (the PHP-functions-in-Go showcase, hibp convention):
#                   docker build --target with-extension ...
#
# Two server modes at runtime (see docker/entrypoint.sh):
#   SERVER_MODE=octane   (default) worker mode via Octane, workers recycled
#                        every 500 requests (worker-mode discipline)
#   SERVER_MODE=classic  plain per-request FrankenPHP — the adopt-when-ready
#                        fallback with zero worker-state concerns

FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --no-scripts --prefer-dist --no-progress

# --- optional: FrankenPHP with the Go-native maagap extension compiled in ---
FROM dunglas/frankenphp:1.12.6-builder-php8.4 AS extension-builder
COPY --from=caddy:builder /usr/bin/xcaddy /usr/bin/xcaddy
WORKDIR /src
COPY frankenphp-ext ./frankenphp-ext
ENV CGO_ENABLED=1 \
    XCADDY_SETCAP=1 \
    XCADDY_GO_BUILD_FLAGS="-ldflags='-w -s' -tags=nobadger,nomysql,nopgx"
RUN CGO_CFLAGS="$(php-config --includes)" \
    CGO_LDFLAGS="$(php-config --ldflags) $(php-config --libs)" \
    xcaddy build \
      --output /usr/local/bin/frankenphp \
      --with github.com/dunglas/frankenphp/caddy \
      --with github.com/marco-montesines/maagaparuga/apps/web/frankenphp-ext/extension=./frankenphp-ext/extension

# --- application image (default target) ---
FROM dunglas/frankenphp:1.12.6-php8.4 AS standard
RUN install-php-extensions pdo_pgsql pcntl opcache intl zip
WORKDIR /app
COPY --from=vendor /app/vendor ./vendor
COPY . .
RUN php artisan package:discover --ansi \
    && mkdir -p storage/framework/cache storage/framework/sessions storage/framework/views \
    && chown -R www-data:www-data storage bootstrap/cache
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENV SERVER_MODE=octane \
    OCTANE_MAX_REQUESTS=500
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# --- application image with the Go extension baked in ---
FROM standard AS with-extension
COPY --from=extension-builder /usr/local/bin/frankenphp /usr/local/bin/frankenphp
