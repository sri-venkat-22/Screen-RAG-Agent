# Data Engineer Knowledge Base

## Pipeline Design
Data pipelines move information from source systems into reliable analytical or operational stores. Good design defines freshness requirements, data contracts, failure handling, backfills, ownership, and observability. Batch systems optimize for throughput and reproducibility, while streaming systems optimize for low latency and event-time correctness. Strong candidates explain why a workload needs batch, streaming, or a hybrid architecture.

## Data Modeling
Analytics models should match query patterns and business definitions. Star schemas improve understandability and reuse when facts and dimensions are stable. Wide denormalized tables can improve performance for specific dashboards but may duplicate logic. Good data engineers know how to manage slowly changing dimensions, partitioning, clustering, and semantic consistency across teams.

## Quality, Lineage, And Contracts
Data quality checks should cover freshness, volume, schema, null rates, accepted ranges, uniqueness, referential integrity, and business rules. Lineage helps teams understand downstream impact when a source changes. Data contracts make producer expectations explicit and reduce accidental breakage. Strong answers include alerting strategy and how to prioritize incidents based on consumer impact.

## Orchestration And Backfills
Orchestration tools coordinate dependencies, retries, scheduling, and visibility. Backfills must be safe, idempotent, and observable because they can overload warehouses or overwrite trusted outputs. Good candidates describe how to isolate backfill runs, validate results, and communicate changes to downstream consumers.

## Feature Stores And ML Data
ML data platforms need online and offline feature parity, point-in-time correctness, training set reproducibility, and low-latency serving. Feature freshness, skew detection, and lineage are especially important. Strong candidates can reason about when to compute features batch, stream, or on request.

