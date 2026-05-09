# Backend Engineer Knowledge Base

## Role Expectations
Backend engineering is about building reliable, observable, and evolvable services. A strong backend engineer understands request lifecycles, data modeling, failure domains, latency budgets, and how operational realities influence design choices. Good answers typically connect application behavior to storage systems, network behavior, concurrency, and the limits of eventual consistency.

## API Design And Contracts
Well designed APIs optimize for clarity, consistency, and resilience. Endpoints should have predictable shapes, explicit validation, and clear error semantics. Request idempotency matters whenever retries are possible, especially for writes triggered by payment flows, provisioning actions, or asynchronous clients. Versioning strategy should be deliberate. Some teams prefer URI versioning, others version through headers or additive schema evolution, but all approaches need a compatibility story.

Pagination, filtering, and partial failure handling are often under-discussed but critical for real systems. Cursor pagination scales better than offset pagination for large mutable datasets. APIs should also expose stable identifiers, enforce sensible limits, and return enough metadata for clients to recover or retry safely. Validation belongs close to the boundary of the service so bad data fails fast.

## Data Modeling And Transactions
Data modeling should begin with access patterns, not tables alone. Engineers need to know which entities are read together, which fields need indexes, where denormalization helps, and what consistency guarantees are truly required. Relational systems are often a strong default because they provide transactions, constraints, and mature query planners. NoSQL systems may help with write scalability or flexible schemas but shift more correctness burden onto application code.

Transactions preserve invariants within a bounded context, but distributed transactions are expensive and often avoided. Instead, systems use idempotency keys, outbox patterns, compensating actions, and carefully designed retry behavior. Good candidates know when atomicity is essential and when eventual consistency is acceptable. They should also be able to explain the operational cost of each choice.

## Indexing, Query Performance, And Caching
Indexes are valuable only when they match query patterns. Over indexing increases write cost and storage usage, while missing indexes create latency spikes and lock contention. Engineers should read query plans, understand selective predicates, and recognize anti patterns such as leading wildcard searches or sorting on unindexed columns at scale.

Caching can reduce latency and database load, but it introduces coherence problems. Common patterns include read through caches, write through caches, cache aside, and TTL based invalidation. Cache invalidation should be driven by domain semantics where possible rather than guesswork. A strong answer covers key selection, stale reads, warming strategy, fallback behavior, and monitoring of hit rates and eviction patterns.

## Queues, Background Jobs, And Retries
Many workflows do not belong on the synchronous request path. Queues allow expensive or failure prone tasks to run asynchronously, improve latency, and isolate transient dependencies. However, queues do not remove complexity; they move it. Systems must handle duplicate delivery, poison messages, ordering assumptions, retry storms, and backpressure.

Idempotent workers are essential. Every retryable job should be safe to process more than once or protected by a deduplication strategy. Dead letter queues help isolate bad messages, but they should not become silent graveyards. Strong operators watch queue depth, processing lag, success rates, and retry counts to detect incidents before customers do.

## Reliability, Consistency, And Idempotency
Real backend systems fail in partial ways. Databases become slow instead of fully down, third party APIs time out intermittently, and background workers backlog gradually. Reliability engineering therefore depends on timeouts, retries with jitter, circuit breakers, graceful degradation, and clear ownership boundaries. Synchronous chains of dependent services should stay as short as possible.

Idempotency is a powerful tool for handling retries safely. For write APIs, an idempotency key can bind repeated client attempts to the same logical operation. This reduces double charge and duplicate resource creation risks. Exactly once processing is rare in practice; most systems approximate it through at least once delivery plus idempotent handlers and reconciliation logic.

## Observability And Incident Response
Observability should make systems explainable under failure. Metrics capture trends such as request volume, error rate, latency percentiles, queue depth, and resource usage. Logs capture structured details for specific executions. Traces show how a request fans out across services. Together they help engineers move from symptoms to root cause quickly.

Incident response should start with stabilization. Confirm impact, reduce blast radius, and preserve critical functionality. Only then should deeper diagnosis begin. Good engineers compare current behavior to baselines, inspect recent config changes, look for saturation or dependency issues, and form falsifiable hypotheses. A strong retrospective produces action items tied to detection, prevention, and recovery rather than vague calls to "be more careful".

## Authentication, Authorization, And Multi-Tenancy
Authentication proves who the caller is. Authorization determines what they can do. The two are related but distinct. Service boundaries should validate tokens, propagate identity safely, and enforce least privilege. Role based access control is simple and common, but attribute based access control can offer more flexibility when policies depend on resource ownership or environment context.

Multi-tenant systems must decide how strongly tenant data is isolated. Isolation can exist at the application row level, schema level, or database level. Each approach trades operational simplicity against blast radius and compliance posture. Candidates should be able to reason about tenant scoped indexes, noisy neighbor effects, and auditability.

## Scalability And Performance Debugging
Backend scalability is usually constrained by a few bottlenecks: database throughput, network fan out, lock contention, hot keys, or inefficient serialization. Performance debugging starts with measurement. Look at request percentiles, error correlation, queueing delay, cache behavior, and database wait events. Do not guess before measuring.

An increase in p99 latency without a deploy may point to traffic shifts, data growth, dependency degradation, or infrastructure saturation. Engineers should segment latency by endpoint, dependency, and request shape. Useful mitigation steps include load shedding, query optimization, connection pool tuning, async offloading, rate limiting, and capacity changes. The best answers explain both investigation order and why each signal matters.

## System Design Tradeoffs
There is rarely one correct architecture. Good backend design is about explicit tradeoffs. For example, synchronous RPC simplifies consistency reasoning but increases coupling and tail latency. Event driven workflows improve isolation and elasticity but complicate debugging and data freshness. Monoliths can move faster early on, while service decomposition becomes valuable when team boundaries, scaling needs, or fault isolation justify the operational overhead.

Design interviews are strongest when the candidate states assumptions, identifies invariants, and chooses the simplest architecture that satisfies them. The explanation should include data flow, failure handling, capacity constraints, and how the service would be operated over time.
