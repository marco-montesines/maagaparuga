# Roadmap

Where MaagapAruga is headed **beyond its initial build**. The platform's current
state is summarised in the [README](README.md#status); this document is the
forward vision — research and feature directions, explored on **synthetic data
only**, as demonstrations of technique.

Nothing here is a medical device or a clinical tool. Anything that would touch
real health data or take a real-world action stays out of scope — MDR + GDPR
govern what could ever leave the research/mock stage (see
[DISCLAIMER.md](DISCLAIMER.md)). Everything below is aspirational and unscheduled.

## Machine learning — a deliberate ladder

An ML progression where each rung is taken only when the simpler, more explainable
method below it demonstrably falls short:

1. **Classical ML on engineered features** (scikit-learn) — e.g. anomaly and
   artifact detection on vitals streams; easy to validate, explain, and test.
2. **Signal processing** — if the device mockup ever emits waveforms (ECG/PPG)
   rather than discrete samples: SciPy / NeuroKit2 for physiological features.
3. **Deep learning, only when patient-level results justify it** — PyTorch, exported
   to ONNX for framework-independent deployment on modest hardware.
4. **Transcript topic modelling** over care-note transcriptions (LDA / BERTopic).
5. **Privacy-preserving multi-site learning** — federated learning + PATE +
   **differential privacy**: learn across sites *without ever pooling raw records*,
   with a measurable privacy guarantee (a spent privacy budget). The most advanced,
   aspirational rung — research-only, and only if a real ethics-approved multi-site
   study ever existed.

> Validation would outrank novelty: any learned model needs patient-level (ideally
> site-level) train/test separation, explicit missing-data handling, calibrated
> thresholds, false-alarm/missed-event analysis, and fail-safe human review.

## Multi-modal stress & emotion sensing

Fuse pretrained, per-modality models rather than training one monolith — a shape that
maps cleanly onto a microservice architecture:

- **Physiological** — heart-rate-variability features from a vitals stream.
- **Vocal** — acoustic strain features over consultation audio.
- **Facial expression** — over teleconsultation frames; the most privacy-sensitive
  modality, and mock-media-only if ever built.

MDR caution throughout: results surface to a **human-review inbox**, never an automated
intervention. Third-party model and dataset licences are checked before any use.

## Devices & ingest

A rich **IoMT device-fleet mockup**: distinct device personalities (BP monitor, pulse
oximeter, thermometer, imaging), an **MQTT** ingest path (real fleets speak MQTT),
fleet-scale load and burst profiles, and scripted scenarios that drive alert storylines
end to end — vitals degrade, a score rises, an alert fires, it lands in the inbox.

## Platform & edge

- **CDN + WAF at the edge** — edge TLS, DDoS/WAF, asset caching, and bot mitigation in
  front of the gateway, with the origin locked so the cluster is never hit directly.
- **AI gateway** — should the platform ever front an LLM (e.g. retrieval over care
  notes), route it through an AI-proxy pattern for provider abstraction, cost/token
  limits, retries, and observability. Any LLM output is decision *support* for human
  review, never automated clinical action.
- **Multi-cloud, decoupled placement** — core infrastructure, the GPU/ML tier, and
  off-provider backups each an independent, IaC-driven provider choice.

## Product

- **Payments**, where a flow ever warrants one (e.g. consultation booking) —
  **sandbox/test-mode only, never real money**, via a payment provider in test mode so
  card data never touches the platform.
