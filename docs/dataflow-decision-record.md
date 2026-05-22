# Dataflow / Apache Beam Decision Record

**Status:** DECISION RECORD -- Dataflow deferred pending measured justification
**Date:** 2026-05-22
**Branch:** `docs/dataflow-decision-record`
**Author intent:** Rigorous architectural assessment. No sales language. No unsupported claims.

---

## 1. Context

### Current Architecture

The Real-Time Data Platform operates on the following validated path:

```
Pub/Sub topic
  → Cloud Run worker (push subscription)
    → Cloud SQL PostgreSQL (bronze.market_events)

Cloud SQL PostgreSQL
  → dbt incremental models (silver, gold) [scheduled via Cloud Run Job]

Cloud SQL PostgreSQL
  → BigQuery analytical append job (cursor-based MERGE → rtdp_analytics)

BigQuery quality checks
  → Cloud Monitoring custom metrics → alert policies → email notification
```

All components are Terraform-managed with GCS remote state. The Cloud Run worker runs with `maxScale=1` and `concurrency=1`. Pub/Sub is configured with a deadLetterPolicy (`maxDeliveryAttempts=5`) and 10s/60s backoff. Cloud SQL uses `ON CONFLICT(event_id) DO NOTHING` for idempotent writes. BigQuery receives data through a cursor-based incremental append job.

### Current Proven Scale and Evidence

| Metric | Value | Source |
|---|---|---|
| 50,000-event bounded cloud load test | PASSED: 0 publish errors, 0 worker errors, 0 duplicate event_ids | load-test-50000-cloud-evidence.md |
| Sustained 10 events/sec for 30 minutes | PASSED: 18,000 attempted publishes, 18,000 acknowledged, 0 publish errors | steady-state-10eps-30min-cloud-validation-evidence.md |
| 18,000 matched unique worker events | 18,000 of 18,000 (0 missing worker events) | steady-state-10eps-30min-cloud-validation-evidence.md |
| p50 end-to-end latency | 154.385 ms | steady-state-10eps-30min-cloud-validation-evidence.md |
| p95 end-to-end latency | 227.59 ms | steady-state-10eps-30min-cloud-validation-evidence.md |
| p99 end-to-end latency | 693.995 ms | steady-state-10eps-30min-cloud-validation-evidence.md |
| max latency | 960,263.973 ms -- documented as outlier/log-join/delayed-observation caveat | steady-state-10eps-30min-cloud-validation-evidence.md |
| Cloud SQL final state | STOPPED / NEVER (across all validations) | Multiple evidence docs |
| Schedulers final state | PAUSED | Multiple evidence docs |
| Terraform plan exit | PLAN_EXIT=0 | All evidence branches |
| BigQuery rows (analytical tier) | 6,120 rows; cursor-based incremental MERGE proven | bigquery-incremental-append-evidence.md |
| dbt Cloud SQL live execution | PROVEN: dbt run PASS=2; dbt test PASS=22 | dbt-cloud-sql-incremental-execution-proof.md |
| Alerting loop | Quality failure → Cloud Monitoring incident OPEN → email delivery proven | bigquery-quality-incident-notification-delivery-proof.md |

Latency is computed via producer artifact / worker structured log join (Option B instrumentation). No database-persisted latency columns exist. The max outlier is a log-join artifact or delayed observation, not a representative tail latency.

### Why Dataflow Is Being Evaluated Now

The market-value gap audit (`docs/market-value-gap-audit-2026-2027.md`) identified Dataflow / Apache Beam as the highest-priority remaining gap, rated Priority 5 of 5. The absence of Dataflow is a binary disqualifier for streaming-specific roles and a visible architectural gap for senior reviewers.

The recommended response in the gap audit was explicit: **write a decision record before implementing anything**. A well-structured decision record demonstrates the same architectural reasoning a Dataflow implementation would, while avoiding premature GCP cost exposure and the risk of producing shallow Dataflow evidence.

This document is that decision record.

---

## 2. Decision

**Dataflow / Apache Beam implementation is deferred.**

The current Cloud Run worker path (Pub/Sub → Cloud Run → Cloud SQL) remains the primary validated ingestion and processing path for the Real-Time Data Platform. dbt transformation and BigQuery analytical append are separate, independently-scheduled jobs that read from Cloud SQL.

**The next Dataflow step is not implementation. It is measured justification.**

Implementation of Dataflow will be scheduled only when one or more trigger conditions defined in Section 5 of this document are met by measured evidence -- not by assumption, speculation, or role-requirement pressure alone. A minimal Beam proof (`feat/dataflow-minimal-beam-proof`) is the appropriate first implementation step if and when the decision record conditions are satisfied.

**Recommended next branches after this document:**

1. `docs/replay-backfill-strategy` -- closes the operational replay gap, which has higher near-term ROI.
2. `docs/dbt-observability-metrics-plan` -- closes the last significant gap in the analytics engineering story.
3. `feat/dataflow-minimal-beam-proof` -- a minimal, scoped Beam proof, only if a target role or client requires Beam experience before the replay/dbt observability branches are complete, or after those branches conclude.

---

## 3. Why Cloud Run Is Valid Today

### Proven Throughput at Current Scale

The Cloud Run worker path has been validated at two complementary scales:

- **50,000-event bounded load test**: published at the maximum safe rate; all 50,000 events acknowledged, processed, and persisted with zero errors and zero duplicates.
- **10 events/sec for 30 minutes (sustained)**: 18,000 events published and acknowledged; 18,000 matched worker events; p50=154 ms, p95=227 ms, p99=694 ms.

At 10 events/sec (600 events/minute, 36,000 events/hour), the Cloud Run path shows no signs of backpressure, queue growth, or latency degradation. The saturation point has not been characterized, but the current operating rate is well within the demonstrated envelope.

No evidence suggests the current Cloud Run path is approaching a throughput ceiling at the validated operating rate.

### Operational Simplicity

The Cloud Run worker is a standard Python service container, deployed with Terraform, built in CI, and observable through Cloud Monitoring structured logs. There is no cluster to manage, no streaming runner configuration, no Beam SDK dependency, and no Dataflow-specific IAM or networking. Debugging, iteration, and deployment are all simpler than equivalent Dataflow operations.

### Low Cost

The Cloud Run worker scales to zero when idle. During validation windows, cost is bounded by the event count and the Cloud SQL activation window. Cloud SQL is kept at `STOPPED / NEVER` outside controlled runs. This posture is verified across 60+ evidence documents.

By contrast, a Dataflow streaming job bills from the moment it is launched, whether or not events are flowing. Dataflow worker cost is non-trivial for even a minimal streaming proof.

### Fast Iteration

Changes to the worker -- logic, schema handling, error policy, DLQ behavior -- are implemented in Python, tested with pytest (257 tests in the current validation baseline), linted with ruff, and deployed via a manual workflow. The feedback loop from code change to cloud evidence is measured in minutes. A Dataflow pipeline with Beam SDK changes requires a more complex build, runner execution, and job-level evidence collection process.

### Controlled Validation Windows

Because the worker is a Cloud Run service, validation can be performed in a bounded window (start Cloud SQL, publish N events, stop Cloud SQL) with deterministic cleanup. Dataflow streaming jobs require explicit drain or cancel operations, and cleanup is less reliable in a minimal-cost portfolio context.

### Cloud Run maxScale=1 and concurrency=1 as Intentional Design

The Cloud Run worker is configured with `maxScale=1` and `concurrency=1`. This is a deliberate cost and risk control decision, not a limitation to apologize for:

- **Cost control**: a single instance ensures no parallel worker cost accumulation during validation windows.
- **Ordering predictability**: concurrency=1 eliminates intra-instance race conditions for event processing.
- **Portfolio scope**: the platform does not currently require multi-instance concurrency. If it did, that would itself be a trigger condition for Dataflow (see Section 5).

The trade-off is that maxScale=1 limits the maximum burst throughput to a single Cloud Run instance. This is an acceptable trade-off at the current proven scale. If throughput requirements exceed single-instance capacity, that is a trigger condition for Dataflow.

**Cloud Run is not equivalent to Dataflow.** It does not perform windowed aggregations, does not handle late events natively, does not provide exactly-once transport-layer semantics, and does not autoscale streaming workers. These differences are documented explicitly in Section 6.

---

## 4. Why Dataflow Is Not Automatic

### What Dataflow Adds

Apache Beam / Dataflow provides capabilities that the current Cloud Run path does not:

- **Windowed streaming**: `FixedWindows`, `SlidingWindows`, `SessionWindows` over event-time streams. Current windowing is post-hoc in dbt/PostgreSQL (processing-time aggregation, not event-time).
- **Stateful processing**: per-key state and timers for aggregations, joins, or enrichment that require memory across events in a processing window.
- **Late-event handling**: `AllowedLateness` policy allows events that arrive after their window's watermark to be included or routed to side outputs. The current path has no late-event handling.
- **Watermarking**: Beam's watermark model tracks event-time progress. The current path has no watermark concept.
- **Autoscaling streaming workers**: Dataflow scales worker count based on throughput demand. The current Cloud Run path is hard-capped at `maxScale=1`.
- **Stronger BigQuery write guarantees**: Dataflow can support stronger BigQuery streaming write guarantees when using the appropriate Beam BigQuery Storage Write API path (`COMMITTED` mode), but this must be implemented and validated before any exactly-once claim is made. The current path provides at-least-once delivery with application-layer deduplication via `ON CONFLICT`.
- **High-throughput streaming**: Dataflow is designed for sustained high-throughput streaming (hundreds to thousands of events/sec). The current Cloud Run path has not been characterized above 10 events/sec sustained.

### Why These Needs Are Not Yet Proven by Current Evidence

None of the Dataflow-specific capabilities listed above are currently needed based on measured evidence:

- **Windowed streaming**: The current use case is aggregation of market events by minute and by day. This is implemented in dbt as a scheduled batch transformation, which is appropriate for the current data freshness requirement. No evidence shows that event-time windowing is required for the current use case.
- **Stateful processing**: The worker writes individual events to Cloud SQL. No cross-event state is required in the current processing path.
- **Late-event handling**: At 10 events/sec with p95=227 ms latency, late events are not a demonstrated problem. The saturation point has not been characterized; late events under load have not been observed.
- **Autoscaling**: maxScale=1 is sufficient for all validated runs. No evidence shows that single-instance capacity is insufficient.
- **Exactly-once semantics**: The `ON CONFLICT(event_id) DO NOTHING` deduplication at Cloud SQL has produced zero duplicates across 50,000 bounded events and 18,000 sustained events. This is adequate for the current evidence level.
- **High throughput**: 10 events/sec is the maximum sustained rate proven. No business case or performance requirement justifying higher throughput has been identified.

### Dataflow Cost and Complexity Risk

Dataflow adds cost and complexity risk that the current Cloud Run path does not:

- **Cost**: Dataflow worker billing begins on job launch, regardless of event volume. A 30-minute streaming job will incur non-trivial worker cost even for low event rates.
- **Complexity**: Beam SDK, Dataflow runner, pipeline options, runner configuration, worker pool, staging bucket, and Dataflow-specific IAM must all be managed correctly for a job to run.
- **Implementation risk**: A minimal Dataflow proof with insufficient evidence depth will weaken the portfolio rather than strengthen it. A shallow Dataflow pipeline that a technical reviewer can dismiss in 30 seconds is worse than no Dataflow implementation.
- **Distraction risk**: Investing time in Dataflow before closing higher-ROI gaps (replay/backfill, dbt observability) reduces the portfolio's overall strength. The market-value audit ranks Dataflow as Priority 5 precisely because a decision record closes the gap at minimal risk.

---

## 5. Trigger Conditions for Dataflow

The following table defines the measured evidence or hard requirements that would justify scheduling Dataflow implementation. Each trigger is evaluated against the current evidence baseline.

| Trigger | Current Evidence | Threshold for Action | Recommended Response |
|---|---|---|---|
| Sustained throughput exceeds single Cloud Run instance capacity | 10 eps proven; saturation point not characterized; no evidence of queue growth | Queue depth (undelivered messages) grows under sustained load; single worker processing rate < publish rate | Characterize saturation point (`docs/saturation-throughput-test-plan`); if ceiling < business requirement, evaluate Dataflow autoscaling |
| Pub/Sub undelivered message backlog growth | No backlog observed across all validation runs | Undelivered message count grows monotonically under sustained publish rate and does not drain | Diagnose root cause; if Cloud Run throughput is the bottleneck, evaluate `maxScale` increase first; then evaluate Dataflow |
| Need for event-time windowed aggregations | Current windowing is processing-time in dbt; no event-time windowing is required | Business requirement or target role specifies event-time windowed output (e.g., 1-minute OHLC bars from event timestamps) | Design Beam pipeline with `FixedWindows` and event-time semantics; execute `feat/dataflow-minimal-beam-proof` |
| Late-arriving event handling | No late events observed or handled | Events consistently arrive out of order; business logic requires inclusion of late events in prior windows | Add `AllowedLateness` to Beam pipeline; evaluate Pub/Sub message retention window |
| Stateful stream processing requirement | No stateful processing in current path | Processing logic requires per-key state across events (e.g., session detection, running aggregation without post-hoc dbt) | Design Beam stateful DoFn; requires Dataflow runner |
| BigQuery streaming-native write path required | Current path uses cursor-based batch append (BigQuery append job with MERGE) | Business requirement or client specifies a lower-latency streaming write path to BigQuery | Evaluate Beam BigQuery Storage Write API with `COMMITTED` mode; requires Dataflow; exactly-once semantics must be validated in the implementation before any such claim is made |
| Hard requirement from target role or client | No current hard requirement | Job description or client contract specifies Beam/Dataflow as a required skill or deliverable | Execute `feat/dataflow-minimal-beam-proof` to produce credible evidence; document results |
| Need to prove Apache Beam skill for recruitment | Current project has no Beam code | Specific role requires Beam experience that cannot be addressed by this decision record alone | Execute `feat/dataflow-minimal-beam-proof`; do not claim Beam experience until implemented |

---

## 6. Cloud Run vs Minimal Beam vs Production Dataflow

| Dimension | Current Cloud Run Worker Path | Minimal Beam / Dataflow Proof | Production-Like Dataflow Path |
|---|---|---|---|
| **Implementation status** | Validated: 50,000-event bounded load + 10 eps sustained | Not implemented | Not implemented |
| **Cost** | Very low: Cloud Run scales to zero; Cloud SQL STOPPED/NEVER | Low-medium: Dataflow billing starts on job launch; one-time bounded job | Medium-high: sustained streaming workers; ongoing Dataflow cost |
| **Complexity** | Low: standard Python Cloud Run container, Terraform-managed | Medium: Beam SDK, Dataflow runner, pipeline options, staging bucket | High: pipeline options, windowing, watermarks, state, side outputs, IAM, networking |
| **Validation effort** | Low: bounded publish, Cloud SQL row count, Cloud Monitoring metrics | Medium: job launch, job state capture, output row count, cost control | High: sustained streaming evidence, windowed output validation, exactly-once verification, SLO measurement |
| **Throughput maturity** | Validated to 10 eps sustained, 50,000 bounded; saturation point not characterized | Proof volume only (N test events); not a throughput claim | Designed for high-throughput sustained streaming; throughput must be evidenced |
| **Windowing** | Not implemented (post-hoc in dbt, processing-time) | Not implemented (minimal proof) | FixedWindows / SlidingWindows in Beam (event-time) |
| **Late-event handling** | Not implemented | Not implemented | AllowedLateness policy; side output for discarded late events |
| **Replay / backfill support** | Cursor-based BigQuery incremental append proven; message-level replay not documented | Not in scope for minimal proof | Replay requires Pub/Sub message retention window and pipeline rerun; documented in runbook |
| **Exactly-once claims** | At-least-once with ON CONFLICT deduplication; 0 duplicates proven at 50k events | At-least-once (minimal proof does not claim exactly-once) | Target: Beam BigQuery Storage Write API COMMITTED mode; exactly-once semantics NOT claimed until implemented and validated |
| **Monitoring** | 4 logs-based Cloud Monitoring metrics; 12 BigQuery quality time series; 4-panel dashboard; alert policies | Dataflow job metrics via Cloud Monitoring (system lag, throughput); Cloud Logging | Full Dataflow metrics: system lag, backlog bytes, throughput; alerting on pipeline staleness; SLO integration |
| **Recruitment value** | Strong for GCP platform / Data Engineer roles; insufficient for Dataflow-specific streaming roles | Minimal Dataflow evidence; sufficient for "exposure to Beam" claim | Credible Dataflow streaming portfolio; addresses streaming-specific roles |
| **Risk** | Minimal: already validated; cost-controlled; reversible | Medium: Dataflow billing starts on launch; cleanup required (drain/cancel) | High: sustained streaming cost; complex pipeline; difficult to demonstrate safely in portfolio context |

---

## 7. Minimal Beam / Dataflow Proof Design

This section describes a future minimal Beam/Dataflow proof. It does not implement anything. The proof is designed to be executed in a dedicated branch after the decision record conditions (Section 5) are reviewed and at least one trigger condition is met, or if a target role requires Beam experience.

### Branch Name

`feat/dataflow-minimal-beam-proof`

### Expected Files

| File | Purpose |
|---|---|
| `pipelines/beam_market_events.py` | Python Apache Beam pipeline: ReadFromPubSub → parse MarketEvent → WriteToBigQuery |
| `docs/dataflow-minimal-beam-proof-runbook.md` | Scoped runbook: job launch, cost controls, drain/cancel, cleanup, cost ceiling |
| `docs/dataflow-minimal-beam-proof-evidence.md` | Evidence: job ID, job state, event count ingested, BigQuery row count, cost estimate, no errors |

### Possible Source

- Bounded Pub/Sub sample: publish N test events to a test Pub/Sub topic; read with `ReadFromPubSub`.
- Existing Pub/Sub subscription: not recommended for minimal proof (risk of consuming live messages).

### Possible Sink

- BigQuery staging table (not `rtdp_analytics.market_events_raw`): separate `rtdp_analytics.market_events_beam_proof` test table or a disposable dataset.
- Do not write to production BigQuery tables during the minimal proof.

### Acceptance Criteria

| Criterion | Required |
|---|---|
| N test events ingested via ReadFromPubSub | Yes: all N events |
| N rows written to BigQuery sink table | Yes: N rows; count must match |
| Dataflow job ID captured in evidence | Yes |
| Dataflow job state captured in evidence (DONE or DRAINED) | Yes |
| No pipeline errors in Cloud Logging | Yes |
| Cloud cost bounded by runbook ceiling | Yes: job drain/cancel before time limit |
| No claim of production Dataflow | Yes: evidence explicitly states minimal proof scope |

### Required Cost Controls

The following controls are mandatory for `feat/dataflow-minimal-beam-proof`. No exception.

- **Explicit start timestamp**: record the job launch time in the evidence document.
- **Short run window**: the job must complete or be drained/cancelled within a defined time ceiling (e.g., 10 minutes). The runbook must specify the ceiling.
- **Job drain or cancel instruction**: the runbook must include explicit `gcloud dataflow jobs drain JOB_ID` or `gcloud dataflow jobs cancel JOB_ID` instructions with the correct project and region.
- **No long-running streaming job**: do not leave a Dataflow streaming job running unattended. A streaming job left running overnight will incur significant cost. If a streaming proof is required, the runbook must specify the exact cancel command and the operator must confirm cancel before ending the session.
- **Cost estimate recorded**: estimate the expected worker cost based on vCPU-hours. Record in the evidence document.
- **No auto-restart or scheduler trigger**: the job must not be triggered by Cloud Scheduler or any automated mechanism during the proof.

---

## 8. Production-Like Dataflow Path

A production-credible Dataflow implementation for the Real-Time Data Platform would require all of the following. None of this is implemented. This section is a forward-looking design reference.

### Infrastructure

- Terraform-managed Dataflow resources: `google_dataflow_flex_template_job` or equivalent, with Terraform-controlled launch parameters.
- Alternatively, a Dataflow Flex Template approach: a Docker image containing the Beam pipeline, stored in Artifact Registry, launched via a Flex Template launch request.
- Dedicated Dataflow service account with job-scoped IAM: `roles/dataflow.worker`, BigQuery write permissions, Pub/Sub subscriber permissions.
- Staging GCS bucket for Dataflow temp files and binary staging.
- VPC configuration if private Google Access is required.

### Beam Pipeline

- `ReadFromPubSub` with `timestamp_attribute` for event-time semantics.
- Beam `FixedWindows` or `SlidingWindows` with configurable window duration.
- `AllowedLateness` policy with a documented tolerance (e.g., 60 seconds).
- Dead-letter side output (`TaggedOutput`) for events that fail parsing or exceed lateness tolerance.
- Dead-letter side output written to a separate BigQuery table or Pub/Sub DLQ topic.
- `WriteToBigQuery` using the Beam BigQuery Storage Write API (`COMMITTED` mode) as the target path for stronger write guarantees; exactly-once semantics must be validated in the actual implementation and are not claimed in advance.

### Monitoring and Observability

- Dataflow system lag metric: Cloud Monitoring `dataflow.googleapis.com/job/system_lag`.
- Backlog bytes metric: `dataflow.googleapis.com/job/pubsub_undelivered_bytes`.
- Throughput metric: `dataflow.googleapis.com/job/elements_produced_count`.
- Alert policy: Dataflow system lag > threshold triggers Cloud Monitoring alert.
- Cloud Logging structured logs from DoFn execution.
- Pipeline staleness detection: alert if no elements have been processed within a configurable window.

### Autoscaling

- Dataflow worker autoscaling policy configured (`--autoscalingAlgorithm=THROUGHPUT_BASED`).
- Min and max worker count explicitly configured and bounded (cost control).
- Worker type specified (e.g., `n1-standard-2`) and documented.

### Replay / Backfill Strategy

- Pub/Sub message retention window set to 7 days (or configurable).
- Documented procedure to seek a Pub/Sub subscription to a specific timestamp for replay.
- Beam pipeline designed to be idempotent on replay (no duplicate rows in BigQuery sink).
- Runbook for replay execution: seek timestamp, launch pipeline, monitor to completion, verify output counts.

### Cost Monitoring

- BigQuery billing export analyzed to calculate per-event cost under Dataflow.
- Dataflow cost compared to Cloud Run cost at equivalent event rates.
- Decision criteria for scaling Dataflow worker count vs Cloud Run instance count.

### Staging / Production Separation

- A staging BigQuery dataset (`rtdp_analytics_staging`) receives Dataflow output for validation before promoting to production tables.
- Separate staging Pub/Sub subscription for Dataflow (not shared with Cloud Run worker).
- Dataflow launch in staging project (or staging namespace) before production.

### Runbooks

- Dataflow job launch runbook: launch parameters, expected startup time, health checks.
- Dataflow job drain runbook: explicit drain command, expected drain duration, verification.
- Dataflow job restart runbook: recovery from worker failure, pipeline restart with idempotent guarantees.
- Dataflow pipeline upgrade runbook: Blue/Green or replace strategy for pipeline code changes.

---

## 9. Recruitment Positioning

### For Roles That Require Dataflow

**Safe wording:**

> "I have not implemented Apache Beam or Dataflow in this project. I evaluated Dataflow against the current validated pipeline and documented the architectural reasoning for deferring it in a formal decision record. The decision record defines specific trigger conditions for when Dataflow becomes justified, designs a minimal Beam proof, and specifies what a production-like Dataflow path would require. I have not claimed Beam experience I do not have."

Do not say: "I have Dataflow experience." Do not say: "Dataflow is coming soon." Do not imply Beam familiarity from architectural reading alone.

If the role requires Dataflow from day one, acknowledge the gap directly and offer to demonstrate the decision record as evidence of architectural reasoning and evaluation discipline.

### For Roles Where Dataflow Is Optional

**Safe wording:**

> "The platform uses a Pub/Sub push subscription to a Cloud Run worker. I evaluated Dataflow as an alternative and documented why the Cloud Run path is the appropriate choice at the current validated scale. Dataflow would be justified if throughput requirements exceed single-instance Cloud Run capacity, if event-time windowing is required, or if a client specifies exactly-once BigQuery streaming writes. At 10 events/sec with p95 latency of 227 ms, none of those conditions are currently met."

This positions the deferral as a measured architectural decision, not an oversight.

### For GCP Platform Engineering Roles Without Dataflow

**Safe wording:**

> "My platform validation covers the full GCP data pipeline lifecycle: Pub/Sub ingestion, Cloud Run worker, Cloud SQL persistence, BigQuery analytical tier with dbt incremental models, Cloud Monitoring custom metrics, alert policies, and end-to-end incident notification. All infrastructure is Terraform-managed with zero-diff discipline. The streaming processing layer uses Cloud Run, which is appropriate for the current proven scale. Dataflow is deferred and documented."

### What to Claim and What Not to Claim

| Claim | Safe? | Notes |
|---|---|---|
| Architectural evaluation of Dataflow vs Cloud Run | Yes | This decision record is the evidence |
| Decision discipline: deferring premature architecture | Yes | This decision record is the evidence |
| Apache Beam experience | **No** | Do not claim until `feat/dataflow-minimal-beam-proof` is executed |
| Dataflow pipeline implementation | **No** | Not implemented |
| Exactly-once streaming semantics | **No** | Not claimed; ON CONFLICT deduplication is application-layer |
| Cloud Run for event processing at 10 eps | Yes | Evidenced |
| Windowed streaming aggregations | **No** | Not implemented in Beam; dbt post-hoc aggregation is not streaming windowing |

---

## 10. Risks of Implementing Dataflow Too Early

### Shallow Implementation Risk

A Dataflow pipeline implemented quickly, without a scoped runbook, cost controls, and acceptance criteria, will produce evidence that a technical reviewer can dismiss in minutes. A shallow Beam pipeline that reads three events and writes them to a test table -- without windowing, watermarks, exactly-once semantics, or production-like monitoring -- is not a credible Dataflow portfolio artifact. It may be worse than no Dataflow at all, because it invites deeper scrutiny and demonstrates that the candidate does not know what production Dataflow requires.

### Cloud Cost Risk

Dataflow workers bill from the moment a job is launched. A streaming Dataflow job left running for an hour incurs material cost. A cancelled or failed job may still accrue partial billing. Without a scoped runbook with explicit cost ceilings and drain/cancel instructions, a Dataflow experiment can quickly exceed a reasonable portfolio project budget.

### Distraction from Higher-ROI Gaps

The market-value gap audit (Section 5 of `docs/market-value-gap-audit-2026-2027.md`) ranks replay/backfill strategy and dbt observability metrics ahead of Dataflow implementation in near-term recruitment ROI. These are docs-only, zero-cost branches that close visible gaps in the platform narrative. Spending time on Dataflow before these gaps are closed reduces the portfolio's overall strength relative to the time invested.

### Overengineering Risk

The current Cloud Run path handles 10 events/sec with p95 latency of 227 ms, zero errors, and zero duplicates. Replacing it with Dataflow without a demonstrated throughput or processing requirement would be premature optimization. Architectural decisions made without measured justification are a signal of immature engineering judgment, not a strength.

### False Confidence Risk

Implementing Dataflow and producing evidence that a minimal Beam pipeline "works" does not mean the candidate understands Dataflow production operations: autoscaling policies, worker failure recovery, pipeline upgrade strategies, exactly-once semantics under concurrent writes, Dataflow cost attribution, or BigQuery Storage Write API behavior under load. A minimal proof without these dimensions may create false confidence in both the candidate and the reviewer.

### Risk of Breaking the Current Validated Path

Any change to the ingestion path (e.g., switching Pub/Sub subscriptions, adding a new consumer) could interfere with the validated Cloud Run worker path. A Dataflow implementation that shares the production Pub/Sub subscription with the Cloud Run worker will cause message loss from the worker's perspective. Careful subscription management is required, which adds operational complexity to a minimal proof.

---

## 11. Explicit Non-Claims

The following are not claimed by this project as of 2026-05-22.

- **Dataflow is not implemented.** No Apache Beam pipeline has been written or executed.
- **Apache Beam code is not implemented.** No `beam_market_events.py` or equivalent pipeline file exists.
- **Exactly-once production semantics are not claimed.** Pub/Sub guarantees at-least-once delivery. The ON CONFLICT deduplication provides application-layer idempotency, not transport-layer exactly-once.
- **Windowed streaming is not implemented.** The dbt minute and daily aggregations are processing-time batch transformations, not event-time Beam windowed aggregations.
- **Late-event handling is not implemented.** No `AllowedLateness` policy, no side output for late events, no event-time watermark.
- **Dataflow autoscaling is not proven.** maxScale=1 on Cloud Run is the current concurrency ceiling.
- **BigQuery Storage Write API exactly-once path is not proven.** The current BigQuery write path is cursor-based batch MERGE, not streaming insert with COMMITTED mode.
- **Production streaming Dataflow is not claimed.** No Dataflow job has been launched against the production Pub/Sub topic or the production BigQuery dataset.
- **Maximum throughput / saturation point is not characterized.** The platform has been validated to 10 events/sec sustained and 50,000 events bounded. The throughput ceiling is unknown.
- **Multi-day production stability is not proven.** All validation runs are bounded windows (30 minutes to approximately 57 minutes).
- **DLQ production consumer is not implemented.** DLQ routing is proven; no automated consumer reads or reprocesses DLQ messages.
- **Replay / backfill operational strategy is partial.** Cursor-based BigQuery incremental append is proven; message-level streaming replay is not documented at operational depth.
- **Staging / production separation is not implemented.** All infrastructure is in a single GCP project.
- **Deploy-on-merge is not implemented.** Both worker and API deploy workflows require manual workflow_dispatch.
- **Enterprise security certification is not present.** No SOC 2, ISO 27001, or penetration test has been performed.

---

## 12. Final Decision

### Keep Cloud Run Worker as Validated Baseline

The Pub/Sub → Cloud Run worker → Cloud SQL → BigQuery → dbt path remains the primary validated ingestion and processing path. It has been proven at 50,000 events and at 10 events/sec sustained for 30 minutes. It is Terraform-managed, cost-controlled, and observable. No evidence justifies replacing it with Dataflow at this time.

### Defer Dataflow Implementation

Dataflow / Apache Beam implementation is deferred. The deferral is not ignorance; it is a documented architectural decision with explicit trigger conditions. Implementing Dataflow before any trigger condition is met would be premature architecture, carrying cloud cost risk and shallow implementation risk without proportionate portfolio value.

### Create a Minimal Beam Proof Only After Prerequisites

Create `feat/dataflow-minimal-beam-proof` only after:

1. `docs/replay-backfill-strategy` is complete, OR
2. `docs/dbt-observability-metrics-plan` is complete, OR
3. A specific target role or client requires Beam experience before those branches are complete.

The minimal proof must follow the runbook template in Section 7 of this document: scoped acceptance criteria, explicit cost controls, drain/cancel instructions, and honest evidence scope (no production Dataflow claim).

### Recommended Next Branches After This Document

**Next branch: `docs/replay-backfill-strategy`**

- Closes the operational replay and backfill gap.
- Directly answers a common data platform interview question.
- Docs-only; no cloud execution, no Terraform apply, no Cloud SQL start.
- Higher near-term ROI than Dataflow implementation.

**Then: `docs/dbt-observability-metrics-plan`**

- Closes the last significant gap in the analytics engineering story.
- Defines dbt-specific Cloud Monitoring metrics (run duration, model row counts, test pass rates).
- Docs-only; no cloud execution, no Terraform apply, no Cloud SQL start.

**Then: `feat/dataflow-minimal-beam-proof`** (conditional on trigger conditions or role requirement)

- Only if a trigger condition from Section 5 is met, or a specific role requires Beam evidence.
- Must follow the cost controls and acceptance criteria in Section 7.
- Does not claim production Dataflow.

---

## Validation Commands

```bash
git diff --check
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
grep -En "dataflow-decision-record|DECISION RECORD -- Dataflow" docs/EVIDENCE_INDEX.md
grep -En "Dataflow|Apache Beam|Cloud Run|Trigger Conditions|Minimal Beam|Production-Like Dataflow|Explicit Non-Claims|Final Decision" docs/dataflow-decision-record.md
gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="table(name,state,settings.activationPolicy)"
gcloud scheduler jobs list --project=project-42987e01-2123-446b-ac7 --location=europe-west1 --format="table(id,state,schedule)"
git status --short --branch
```

---

## Evidence Links

| Document | Relevance |
|---|---|
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog; all platform evidence indexed here |
| [docs/market-value-gap-audit-2026-2027.md](market-value-gap-audit-2026-2027.md) | Gap audit that recommended this decision record as Priority 5 |
| [docs/platform-audit-after-cost-performance.md](platform-audit-after-cost-performance.md) | Platform audit confirming Dataflow as deferred; current evidence baseline |
| [docs/gap-closure-snapshot-after-steady-state.md](gap-closure-snapshot-after-steady-state.md) | Post-steady-state gap closure snapshot |
| [docs/cost-performance-summary.md](cost-performance-summary.md) | Cost drivers, resource sizing, Cloud Run maxScale=1 documentation |
| [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md) | 10 eps for 30 min; 18,000 events; p50/p95/p99 latency evidence |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | 50,000-event bounded cloud load test evidence |
| [docs/latency-artifact-100-cloud-validation-evidence.md](latency-artifact-100-cloud-validation-evidence.md) | p50/p95/p99 end-to-end latency from producer artifact and worker logs |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets, error budget, incident runbooks |
| [docs/recruiter-facing-platform-summary.md](recruiter-facing-platform-summary.md) | Safe recruitment positioning for the full platform |
| [docs/gcp-architecture.md](gcp-architecture.md) | GCP service mapping and target architecture |
