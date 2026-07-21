// Command telemetry is the vitals/biotelemetry service. One binary, three
// roles (ADR 0014 — separately deployable, independently scalable):
//
//	serve     gRPC ingest + windowed read API
//	write     JetStream consumer -> batched ClickHouse inserts
//	simulate  mock IoMT device fleet streaming into the ingest API
package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthv1 "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
	"maagaparuga/services/telemetry/internal/broker"
	"maagaparuga/services/telemetry/internal/server"
	"maagaparuga/services/telemetry/internal/simulator"
	"maagaparuga/services/telemetry/internal/store"
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

	listener, err := net.Listen("tcp", *addr)
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}

	grpcServer := grpc.NewServer()
	telemetryv1.RegisterVitalsServiceServer(grpcServer, server.New(bkr, st, log))

	healthServer := health.NewServer()
	healthv1.RegisterHealthServer(grpcServer, healthServer)
	reflection.Register(grpcServer) // lets grpcurl and the gateway introspect

	go func() {
		<-ctx.Done()
		grpcServer.GracefulStop()
	}()

	log.Info("telemetry serving", "addr", *addr)

	return grpcServer.Serve(listener)
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

	if err := st.Migrate(ctx); err != nil {
		return err
	}

	log.Info("telemetry writer consuming", "batch", *batchSize)

	return bkr.Consume(ctx, *batchSize, *maxWait,
		func(ctx context.Context, batch []*telemetryv1.VitalsSample) error {
			if err := st.InsertBatch(ctx, batch); err != nil {
				return err
			}

			log.Info("batch written", "samples", len(batch))

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
	_ = fs.Parse(args)

	if *burst {
		*interval = time.Millisecond
	}

	conn, err := grpc.NewClient(*target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return fmt.Errorf("dial telemetry: %w", err)
	}
	defer conn.Close()

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
	if err != nil {
		return err
	}

	reply, err := stream.CloseAndRecv()
	if err != nil {
		return fmt.Errorf("close stream: %w", err)
	}

	log.Info("simulation finished", "accepted", reply.GetAccepted(), "rejected", reply.GetRejected())

	return nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}

	return fallback
}
