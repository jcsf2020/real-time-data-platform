# Market Value Gap Audit 2026-2027

**Status:** STRATEGIC AUDIT -- market-value gap prioritization for production-like GCP Data Engineering portfolio
**Date:** 2026-05-22
**Branch:** `docs/market-value-gap-audit-2026-2027`
**Author intent:** Evidence-based, critical assessment. No sales language. No unsupported claims.

---

## 1. Executive Summary

The Real-Time Data Platform is currently a strong GCP Data Engineering portfolio asset.
It is strongest on the core pipeline: Pub/Sub ingestion, Cloud Run worker, Cloud SQL
persistence, BigQuery analytics, dbt transformation, Terraform IaC, CI discipline,
Cloud Monitoring observability, and a proven end-to-end alerting loop. Every claim
is backed by indexed, verifiable evidence with run IDs and commit SHAs.

Where it is exposed:

- **Bounded Apache Beam / DataflowRunner proof is validated (see dataflow-bounded-runner-proof-evidence.md).** Production windowed Dataflow streaming remains absent. The previous binary lack-of-evidence gap is closed; the remaining gap is production-like Dataflow streaming semantics for streaming-first roles.
- **No staging/production separation.** A single GCP project with manual deploy triggers
  limits production-likeness credibility.
- **No deploy-on-merge.** CI is automated; CD is not.
- **No multi-day production stability proof.** All validation runs are bounded windows.
- **Replay/backfill semantics are partial.** Strategy is not documented at operational depth.
- **dbt-specific observability metrics are missing.** The analytics engineering story is
  strong but lacks a closed telemetry loop for the transformation layer itself.

The purpose of this document is to rank the remaining gaps by 2026-2027 recruitment value
and production-likeness impact, and to produce a prioritised, actionable roadmap for the
next branches. This audit does not implement anything. It does not inflate any claim.

---

## 2. Current Evidence Baseline

The following capabilities are validated as of 2026-05-22. Only evidence-backed facts
are included.

### Event Ingestion and Processing

| Metric | Value | Source |
|---|---|---|
| 50,000-event bounded cloud load test | PASSED: 0 publish errors, 0 worker errors, 0 duplicate event_ids | load-test-50000-cloud-evidence.md |
| Sustained 10 events/sec for 30 minutes | PASSED: 18,000 attempted publishes, 18,000 acknowledged, 0 publish errors | steady-state-10eps-30min-cloud-validation-evidence.md |
| Matched unique worker events | 18,000 of 18,000 (0 missing) | steady-state-10eps-30min-cloud-validation-evidence.md |
| p50 end-to-end latency | 154.385 ms | steady-state-10eps-30min-cloud-validation-evidence.md |
| p95 end-to-end latency | 227.59 ms | steady-state-10eps-30min-cloud-validation-evidence.md |
| p99 end-to-end latency | 693.995 ms | steady-state-10eps-30min-cloud-validation-evidence.md |
| max latency | 960,263.973 ms -- documented as outlier/log-join/delayed-observation caveat, not normal tail | steady-state-10eps-30min-cloud-validation-evidence.md |
| Cloud SQL final state (every validation) | STOPPED / NEVER | Multiple evidence docs |
| Schedulers final state (every validation) | PAUSED | Multiple evidence docs |

### Infrastructure, Analytics, and Observability

| Capability | State | Evidence |
|---|---|---|
| Terraform IaC | 100% GCP resource coverage; GCS-backed remote state; PLAN_EXIT=0 throughout | All *-import-plan-evidence.md |
| Workload Identity Federation | GitHub Actions OIDC; no stored service account keys in CI | workload-identity-terraform-import-plan-evidence.md |
| BigQuery analytical tier | rtdp_analytics dataset; 3 DAY-partitioned tables; 6,120 rows; cursor-based incremental MERGE | bigquery-incremental-append-evidence.md |
| dbt incremental models | Silver + gold delete+insert; 22 dbt tests; Cloud SQL live execution proven | dbt-cloud-sql-incremental-execution-proof.md |
| Cloud Monitoring | 4 logs-based metrics + 12 BigQuery quality time series; 4-panel dashboard; 2 alert policies | cloud-logs-based-metrics-datapoint-validation.md |
| Alerting loop | Quality failure → Cloud Monitoring incident OPEN → email delivery proven | bigquery-quality-incident-notification-delivery-proof.md |
| DLQ policy | deadLetterPolicy, maxDeliveryAttempts=5, 10s/60s backoff; malformed routing validated with caveat | production-pubsub-dlq-evidence.md, dlq-malformed-message-validation-evidence.md |
| CI | pytest (257 tests), ruff, Terraform plan CI, dbt compile/run/test on every push | .github/workflows/ci.yml |
| BigQuery quality checks | 8-check workflow; scheduled execution proven; controlled failure + pass both evidenced | bigquery-quality-incident-notification-delivery-proof.md |
| SLO and incident response | Production-light SLO targets, error budget, severity levels, runbooks documented | SLO_AND_INCIDENT_RESPONSE.md |
| Cost-control posture | Cloud SQL STOPPED/NEVER in 60+ evidence docs; schedulers PAUSED; Cloud Run worker maxScale=1 | cost-performance-summary.md |

### Explicit Non-Claims (unchanged from prior audits)

- Bounded Apache Beam / DataflowRunner proof: VALIDATED (see dataflow-bounded-runner-proof-evidence.md). Production streaming Dataflow: not claimed. Windowed/stateful Dataflow streaming: not implemented.
- Exactly-once production semantics: NOT claimed.
- Maximum throughput / saturation point: NOT characterized.
- Multi-day continuous production stability: NOT proven.
- DLQ production consumer: NOT implemented.
- Exact cost per event (EUR/USD/GBP): NOT calculated from billing export.
- Staging/prod split: NOT implemented.
- Deploy-on-merge: NOT implemented.
- Enterprise security certification (SOC 2, ISO 27001): NOT present.

---

## 3. 2026-2027 Market Value Lens

Market trend analysis is based on architectural judgment and GCP-oriented job description
patterns observed as of mid-2026. This is not live job-market scraping.

| Capability | Current Project Status | Market Value 2026-2027 | Gap Severity | Recommended Action |
|---|---|---|---|---|
| GCP Pub/Sub | Strong: 50k events, DLQ configured, push subscription operational | Very High -- mandatory for GCP streaming roles | None | Maintain; ensure decision record links evidence |
| Cloud Run | Strong: worker, API, 4 jobs all deployed and evidenced | Very High -- serverless compute pattern is dominant in GCP portfolios | None | Maintain; optional: document back-pressure / auto-scaling analysis |
| Cloud SQL PostgreSQL | Adequate: 50k rows proven; STOPPED/NEVER posture | High -- operational store in almost every GCP data pipeline | Low (posture needs explaining) | Posture documentation sufficient; plan persisted latency columns |
| BigQuery | Adequate: 6,120 rows; partitioned; incremental append; quality checks | Very High -- non-negotiable for GCP analytics roles | Low-Medium (small dataset; no streaming insert path) | Consider throughput-scale BigQuery evidence or BigQuery streaming API reference |
| dbt | Good: 22 tests; incremental models; Cloud SQL live execution | High -- analytics engineering is a required skill for 2026-2027 data platforms | Low-Medium (no dbt observability metrics) | Close dbt observability metrics gap: plan document |
| Terraform / IaC | Strong: 100% coverage; zero-diff discipline; GCS state; Workload Identity | Very High -- IaC ownership is a hard requirement in most platform JDs | Minimal | Maintain zero-diff discipline |
| Cloud Monitoring / incident response | Strong: 4 logs-based metrics; alert policies; email delivery proven | High -- end-to-end alerting loop is a genuine differentiator | Low (SLO burn-rate not implemented) | Write SLO burn-rate monitoring plan |
| Dataflow / Apache Beam | Bounded proof validated (see dataflow-bounded-runner-proof-evidence.md); production streaming not claimed | High for streaming-first roles; Medium for platform generalist roles | **Partial: bounded proof closes the binary evidence gap; production windowed streaming remains the gap for streaming-specific JDs** | Claim bounded Beam proof; be explicit that production windowed Dataflow streaming is not implemented |
| Replay / backfill | Partial (cursor-based BigQuery append proven; no streaming replay) | High -- often asked in data platform interviews | Medium | Write replay/backfill strategy document |
| Data quality automation | Strong: 8-check BigQuery workflow; Cloud Monitoring metrics; incident email proven | High -- data quality ownership is a differentiator in 2026-2027 | Low-Medium (no dbt-level quality metrics) | Close via dbt observability metrics plan |
| Cost / performance ownership | Good: Cloud SQL STOPPED/NEVER; schedulers PAUSED; cost model documented | Medium-High -- cost discipline separates senior from junior candidates | Low (no exact billing export analysis) | Write billing export / cost-per-event plan |
| CI/CD | Partial: CI automated; CD requires manual workflow_dispatch | High -- CD automation is a hard expectation for platform roles | Medium (no deploy-on-merge) | Write deploy-on-merge decision record |
| Staging / prod separation | MISSING: single GCP project; no staging isolation | High -- single-environment portfolios are a flag for production-readiness reviewers | Medium | Write staging environment plan |
| Observability / SLOs | Good: SLO targets documented; no burn-rate alerting implemented | High -- SLO ownership is a senior engineering signal | Medium (burn-rate alerting unimplemented) | Write SLO burn-rate monitoring plan |
| Security / governance | Partial: Workload Identity, Secret Manager, job-scoped IAM; no external certification | Medium -- portfolio-grade security is acceptable; enterprise certification is out of scope | Medium (no data governance artifacts) | Write security / governance posture summary |

---

## 4. Gap Register

All gaps listed. Priority score: 5 = highest urgency, 1 = lowest.

| Gap | Current Status | Recruitment Impact | Production-Likeness Impact | Risk if Ignored | Effort | Priority (1-5) | Recommended Branch |
|---|---|---|---|---|---|---|---|
| Dataflow / Apache Beam production streaming | Bounded proof validated; production windowed streaming not implemented | **Critical for streaming-specific roles requiring windowed/stateful Dataflow; Medium for broad GCP roles** | Low (bounded proof closes the binary gap; windowed semantics not yet proven) | Streaming-first JDs requiring windowed Dataflow cannot be fully addressed; bounded proof is significant progress | High (production windowed implementation) | **3** | `feat/dataflow-windowed-streaming-proof` |
| Replay / backfill strategy | Partial: cursor-based BigQuery append proven; no streaming-level replay documented | High: replay semantics are a standard data platform interview topic | Medium: operational replay path is not described | Interview question about disaster recovery and data reprocessing has no written answer | Low | **4** | `docs/replay-backfill-strategy` |
| dbt observability metrics | Missing: no Cloud Monitoring metrics emitted from dbt job execution | Medium-High: analytics engineering story is strong but lacks its own telemetry loop | Medium: dbt jobs have no observable signal beyond Cloud Run execution success | Cannot demonstrate full observability discipline for the transformation layer | Low | **4** | `docs/dbt-observability-metrics-plan` |
| Staging / prod environment separation | MISSING: single GCP project; no staging; no isolated test environment | High: single-environment is a common red flag in production-readiness reviews | High: no ability to test changes safely before production promotion | Senior reviewers will call out the absence of environment isolation | Low (plan) / Medium (implementation) | **4** | `docs/staging-environment-plan` |
| Deploy-on-merge decision or implementation | MISSING: both deploy workflows require manual workflow_dispatch; CI is automated; CD is not | Medium-High: CD automation is now a table-stakes expectation for platform engineers | Medium: manual deploy reduces iteration speed and introduces deploy-drift risk | CI/CD story is incomplete; CD gap is visible in every workflow file | Low (decision record) | **3** | `docs/deploy-on-merge-decision-record` |
| SLO burn-rate monitoring | MISSING: SLO targets and incident runbooks documented; no burn-rate alerting in Cloud Monitoring | Medium: SLO burn-rate is a senior-level observability signal | Medium: current alerting is event-based (error count > 0), not budget-based | Platform lacks error-budget awareness; cannot demonstrate proactive SLO management | Low (plan) / Medium (implementation) | **3** | `docs/slo-burn-rate-monitoring-plan` |
| Data contracts / schema evolution | Partial: Pydantic MarketEvent with schema_version=1.0; no formal schema registry or evolution strategy documented | Medium: schema evolution is a common data platform interview topic | Medium: single schema version; no migration or compatibility layer documented | Cannot answer questions about backward compatibility or consumer protection | Low | **3** | `docs/data-contracts-schema-evolution-strategy` |
| Data lineage / catalog documentation | MISSING: no data lineage graph; no catalog artifact for consumers | Medium: data lineage is increasingly expected in 2026-2027 analytics roles | Low-Medium: lineage is informally implied by the architecture but not surfaced | Portfolio lacks data governance depth for analytics-heavy JDs | Low | **3** | `docs/data-lineage-catalog-plan` |
| Back-pressure and queue-depth handling | NOT characterized: Cloud Run worker maxScale=1; no queue-depth monitoring or back-pressure evidence | Medium: back-pressure handling is a signal of streaming architecture maturity | Medium: unclear behavior when Pub/Sub backlog exceeds worker processing capacity | Cannot describe how the system behaves under sustained overload | Low (analysis doc) | **3** | `docs/back-pressure-queue-depth-analysis` |
| Maximum throughput / saturation test | NOT claimed: 50k bounded load and 10 eps steady-state proven; saturation point unknown | Medium: saturation point and throughput ceiling are credible interview topics | High: a platform with no known ceiling is harder to trust in production | Cannot answer "what happens at 100 eps?" or "where does it fall over?" | Medium (requires cloud execution) | **3** | `docs/saturation-throughput-test-plan` |
| DLQ production consumer | Strategy documented; malformed routing proven with caveat; automated consumer NOT implemented | Medium: DLQ consumer closes the full error handling loop | Medium: DLQ messages accumulate with no automated recovery path | Poisoned messages pile up silently; no production recovery path | Medium (code + cloud) | **3** | `docs/dlq-consumer-strategy` or `feat/dlq-consumer-implementation` |
| Cloud SQL persisted latency columns | NOT implemented: p50/p95/p99 from artifact/log join only; no DB-persisted timestamp columns | Medium: database-native latency analytics is stronger evidence | Low-Medium: artifact/log join is adequate for portfolio purposes but fragile under log retention limits | Latency evidence depends on log availability; query-time analysis is not possible | Medium (schema migration + cloud execution) | **3** | `docs/cloud-sql-persisted-latency-plan` |
| Cost per event from billing export | NOT calculated: cost model documented; formula defined; no GCP billing export analyzed | Low-Medium: cost per event is occasionally asked in senior interviews | Low: cost-control posture is demonstrated operationally; exact figure adds precision, not substance | Cannot quote a defensible cost-per-event figure; formula estimate only | Low (analysis doc) | **2** | `docs/billing-export-cost-per-event-plan` |
| Multi-day production stability validation | NOT proven: all runs are bounded 30-min to 57-min windows | High (for enterprise credibility): multi-day stability is a production-readiness signal | High: no evidence of behavior under extended runtime (connection leaks, memory drift, scheduling drift) | Cannot claim production stability; bounded runs only | High (requires sustained cloud execution + cost) | **2** | `docs/multi-day-stability-plan` |
| Product-facing dashboard | MISSING: Cloud Monitoring 4-panel engineering dashboard exists; no end-user or stakeholder-facing product view | Low-Medium: product dashboard differentiates portfolio for data-product roles | Low: platform serves data via API; product layer is not required for Data Engineer roles | No visible demo artifact for stakeholders; portfolio relies on documentation | Medium (design + implementation) | **2** | `docs/dashboard-productization-plan` |
| Security / governance posture | Partial: Workload Identity, Secret Manager, job-scoped IAM implemented; no certification or data governance artifacts | Medium: portfolio-grade security is acceptable; governance artifacts add depth | Medium: no data masking, no audit logging policy, no access review process | Senior reviewers in regulated industries will note the absence | Low (assessment doc) | **2** | `docs/security-governance-posture` |
| Runbook maturity / operational handover | Partial: SLO and incident response runbooks exist; no operational handover package; no on-call simulation | Low-Medium: runbook quality is a production-maturity signal | Medium: handover to another engineer is not demonstrated | Operational knowledge lives in the author's head; team scalability unclear | Low | **2** | `docs/runbook-maturity-operational-handover` |
| Disaster recovery / restore validation | NOT validated: no backup restore test; no failover simulation; no RTO/RPO statement | Low: DR validation is typically out of scope for portfolio projects | Medium: no proven path to restore the platform after data loss | Cannot state RTO or RPO; restore path is theoretical only | High (requires cloud execution) | **1** | `docs/disaster-recovery-restore-validation` |

---

## 5. Priority Ranking

The following 10 branches are ranked by a composite of recruiter keyword value,
architecture maturity signal, evidence credibility impact, implementation risk,
cloud cost risk, and ability to complete safely without GCP mutations.

| Rank | Branch Name | Objective | Why This First | Expected Evidence Output | Implementation Type | Risk Level |
|---|---|---|---|---|---|---|
| 1 | `docs/dataflow-decision-record` | Document the architectural reasoning for Cloud Run vs Dataflow; define when Dataflow becomes justified | Highest ROI per hour: closes the most common senior interview challenge with a single docs-only branch; demonstrates architectural judgment, not ignorance | ADR-style decision record: current path reasoning, Dataflow trigger conditions, minimal Beam proof design, production Dataflow path | docs-only | Minimal |
| 2 | `docs/replay-backfill-strategy` | Define operational replay and backfill semantics for the RTDP pipeline | Second-most-common data platform interview question; no cloud execution required; closes a documented gap | Strategy doc: replay trigger conditions, cursor-based path, message-level rewind analysis, backfill runbook skeleton | docs-only | Minimal |
| 3 | `docs/dbt-observability-metrics-plan` | Define and plan dbt-specific Cloud Monitoring metrics for the transformation layer | Closes the only remaining gap in the analytics engineering story; no cloud execution required; adds telemetry depth to a proven capability | Plan doc: metric types (dbt run duration, model row counts, test pass rates), emission strategy, alert thresholds | docs-only | Minimal |
| 4 | `docs/staging-environment-plan` | Design a staging/prod environment separation strategy | Addresses the most visible production-likeness gap; a written plan is more credible than silence; no cloud execution or Terraform apply required | Plan doc: project topology, promotion workflow, cost model, Terraform workspace strategy | docs-only | Minimal |
| 5 | `docs/deploy-on-merge-decision-record` | Document the deploy-on-merge decision and a safe implementation path | Closes the CI/CD gap with a decision record; positions the manual dispatch as a deliberate choice, not an omission | ADR-style doc: current trigger choice rationale, deploy-on-merge implementation path, risk analysis | docs-only | Minimal |
| 6 | `docs/slo-burn-rate-monitoring-plan` | Plan SLO burn-rate alerting on top of validated Cloud Monitoring metrics | Converts existing SLO targets into actionable error-budget monitoring; docs-only; high production-maturity signal | Plan doc: burn-rate calculation model, alert policy design, Cloud Monitoring implementation path | docs-only | Minimal |
| 7 | `docs/data-contracts-schema-evolution-strategy` | Document the schema evolution strategy for MarketEvent and downstream consumers | Demonstrates data contract maturity; addresses a common analytics platform interview topic; no code changes | Strategy doc: Pydantic versioning approach, backward compatibility policy, consumer protection model | docs-only | Minimal |
| 8 | `docs/back-pressure-queue-depth-analysis` | Characterize back-pressure behavior at Cloud Run maxScale=1 with Pub/Sub backlog growth | Closes a visible streaming architecture gap; demonstrates that the current limits are known and deliberate | Analysis doc: Pub/Sub delivery timeout behavior, Cloud Run concurrency=1 behavior under backlog, recommended monitoring approach | docs-only | Minimal |
| 9 | `docs/data-lineage-catalog-plan` | Produce a data lineage graph and catalog documentation for RTDP data products | Adds data governance depth; frequently required for analytics and data platform roles in 2026-2027 | Plan doc: lineage graph (bronze → silver → gold → BigQuery), catalog entry format, future tooling options | docs-only | Minimal |
| 10 | `docs/billing-export-cost-per-event-plan` | Plan a billing export analysis to convert the cost_per_event formula to a measured figure | Closes the cost-per-event gap; converts a formula to an evidence-backed claim | Plan doc: billing export setup, cost attribution methodology, expected per-event cost range | docs-only | Minimal |

---

## 6. Specific Dataflow Assessment

### Is the Lack of Dataflow a Serious Gap?

**It depends on the target role.** The absence of Dataflow is a binary disqualifier
for some roles and a non-issue for others. The answer below is direct, not softened.

**For roles where Dataflow is a serious gap:**

- Streaming Data Engineer with Beam/Dataflow in the required skills section
- GCP Streaming Platform roles that specify windowed aggregations, stateful processing,
  or exactly-once semantics
- Roles at organisations with existing Dataflow pipelines where operational Dataflow
  experience is expected from day one
- Senior Data Engineer roles where the scope includes architectural decisions about
  stream processing framework selection

For these roles, the current Cloud Run worker is not equivalent to Dataflow.
Submitting without Dataflow evidence for a Dataflow-specific JD is not credible.

**For roles where deferring Dataflow is acceptable:**

- GCP Data Engineer / Data Platform Engineer generalist roles where Pub/Sub, BigQuery,
  dbt, Terraform, and observability are the primary requirements
- Analytics Engineer with platform exposure roles
- Junior to mid Data Engineer roles where practical GCP evidence outweighs framework depth
- B2B / freelance delivery roles where the deliverable is a working platform, not
  Dataflow expertise specifically
- Roles where Cloud Run + Pub/Sub push subscription is the stated or implied pattern

**Market frequency estimate (architectural judgment, not live job-market scraping):**

Based on architectural judgment, not live job-market scraping, Dataflow / Apache Beam
appears frequently in GCP streaming-focused roles, but less consistently as a hard
requirement in broader GCP Data Engineer / Data Platform Engineer roles. Therefore,
the absence of Dataflow is a serious gap for streaming-specific roles, but not
automatically disqualifying for broader GCP platform roles where Pub/Sub, Cloud Run,
BigQuery, dbt, Terraform, CI/CD, and observability are the main evaluation signals.

### Should the Next Step Be Dataflow Implementation or a Decision Record?

**Recommendation: Decision record first. Implementation only if the decision record
concludes it is justified.**

Reasons:

1. A well-structured decision record demonstrates the same architectural reasoning that
   a Dataflow implementation would; it shows the candidate evaluated the trade-offs.
2. Dataflow implementation requires GCP cost (Dataflow workers are billed per vCPU-hour)
   and significant implementation complexity. Running a real Dataflow pipeline to produce
   credible evidence requires a non-trivial budget window.
3. The current Cloud Run path is not "wrong." It is appropriate for the current event
   rate (10 eps proven; no evidence saturation has been reached). Replacing it with
   Dataflow without a demonstrated need would be premature architecture.
4. A decision record that says "Dataflow becomes justified at X threshold and here is
   what a minimal proof looks like" is more credible than a rushed Dataflow implementation
   with shallow evidence.

### What Would a Minimal Beam/Dataflow Proof Look Like?

A minimum viable Dataflow proof for portfolio purposes would require:

1. A Python Apache Beam pipeline (streaming or batch) that reads from a Pub/Sub
   subscription, parses MarketEvent records, and writes to BigQuery using the
   Beam BigQuery I/O connector.
2. A Dataflow job launched via `gcloud dataflow jobs run` or Terraform, with a
   committed evidence doc showing job ID, state, and at least one output row.
3. Acceptance criteria: N events read from Pub/Sub, N rows written to BigQuery,
   zero pipeline errors, job state `DONE` or `RUNNING` as appropriate.
4. Cloud cost implication: Dataflow workers bill from the moment the job starts.
   A minimal single-event proof should be achievable in under 5 minutes with
   minimal cost, but the cluster startup overhead is non-trivial to manage safely.

This is achievable but requires a dedicated branch with a scoped runbook and
careful cost management.

### What Would a Production-Like Dataflow Path Look Like?

A production-credible Dataflow implementation would require:

1. A Python Beam streaming pipeline with `ReadFromPubSub` → windowed
   aggregations (`FixedWindows` or `SlidingWindows`) → `WriteToBigQuery`.
2. Exactly-once write semantics using the Beam BigQuery storage write API.
3. Autoscaling Dataflow worker configuration managed by Terraform.
4. Late-event handling with `AllowedLateness` policy.
5. Cloud Monitoring integration for Dataflow-specific metrics (system lag,
   backlog bytes, throughput).
6. Evidence: sustained processing of at least 18,000 events (equivalent to the
   steady-state run) with windowed output validated in BigQuery.
7. Cost implication: a sustained streaming Dataflow job running for 30 minutes
   will be materially more expensive than the current Cloud Run path. This is
   a meaningful cloud cost risk for a portfolio project.

### What Should Not Be Claimed Yet?

- Do not claim Dataflow is "coming soon" without a decision record.
- Do not claim the Cloud Run path is "production-equivalent to Dataflow" -- it is not.
- Bounded Beam proof is validated; bounded Apache Beam / DataflowRunner experience can be claimed. Do not claim production windowed streaming or stateful Dataflow without additional evidence.
- Do not claim exactly-once semantics without the Beam storage write API evidence.
- The decision record was written and the bounded proof executed; the bounded proof closes the binary evidence gap. Production windowed Dataflow is the remaining step.

### Comparison Table

| Dimension | Current Cloud Run Worker Path | Minimal Beam/Dataflow Proof | Production-Like Dataflow Pipeline |
|---|---|---|---|
| Implementation status | Validated at 50,000 events + 10 eps | Validated (JOB_STATE_DRAINED; 10 proof rows; see dataflow-bounded-runner-proof-evidence.md) | Not implemented |
| Windowed aggregations | Not implemented (done in dbt/PostgreSQL post-hoc) | Not implemented in beam | FixedWindows / SlidingWindows in Beam |
| Exactly-once semantics | At-least-once with ON CONFLICT deduplication | At-least-once (minimal proof) | Beam storage write API (exactly-once in BigQuery) |
| Late-event handling | Not implemented | Not implemented | AllowedLateness policy in Beam |
| Autoscaling | maxScale=1 (hard cap) | Dataflow worker autoscaling | Full Dataflow autoscaling configured |
| Cost | Very low (Cloud Run scales to zero) | Low-medium (Dataflow startup overhead) | Medium-high (sustained Dataflow workers) |
| Interview signal | Strong for platform roles; insufficient for Dataflow-specific roles | Bounded DataflowRunner proof validated; closes binary evidence gap; production windowed streaming not yet proven | Credible Dataflow streaming portfolio |
| Implementation risk | Already validated | Completed (Beam SDK + DataflowRunner executed) | High (complex, expensive, time-consuming) |
| Cloud cost risk | Minimal (controlled windows) | Incurred and bounded (proof-only topic; 10 rows) | High (sustained streaming workers) |
| Recommended for next branch? | Maintain as baseline | Completed -- bounded proof accepted | Consider only if streaming-first roles require windowed evidence |

---

## 7. Recommended Roadmap

All branches below avoid Cloud SQL start, Terraform apply, and GCP cost exposure
unless explicitly noted. Cloud SQL and scheduler state is STOPPED/NEVER and PAUSED
throughout.

### P0 -- Immediate Positioning Fixes (docs-only, no cloud, no code)

| Branch | Expected Files | Validation Commands | Cloud SQL Required | Terraform Apply | GCP Cost Risk |
|---|---|---|---|---|---|
| `docs/dataflow-decision-record` | `docs/dataflow-decision-record.md` | `grep -E "Dataflow\|Apache Beam\|decision" docs/dataflow-decision-record.md` | No | No | None |
| `docs/replay-backfill-strategy` | `docs/replay-backfill-strategy.md` | `grep -E "replay\|backfill\|cursor\|reprocess" docs/replay-backfill-strategy.md` | No | No | None |

### P1 -- High Recruitment Value, Low Risk (docs-only)

| Branch | Expected Files | Validation Commands | Cloud SQL Required | Terraform Apply | GCP Cost Risk |
|---|---|---|---|---|---|
| `docs/dbt-observability-metrics-plan` | `docs/dbt-observability-metrics-plan.md` | `grep -E "dbt\|observability\|metric\|monitoring" docs/dbt-observability-metrics-plan.md` | No | No | None |
| `docs/staging-environment-plan` | `docs/staging-environment-plan.md` | `grep -E "staging\|prod\|isolation\|workspace" docs/staging-environment-plan.md` | No | No | None |
| `docs/deploy-on-merge-decision-record` | `docs/deploy-on-merge-decision-record.md` | `grep -E "deploy\|merge\|CI\|CD\|workflow_dispatch" docs/deploy-on-merge-decision-record.md` | No | No | None |
| `docs/slo-burn-rate-monitoring-plan` | `docs/slo-burn-rate-monitoring-plan.md` | `grep -E "SLO\|burn.rate\|error.budget\|alerting" docs/slo-burn-rate-monitoring-plan.md` | No | No | None |

### P2 -- Production-Likeness Improvements (docs or light code)

| Branch | Expected Files | Validation Commands | Cloud SQL Required | Terraform Apply | GCP Cost Risk |
|---|---|---|---|---|---|
| `docs/data-contracts-schema-evolution-strategy` | `docs/data-contracts-schema-evolution-strategy.md` | `grep -E "schema.version\|evolution\|compatibility\|contract" docs/data-contracts-schema-evolution-strategy.md` | No | No | None |
| `docs/back-pressure-queue-depth-analysis` | `docs/back-pressure-queue-depth-analysis.md` | `grep -E "back.pressure\|queue.depth\|backlog\|concurrency" docs/back-pressure-queue-depth-analysis.md` | No | No | None |
| `docs/data-lineage-catalog-plan` | `docs/data-lineage-catalog-plan.md` | `grep -E "lineage\|catalog\|bronze\|silver\|gold" docs/data-lineage-catalog-plan.md` | No | No | None |
| `docs/cloud-sql-persisted-latency-plan` | `docs/cloud-sql-persisted-latency-plan.md` | `grep -E "latency\|timestamp\|p50\|p95\|p99" docs/cloud-sql-persisted-latency-plan.md` | No | No | None |

### P3 -- Larger Implementation Branches (code or cloud execution required)

| Branch | Expected Files | Validation Commands | Cloud SQL Required | Terraform Apply | GCP Cost Risk |
|---|---|---|---|---|---|
| `feat/dbt-observability-metrics-implementation` | `scripts/push_dbt_metrics.py`, updated `ci.yml`, `docs/dbt-observability-metrics-evidence.md` | `uv run pytest -q; grep -E "dbt_metric\|TOTAL\|timeSeries" docs/dbt-observability-metrics-evidence.md` | YES (controlled window) | Optional | Low |
| `exec/saturation-throughput-test` | `docs/saturation-throughput-test-evidence.md`, load script | `grep -E "saturation\|eps\|error\|PLAN_EXIT" docs/saturation-throughput-test-evidence.md` | YES (controlled window) | No | Medium |
| `feat/dataflow-minimal-beam-proof` | `pipelines/beam_market_events.py`, `docs/dataflow-minimal-beam-proof-evidence.md` | `gcloud dataflow jobs describe JOB_ID --format=json` | No | Possible | Medium-High |
| `docs/billing-export-cost-per-event-plan` | `docs/billing-export-cost-per-event-plan.md` | `grep -E "billing\|cost.per.event\|SKU\|export" docs/billing-export-cost-per-event-plan.md` | No | No | None |

---

## 8. Critical Technical Review

A senior hiring manager or technical interviewer may raise the following challenges.
Each is stated as it would actually be raised, not softened. The defensive answer is
evidence-based, not apologetic.

---

**Challenge: "This has no Dataflow. It's not a real streaming platform."**

Correct that Dataflow is not implemented. The Cloud Run push-subscription worker is
not a Beam pipeline. It does not perform windowed aggregations, does not handle late
events, and does not scale to enterprise streaming volumes through Dataflow autoscaling.

Defensive answer: The Cloud Run path is the appropriate architectural choice for the
current validated event rate (10 eps, 18,000 events per 30 minutes). At this rate,
the overhead, cost, and complexity of Dataflow are not justified. The decision to
defer is documented, not ignored. The question of when Dataflow becomes justified
(saturation point, windowing requirements, exactly-once SLA) is addressed in the
decision record. Candidates who implement Dataflow prematurely without measuring
their current stack's limits are not demonstrating sound architectural judgment.

---

**Challenge: "No multi-day production traffic. This is just a test harness."**

Correct. No continuous multi-day data flow has been proven. All validation runs are
bounded windows of 30 minutes to approximately 57 minutes.

Defensive answer: The platform operates in bounded, controlled windows by design.
This is deliberate cost discipline (Cloud SQL STOPPED/NEVER outside validation windows).
The platform is explicitly positioned as a portfolio project, not a continuously-running
enterprise system. The honest labelling of bounded evidence is a strength, not a weakness.
A candidate who claims sustained production traffic they cannot prove is a higher risk
than one who shows exactly what was tested.

---

**Challenge: "No staging environment. A production system always has staging."**

Correct. All infrastructure is in a single GCP project with no staging isolation.

Defensive answer: The staging gap is acknowledged, documented, and queued for the
`docs/staging-environment-plan` branch. The absence of staging is a known architectural
limitation. For a solo portfolio project, the cost of maintaining a fully isolated
staging environment was traded off against the cost of evidence-first production validation.
The correct mitigation -- which is documented -- is a second GCP project with Terraform
workspaces. The plan can be articulated clearly; it has not been implemented.

---

**Challenge: "No production replay. What happens when the pipeline fails for an hour?"**

Correct. No operational replay path for production messages has been implemented or
documented at runbook depth.

Defensive answer: The BigQuery incremental append job provides a cursor-based
reprocessing path from Cloud SQL. For bounded reprocessing, this path is proven and
idempotent (second run is idempotent at 6,120 rows). A full streaming message-level
replay is not implemented. The `docs/replay-backfill-strategy` branch will document
the operational replay semantics explicitly, including the distinction between
cursor-based reprocessing and Pub/Sub message retention-based replay.

---

**Challenge: "No measured cost per event. You cannot manage cloud costs without data."**

Technically correct. The cost_per_event formula is defined. No GCP billing export
has been analyzed.

Defensive answer: The cost model inputs are documented precisely: Cloud SQL tier,
Cloud Run sizing, BigQuery table footprint, and the formula `cost_per_event = total_window_cost / event_count`.
The operational cost-control discipline is proven in 60+ evidence documents (Cloud SQL
STOPPED/NEVER, schedulers PAUSED). The missing piece is a billing export that converts
the formula to a measured figure. This is a known gap. The `docs/billing-export-cost-per-event-plan`
branch will close it with actual billing data analysis.

---

**Challenge: "No exactly-once semantics. At-least-once is not safe for financial data."**

Correct. Exactly-once end-to-end semantics are not claimed. Pub/Sub guarantees
at-least-once delivery. The ON CONFLICT idempotency at Cloud SQL prevents duplicate
rows, but this is application-level deduplication, not transport-layer exactly-once.

Defensive answer: The platform implements at-least-once delivery with application-layer
idempotency deduplication via `ON CONFLICT(event_id) DO NOTHING`. Zero duplicates have
been proven at 50,000 events and 18,000 steady-state events. This covers the observed
failure modes in the test evidence. True exactly-once transport-layer semantics require
either Dataflow with the BigQuery storage write API or an equivalent mechanism. This
is documented as a non-claim, not an omission.

---

**Challenge: "No enterprise security certification. I cannot put this in production."**

Correct. No SOC 2, ISO 27001, GDPR DPA, or penetration test exists.

Defensive answer: The security posture is portfolio-grade. Workload Identity Federation
eliminates stored service account keys in CI. Secret Manager provides runtime-only secret
injection. IAM bindings are job-scoped (not project-level). No credentials are committed.
Enterprise certification is out of scope for a portfolio project and is not claimed.
A candidate who pretends portfolio-grade security is enterprise-certified is a higher
risk than one who articulates the gap clearly.

---

## 9. Safe Recruitment Positioning

### LinkedIn / Recruiter Paragraph

> Built a GCP real-time data platform validated at 50,000 events with Pub/Sub, Cloud Run,
> Cloud SQL, BigQuery, dbt, Terraform, and Cloud Monitoring. The full stack is Terraform-managed
> with zero-diff discipline, 257 tests in CI, and an end-to-end alerting loop proven from
> BigQuery quality failure to delivered email. Evidence is indexed and verifiable.
> Bounded Apache Beam / DataflowRunner proof validated; production streaming Dataflow is not claimed. This is bounded portfolio evidence, not a production SLA claim.

### Technical Interview Paragraph

> I validated a GCP event-processing pipeline with Pub/Sub push subscription to a Cloud Run
> worker, idempotent Cloud SQL writes via ON CONFLICT, a BigQuery analytical tier with
> dbt incremental models, and Cloud Monitoring custom metrics. The platform was tested at
> 50,000 events with zero errors and zero duplicates, and at a sustained 10 events/sec for
> 30 minutes with p50/p95/p99 latency evidence from producer-to-worker instrumentation.
> All infrastructure is Terraform-managed with GCS remote state and Workload Identity
> Federation for CI. A bounded Apache Beam / DataflowRunner proof has been validated (JOB_STATE_DRAINED; 10 proof rows); production windowed Dataflow streaming is not claimed. The Cloud Run path remains the baseline at the current validated scale.

### Senior Engineer Caveat Paragraph

> This platform does not claim: production streaming Dataflow or windowed/stateful Apache Beam pipelines; exactly-once
> transport-layer semantics; maximum throughput or saturation characterization; multi-day
> continuous production stability; staging/production isolation; deploy-on-merge automation;
> or enterprise security certification. All validation runs are bounded, controlled windows.
> Cloud SQL is kept STOPPED/NEVER between runs. Every limitation is documented explicitly
> in the evidence base. The evidence is verifiable; nothing is invented.

---

## 10. Final Recommendation

### On Dataflow

**Do not implement Dataflow as the next step.**

Write `docs/dataflow-decision-record` first. The decision record will establish:
- why Cloud Run is the correct choice at the current validated scale,
- what measured evidence (saturation point, windowing requirement, exactly-once SLA)
  would justify Dataflow investment,
- what a minimal Beam proof looks like, and
- what a production-like Dataflow path requires.

A well-structured decision record is more credible to a senior reviewer than a rushed
Dataflow proof with shallow evidence. It also eliminates the risk of incurring Dataflow
worker costs for a pipeline that may not produce sufficient differentiation value.

If the decision record concludes that a minimal Beam proof is justified, schedule
`feat/dataflow-minimal-beam-proof` as a P3 branch with a scoped runbook and cost ceiling.

### Next 3 Branches in Order

**Branch 1: `docs/dataflow-decision-record`**

- Expected evidence: ADR-style document with architectural reasoning, trigger conditions,
  minimal proof design, and production Dataflow path description.
- No code changes. No cloud execution. No Terraform apply. No Cloud SQL start.
- Closes: the most common senior interview challenge about streaming architecture.

**Branch 2: `docs/replay-backfill-strategy`**

- Expected evidence: Strategy document covering cursor-based BigQuery reprocessing,
  Pub/Sub message retention replay, and a backfill runbook skeleton.
- No code changes. No cloud execution. No Terraform apply. No Cloud SQL start.
- Closes: the replay/backfill gap; addresses a standard data platform interview topic.

**Branch 3: `docs/dbt-observability-metrics-plan`**

- Expected evidence: Plan document defining dbt-specific Cloud Monitoring metrics
  (run duration, model row counts, test pass rates), emission strategy, and
  alert thresholds.
- No code changes. No cloud execution. No Terraform apply. No Cloud SQL start.
- Closes: the last significant gap in the analytics engineering story; adds telemetry
  depth to an already-proven dbt capability.

### What Not to Do Yet

- Do not implement Dataflow before the decision record is written.
- Do not start Cloud SQL outside a scoped validation runbook.
- Do not resume schedulers outside a scoped execution proof.
- Do not run `terraform apply` without a dedicated branch and a scoped plan.
- Do not claim sustained production throughput, exactly-once semantics, or enterprise
  security certification.
- Do not attempt a saturation throughput test before the decision record establishes
  whether the throughput ceiling justifies further investment.

---

## Validation Commands

```bash
git diff --check
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
grep -En "market-value-gap-audit-2026-2027|STRATEGIC AUDIT -- market-value" docs/EVIDENCE_INDEX.md
grep -En "Dataflow|Apache Beam|2026-2027|Priority Ranking|Gap Register|Recommended Roadmap|Critical|Safe Recruitment Positioning|Final Recommendation" docs/market-value-gap-audit-2026-2027.md
gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="table(name,state,settings.activationPolicy)"
gcloud scheduler jobs list --project=project-42987e01-2123-446b-ac7 --location=europe-west1 --format="table(id,state,schedule)"
git status --short --branch
```

---

## Evidence Links

| Document | Purpose |
|---|---|
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog -- 60+ documents by category |
| [docs/platform-audit-after-cost-performance.md](platform-audit-after-cost-performance.md) | Prior platform audit: closed gaps, remaining gaps, recruitment value |
| [docs/gap-closure-snapshot-after-steady-state.md](gap-closure-snapshot-after-steady-state.md) | Post-steady-state gap closure snapshot |
| [docs/cost-performance-summary.md](cost-performance-summary.md) | Cost drivers, resource sizing, performance evidence |
| [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md) | Sustained 10 eps for 30 minutes; 18,000 events; p50/p95/p99 latency |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | 50,000-event bounded cloud load test evidence |
| [docs/latency-artifact-100-cloud-validation-evidence.md](latency-artifact-100-cloud-validation-evidence.md) | p50/p95/p99 end-to-end latency from producer artifact and worker logs |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets, error budget, incident runbooks |
| [docs/recruiter-facing-platform-summary.md](recruiter-facing-platform-summary.md) | One-page hiring translation of the evidence base |
| [docs/executive-platform-audit-after-50k.md](executive-platform-audit-after-50k.md) | Post-50k platform audit with critical technical review |
