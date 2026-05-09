# DevOps / SRE Knowledge Base

## Reliability And SLOs
Reliability work starts by defining what users need from the system. Service level indicators measure user-visible behavior, service level objectives set reliability targets, and error budgets help teams balance feature velocity with stability. Good candidates distinguish internal infrastructure metrics from user-impacting signals and explain how alerting should avoid noise.

## Incident Response
Incident response prioritizes stabilization, impact assessment, communication, and evidence preservation. Engineers should reduce blast radius, apply mitigations, and form hypotheses from metrics, logs, and traces. A strong retrospective identifies detection gaps, prevention work, and recovery improvements instead of stopping at human error.

## Deployment And Rollback
Safe deployment strategies include blue-green releases, canaries, rolling deployments, feature flags, and automated rollback criteria. Database migrations require special care because schema and application versions may coexist. Good answers cover backward-compatible migrations, health checks, progressive rollout, and operational runbooks.

## Kubernetes And Infrastructure
Kubernetes introduces abstractions for scheduling, service discovery, scaling, and rollout control, but it also creates failure modes around resource limits, probes, networking, and control-plane pressure. Infrastructure as code helps make environments repeatable, reviewable, and recoverable. Strong engineers understand capacity planning, secrets management, and least privilege access.

## Observability And Capacity
Observability combines metrics, logs, traces, events, and dashboards into an explainable system. Capacity planning uses traffic growth, saturation signals, and load testing to avoid emergency scaling. Good candidates know how to reason about p95 and p99 latency, queue depth, CPU throttling, memory pressure, and dependency health.

