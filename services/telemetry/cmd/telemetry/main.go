// Command telemetry is the vitals/biotelemetry service. One binary, three
// roles (ADR 0014 — separately deployable, independently scalable):
//
//	serve     gRPC ingest + windowed read API
//	write     JetStream consumer -> batched ClickHouse inserts
//	simulate  mock IoMT device fleet streaming into the ingest API
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthv1 "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/reflection"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
	"maagaparuga/services/telemetry/internal/auth"
	"maagaparuga/services/telemetry/internal/authz"
	"maagaparuga/services/telemetry/internal/broker"
	"maagaparuga/services/telemetry/internal/devauth"
	"maagaparuga/services/telemetry/internal/server"
	"maagaparuga/services/telemetry/internal/simulator"
	"maagaparuga/services/telemetry/internal/store"
	"maagaparuga/services/telemetry/internal/vitals"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var err error

	switch os.Args[1] {
	case "serve":
		err = runServe(ctx, log, os.Args[2:])
	case "write":
		err = runWrite(ctx, log, os.Args[2:])
	case "simulate":
		err = runSimulate(ctx, log, os.Args[2:])
	default:
		usage()
		os.Exit(2)
	}

	if err != nil {
		log.Error("exiting with error", "error", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: telemetry <serve|write|simulate> [flags]")
}

func runServe(ctx context.Context, log *slog.Logger, args []string) error {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	addr := fs.String("addr", env("TELEMETRY_ADDR", ":9090"), "gRPC listen address")
	natsURL := fs.String("nats", env("NATS_URL", "nats://nats:4222"), "NATS URL")
	chAddr := fs.String("clickhouse", env("CLICKHOUSE_ADDR", "clickhouse:9000"), "ClickHouse address")
	chDB := fs.String("clickhouse-db", env("CLICKHOUSE_DB", "maagaparuga"), "ClickHouse database")
	chUser := fs.String("clickhouse-user", env("CLICKHOUSE_USER", "maagaparuga"), "ClickHouse user")
	chPass := fs.String("clickhouse-password", env("CLICKHOUSE_PASSWORD", ""), "ClickHouse password")
	issuer := fs.String("oidc-issuer", env("OIDC_ISSUER", ""), "ZITADEL issuer URL; device tokens are verified against its JWKS")
	audience := fs.String("oidc-audience", env("OIDC_AUDIENCE", "telemetry"), "expected token audience")
	authMode := fs.String("auth", env("AUTH_MODE", "jwt"), "jwt (verify device tokens) or disabled")
	fgaURL := fs.String("openfga-url", env("OPENFGA_URL", "http://openfga:8080"), "OpenFGA base URL")
	fgaStore := fs.String("openfga-store", env("OPENFGA_STORE_ID", ""), "OpenFGA store id")
	fgaModel := fs.String("openfga-model", env("OPENFGA_MODEL_ID", ""), "OpenFGA authorization model id")
	_ = fs.Parse(args)

	bkr, err := broker.Connect(ctx, *natsURL)
	if err != nil {
		return err
	}
	defer bkr.Close()

	st, err := store.Open(ctx, store.Config{
		Addr: *chAddr, Database: *chDB, Username: *chUser, Password: *chPass,
	})
	if err != nil {
		return err
	}
	defer st.Close()

	serverOpts, err := authOptions(ctx, log, *authMode, *issuer, *audience)
	if err != nil {
		return err
	}

	checker, err := authzChecker(log, *authMode, *fgaURL, *fgaStore, *fgaModel)
	if err != nil {
		return err
	}

	listener, err := net.Listen("tcp", *addr)
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}

	grpcServer := grpc.NewServer(serverOpts...)
	telemetryv1.RegisterVitalsServiceServer(grpcServer, server.New(bkr, st, checker, log))

	healthServer := health.NewServer()
	healthv1.RegisterHealthServer(grpcServer, healthServer)
	reflection.Register(grpcServer) // lets grpcurl and the gateway introspect

	go func() {
		<-ctx.Done()
		grpcServer.GracefulStop()
	}()

	log.Info("telemetry serving", "addr", *addr, "auth", *authMode)

	return grpcServer.Serve(listener)
}

// authOptions builds the server's authentication middleware.
//
// "jwt" is the only mode that authenticates devices; "disabled" exists for
// local work before an identity provider is configured and says so loudly,
// because an unauthenticated ingest endpoint is exactly the anti-pattern this
// platform was built to avoid.
func authOptions(
	ctx context.Context,
	log *slog.Logger,
	mode, issuer, audience string,
) ([]grpc.ServerOption, error) {
	switch mode {
	case "disabled":
		log.Warn("DEVICE AUTHENTICATION DISABLED — every caller may write vitals; " +
			"set AUTH_MODE=jwt with OIDC_ISSUER for anything but local development")

		return nil, nil

	case "jwt":
		if issuer == "" {
			return nil, errors.New("auth=jwt requires OIDC_ISSUER (or -auth=disabled for local work)")
		}

		verifier, err := auth.NewVerifier(ctx, issuer, audience)
		if err != nil {
			return nil, err
		}

		interceptors := &auth.Interceptors{
			Verifier: verifier,
			Log:      log,
			// Probes carry no credentials.
			Public: map[string]bool{
				"/grpc.health.v1.Health/Check": true,
				"/grpc.health.v1.Health/Watch": true,
			},
		}

		return []grpc.ServerOption{
			grpc.UnaryInterceptor(interceptors.Unary()),
			grpc.StreamInterceptor(interceptors.Stream()),
		}, nil

	default:
		return nil, fmt.Errorf("unknown auth mode %q (want jwt or disabled)", mode)
	}
}

// authzChecker builds the per-object authorization checker. It is bound to the
// auth mode: with authentication on there is a caller identity to authorize,
// so an OpenFGA store MUST be configured; with authentication disabled there
// is no identity, so authorization is disabled too (nil) — the same loud
// local-only posture as auth.
func authzChecker(
	log *slog.Logger,
	authMode, url, storeID, modelID string,
) (authz.Checker, error) {
	if authMode == "disabled" {
		log.Warn("OBJECT AUTHORIZATION DISABLED — callers are not checked against " +
			"care-recipient relationships (follows AUTH_MODE=disabled; local only)")

		return nil, nil
	}

	if storeID == "" {
		return nil, errors.New("auth=jwt requires OPENFGA_STORE_ID so callers can be " +
			"authorized per care recipient (or -auth=disabled for local work)")
	}

	return authz.New(authz.Config{URL: url, StoreID: storeID, ModelID: modelID})
}

func runWrite(ctx context.Context, log *slog.Logger, args []string) error {
	fs := flag.NewFlagSet("write", flag.ExitOnError)
	natsURL := fs.String("nats", env("NATS_URL", "nats://nats:4222"), "NATS URL")
	chAddr := fs.String("clickhouse", env("CLICKHOUSE_ADDR", "clickhouse:9000"), "ClickHouse address")
	chDB := fs.String("clickhouse-db", env("CLICKHOUSE_DB", "maagaparuga"), "ClickHouse database")
	chUser := fs.String("clickhouse-user", env("CLICKHOUSE_USER", "maagaparuga"), "ClickHouse user")
	chPass := fs.String("clickhouse-password", env("CLICKHOUSE_PASSWORD", ""), "ClickHouse password")
	batchSize := fs.Int("batch", 500, "max samples per ClickHouse insert")
	maxWait := fs.Duration("max-wait", 2*time.Second, "idle wait between empty fetches")
	healthAddr := fs.String("health-addr", env("HEALTH_ADDR", ":9091"), "health endpoint (liveness) address")
	_ = fs.Parse(args)

	// The writer has no service port, so give Kubernetes a health signal:
	// a wedged consumer that stops draining the queue but keeps running is a
	// real failure the liveness probe must catch.
	serveHealth(ctx, log, *healthAddr)

	bkr, err := broker.Connect(ctx, *natsURL)
	if err != nil {
		return err
	}
	defer bkr.Close()

	st, err := store.Open(ctx, store.Config{
		Addr: *chAddr, Database: *chDB, Username: *chUser, Password: *chPass,
	})
	if err != nil {
		return err
	}
	defer st.Close()

	if err := st.Migrate(ctx); err != nil {
		return err
	}

	log.Info("telemetry writer consuming", "batch", *batchSize)

	return bkr.Consume(ctx, *batchSize, *maxWait,
		func(ctx context.Context, batch []*telemetryv1.VitalsSample) error {
			// Defence in depth: the ingest API validates, but this consumer
			// must not assume it is the only publisher to the stream. An
			// implausible value dropped here is a logged anomaly; the same
			// value written to the store would become a clinical number
			// somebody later reads as real.
			accepted := batch[:0]

			for _, sample := range batch {
				if err := vitals.Validate(sample, time.Now()); err != nil {
					log.WarnContext(ctx, "dropped invalid sample from stream",
						"device_id", sample.GetDeviceId(), "error", err)

					continue
				}

				accepted = append(accepted, sample)
			}

			if len(accepted) == 0 {
				return nil
			}

			if err := st.InsertBatch(ctx, accepted); err != nil {
				return err
			}

			log.Info("batch written", "samples", len(accepted), "dropped", len(batch)-len(accepted))

			return nil
		})
}

func runSimulate(ctx context.Context, log *slog.Logger, args []string) error {
	fs := flag.NewFlagSet("simulate", flag.ExitOnError)
	target := fs.String("target", env("TELEMETRY_TARGET", "telemetry:9090"), "telemetry gRPC address")
	recipients := fs.String("recipients", "1,2,3,4", "comma-separated care recipient ids")
	perRecipient := fs.Int("devices", 2, "devices per care recipient")
	interval := fs.Duration("interval", 2*time.Second, "sampling interval")
	total := fs.Int("total", 0, "stop after N samples (0 = run until interrupted)")
	burst := fs.Bool("burst", false, "burst mode: sample as fast as possible to demonstrate broker buffering")
	seed := fs.Uint64("seed", 42, "deterministic seed")
	// Device onboarding: how the mock device obtains its bearer token. The
	// telemetry service verifies the resulting JWT identically whichever path
	// produced it (see internal/devauth).
	authMethod := fs.String("auth-method", env("DEVICE_AUTH_METHOD", "client_credentials"),
		"client_credentials (M2M, default), jwt_profile (machine key), or static (use -token)")
	issuer := fs.String("oidc-issuer", env("OIDC_ISSUER", ""), "ZITADEL issuer for minting a device token")
	clientID := fs.String("client-id", env("DEVICE_CLIENT_ID", ""), "device client id (client_credentials)")
	clientSecret := fs.String("client-secret", env("DEVICE_CLIENT_SECRET", ""), "device client secret (client_credentials)")
	projectID := fs.String("audience", env("OIDC_AUDIENCE", ""), "project id used as the token audience")
	keyPath := fs.String("key", env("DEVICE_KEY_PATH", ""), "device machine-key file (jwt_profile)")
	token := fs.String("token", env("DEVICE_TOKEN", ""), "pre-minted bearer token (PAT or any token); overrides -auth-method")
	_ = fs.Parse(args)

	if *burst {
		*interval = time.Millisecond
	}

	// Obtain the device credential BEFORE dialing, so an auth misconfiguration
	// fails fast with a clear message instead of a stream error.
	bearer, err := deviceToken(ctx, *authMethod, *issuer, *clientID, *clientSecret, *projectID, *keyPath, *token)
	if err != nil {
		return fmt.Errorf("obtain device token: %w", err)
	}

	conn, err := grpc.NewClient(*target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return fmt.Errorf("dial telemetry: %w", err)
	}
	defer conn.Close()

	// Devices authenticate with a bearer token the same way any client does.
	if bearer != "" {
		ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+bearer)
		log.Info("device authenticated", "method", *authMethod)
	} else {
		log.Warn("no device credentials configured — streaming without a token " +
			"(succeeds only if the telemetry service runs with AUTH_MODE=disabled)")
	}

	stream, err := telemetryv1.NewVitalsServiceClient(conn).StreamVitals(ctx)
	if err != nil {
		return fmt.Errorf("open stream: %w", err)
	}

	fleet := simulator.NewFleet(strings.Split(*recipients, ","), *perRecipient, *seed)

	log.Info("simulating fleet",
		"devices", len(fleet.Devices), "interval", *interval, "burst", *burst)

	err = fleet.Run(ctx, *interval, *total, func(sample *telemetryv1.VitalsSample) error {
		return stream.Send(&telemetryv1.StreamVitalsRequest{Sample: sample})
	})
	// Send returns io.EOF when the server has closed the stream; the real
	// status (e.g. Unauthenticated) is only available from CloseAndRecv. So a
	// non-EOF Send error is a local/transport failure, but on EOF we must fall
	// through to CloseAndRecv rather than report a bare "EOF".
	if err != nil && !errors.Is(err, io.EOF) {
		return fmt.Errorf("send: %w", err)
	}

	// A cancelled context is a clean stop, not a stream error.
	if ctx.Err() != nil {
		log.Info("simulation stopped")

		return nil
	}

	reply, err := stream.CloseAndRecv()
	if err != nil {
		return fmt.Errorf("stream closed by server: %w", err)
	}

	log.Info("simulation finished", "accepted", reply.GetAccepted(), "rejected", reply.GetRejected())

	return nil
}

// deviceToken resolves the bearer token a simulated device presents, per the
// selected onboarding method. An explicit -token wins (a PAT or any pre-minted
// token). Otherwise the method-specific source mints one. When nothing is
// configured it returns "" so the simulator can still run tokenless against a
// telemetry service in AUTH_MODE=disabled.
func deviceToken(
	ctx context.Context,
	method, issuer, clientID, clientSecret, projectID, keyPath, staticToken string,
) (string, error) {
	if staticToken != "" {
		return devauth.Static{Value: staticToken}.Token(ctx)
	}

	switch method {
	case "", "client_credentials":
		// Nothing configured: run tokenless (auth-disabled local mode).
		if issuer == "" && clientID == "" && clientSecret == "" {
			return "", nil
		}

		return devauth.ClientCredentials{
			Issuer: issuer, ClientID: clientID, ClientSecret: clientSecret, ProjectID: projectID,
		}.Token(ctx)

	case "jwt_profile":
		return devauth.JWTProfile{Issuer: issuer, KeyPath: keyPath, ProjectID: projectID}.Token(ctx)

	case "static":
		return "", errors.New("auth-method=static requires -token (a PAT or pre-minted token)")

	default:
		return "", fmt.Errorf("unknown auth-method %q (want client_credentials, jwt_profile or static)", method)
	}
}

// serveHealth runs a tiny HTTP server exposing /healthz for the liveness probe
// of port-less roles (the writer). It reports OK while the process is alive;
// the process exits (and is restarted) on any fatal error in the main loop, so
// "answering" is a sufficient liveness signal here. Shuts down with ctx.
func serveHealth(ctx context.Context, log *slog.Logger, addr string) {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	srv := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()

	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("health server stopped", "error", err)
		}
	}()
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}

	return fallback
}
