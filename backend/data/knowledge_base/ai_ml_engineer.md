# AI/ML Engineer Knowledge Base

## Role Expectations
An AI/ML engineer is expected to translate product goals into data and model systems that are measurable, observable, and maintainable. The role is not only about training a model. It includes shaping the problem definition, defining evaluation criteria, instrumenting inference behavior, handling tradeoffs between cost and quality, and creating rollback paths when models regress. Strong candidates explain how their modeling choices interact with latency budgets, feature freshness, data drift, and incident response.

## Problem Framing And Evaluation
Every ML or LLM system begins with a target decision. Before training or prompting anything, define the prediction or generation task, the user behavior being optimized, and the failure modes that are unacceptable. Good evaluation strategy connects offline metrics to real user outcomes. For a classifier this may mean precision, recall, calibration, and error slicing. For a retrieval system it may mean recall at k, mean reciprocal rank, grounding quality, and downstream answer usefulness. For a generative system it may mean factuality, completeness, style adherence, latency, and cost per request.

Offline evaluation is never sufficient on its own. It is useful for fast iteration, regression testing, and model comparison, but it can drift away from product value if the evaluation set becomes stale or narrow. Strong systems pair offline evaluation with online monitoring, human review, and guardrail metrics. A healthy deployment process typically includes fixed benchmark sets, canary traffic, shadow testing, and rollback criteria. Candidates should be able to describe why a metric is chosen and what blind spots remain.

## Feature Engineering And Data Quality
High quality models depend on high quality data. Feature engineering is often less about exotic transforms and more about defining stable, leak free, interpretable signals. Leakage occurs when the training signal contains information that would not exist at inference time. A candidate should recognize common leakage sources such as target encoded aggregates computed over future data, features derived from post outcome events, or improperly joined tables.

Data quality checks should cover freshness, null rates, cardinality shifts, schema changes, and semantic validity. In production systems, these checks are best automated and tied to alerts. Training data should also be versioned so that a model can be reproduced. When debugging performance regressions, always inspect label definitions, feature distribution changes, and serving skew between offline and online pipelines.

## Retrieval Augmented Generation Foundations
RAG systems aim to ground model outputs in retrieved evidence. A typical pipeline has document ingestion, chunking, embedding generation, indexing, query construction, retrieval, optional reranking, answer generation, and post generation validation. The purpose of retrieval is not merely to find similar text. It is to surface the minimum set of evidence needed for the model to answer accurately without hallucinating or omitting critical detail.

Document chunking is a core design decision. Small chunks improve retrieval precision but can lose context. Large chunks preserve context but can dilute relevance and waste context window budget. Practical chunking strategies use semantic boundaries such as headings, sections, and paragraphs, then apply overlap to reduce fragmentation. Good chunk metadata includes source, title, topic, and sometimes document hierarchy so the system can preserve provenance.

Embedding model choice should reflect the domain and retrieval workload. Smaller embedding models are cheaper and faster but may underperform on nuanced technical content. General purpose embeddings can work surprisingly well for many cases, but domain tuned models may help when vocabulary is specialized. Engineers should understand that embeddings can drift as content or user queries change, so retrieval quality needs periodic evaluation instead of one time benchmarking.

## Query Construction And Retrieval Quality
A weak query often leads to weak retrieval even when the index is correct. Query construction can combine user intent, profile information, structured filters, and expansion terms. In an interview system, the resume and target role can be used to derive evaluation topics and retrieve focused technical context. Query expansion might add synonyms or related concepts such as converting "vector store" into "embedding index, ANN search, metadata filtering, reranking".

Retrieval quality should be evaluated independently from the language model. Common diagnostics include checking whether the relevant chunk appears in the top k results, how often retrieved chunks disagree with each other, and whether the retrieved evidence actually contains the facts needed to answer. Hybrid retrieval combines lexical search with semantic search. Reranking can improve precision by ordering retrieved chunks with a more expensive cross encoder or a strong scoring heuristic.

## Reranking And Context Assembly
The first retrieval pass usually favors recall. Reranking then improves precision. A reranker can consider lexical overlap, semantic similarity, chunk position, source authority, and structured metadata such as role or topic. Context assembly should also deduplicate chunks and avoid flooding the model with near identical passages. When multiple chunks overlap, select the ones that provide complementary evidence.

Prompt assembly should make provenance clear. Instead of dumping raw chunks, many systems format context as titled snippets with source labels. This helps both the model and the developer during debugging. If the model still hallucinates despite strong retrieval, inspect whether the prompt clearly instructs the model to stay within the evidence and whether the retrieved chunks actually answer the question at the right level of abstraction.

## Hallucination Mitigation And Guardrails
Hallucinations usually come from one of three places: missing evidence, poor instructions, or an answer synthesis step that overgeneralizes. Mitigation techniques include stronger retrieval, reranking, response constraints, answer abstention, and post answer validation. Systems should prefer "I do not have enough evidence" over fabricated certainty. Guardrails can also check for citation presence, unsupported claims, unsafe content, or missing mandatory fields.

In production, hallucination management is not just a prompt problem. It is an observability problem. Teams should store the query, retrieved chunks, prompt version, model version, and generated output. That trace makes failures explainable and enables regression analysis after model or prompt changes.

## Model Deployment And Monitoring
Production ML systems should be instrumented end to end. At minimum, log request volume, latency, error rate, model version, input size, output size, and business outcome proxies. For retrieval systems, add retrieval hit rates, top k overlap, reranker behavior, and empty retrieval counts. For model quality, monitor drift in embeddings or features, response distribution changes, calibration shifts, and human flagged errors.

Safe rollout patterns include canary deployment, shadow deployment, and feature flags. A model upgrade should be reversible. If a new model improves average quality but introduces severe edge case failures, the system needs circuit breakers or scoped rollout controls. Candidates should be able to explain how they would compare models, protect users during rollout, and debug regressions without losing traceability.

## Overfitting, Underfitting, And Error Analysis
A model with high training performance and low validation performance is usually overfitting, but the root cause can vary. Possible causes include overly expressive models, too little data, data leakage, distribution mismatch, or brittle feature engineering. Strong answers go beyond naming regularization techniques and discuss data splits, leakage checks, label quality, simplification, and targeted augmentation.

Error analysis should be systematic. Slice failures by cohort, source, query type, input length, and recency. In RAG, inspect both retrieval and generation separately. A bad final answer may come from missing evidence, but it can also come from good evidence that was poorly synthesized. Debugging is faster when the pipeline is decomposed into retrievable artifacts rather than treated as a single opaque LLM call.

## Experimentation And Iteration
Experimentation in AI systems should be incremental and traceable. Change one component at a time when possible: chunk size, overlap, embedding model, retrieval parameters, reranking logic, prompt policy, or generation model. Record the change, the benchmark result, and the tradeoff. This discipline prevents accidental regressions and helps explain why a system improved.

For interview systems specifically, the question generation logic should remain grounded in retrieved content and candidate context. The goal is not novelty for its own sake. The goal is producing questions that are role relevant, candidate aware, and supported by evidence from the knowledge base. A good engineer can explain how each generated question traces back to a topic, a query, and a supporting set of chunks.

