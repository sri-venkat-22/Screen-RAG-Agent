from __future__ import annotations

import re
from statistics import mean

from backend.app.schemas import AnswerEvaluation, InterviewQuestion, InterviewTurn, SessionInsights, SignalScore

STRUCTURE_CUES = ("first", "second", "third", "because", "tradeoff", "finally", "step", "then")
TECHNICAL_SIGNAL_TERMS = (
    "api",
    "cache",
    "chunk",
    "chunking",
    "database",
    "embedding",
    "embeddings",
    "evaluation",
    "fallback",
    "index",
    "latency",
    "metric",
    "monitoring",
    "observability",
    "pipeline",
    "precision",
    "queue",
    "recall",
    "retrieval",
    "reranking",
    "rollback",
    "schema",
    "test",
    "throughput",
    "validation",
)
OPERATIONAL_CUES = (
    "failure",
    "fallback",
    "monitor",
    "rollback",
    "tradeoff",
    "validate",
    "metric",
    "test",
)


def evaluate_answer(question: InterviewQuestion, answer_text: str) -> AnswerEvaluation:
    normalized = answer_text.strip()
    normalized_lower = normalized.lower()
    words = re.findall(r"\b[\w.+/#-]+\b", normalized_lower)
    word_count = len(words)
    unique_words = set(words)
    expected_terms = _expected_terms(question)
    matched_terms = [
        term
        for term in expected_terms
        if (" " in term and term in normalized_lower) or term in unique_words
    ]

    exact_coverage = min(100, round((len(matched_terms) / max(len(expected_terms), 1)) * 100))
    technical_matches = [
        term
        for term in TECHNICAL_SIGNAL_TERMS
        if (" " in term and term in normalized_lower) or term in unique_words
    ]
    technical_coverage = min(100, len(technical_matches) * 14)
    keyword_coverage = max(exact_coverage, technical_coverage)
    clarity = min(
        100,
        40
        + sum(8 for cue in STRUCTURE_CUES if cue in normalized.lower())
        + min(20, normalized.count("\n") * 4),
    )
    specificity = min(
        100,
        35
        + min(25, len(re.findall(r"\b\d+(?:ms|s|%|x|m|k)?\b", normalized.lower())) * 8)
        + (15 if "for example" in normalized.lower() or "for instance" in normalized.lower() else 0)
        + (10 if any(token in normalized.lower() for token in ("latency", "accuracy", "throughput", "recall", "precision")) else 0),
    )
    operational_depth = sum(1 for cue in OPERATIONAL_CUES if cue in normalized_lower)
    depth = min(
        100,
        20
        + min(60, int(word_count * 0.7))
        + (10 if word_count >= 120 else 0)
        + min(15, operational_depth * 4),
    )

    score = round(keyword_coverage * 0.3 + clarity * 0.2 + specificity * 0.22 + depth * 0.28)
    strengths: list[str] = []
    improvements: list[str] = []

    if keyword_coverage >= 60:
        strengths.append(f"Grounded the answer in relevant concepts for {question.focus_topic}.")
    else:
        improvements.append(f"Anchor the answer more explicitly in {question.focus_topic} concepts.")

    if specificity >= 65:
        strengths.append("Included concrete implementation or metric-level details.")
    else:
        improvements.append("Add examples, metrics, or operational details to strengthen the answer.")

    if clarity >= 65:
        strengths.append("Structured the response in a way that is easy to follow.")
    else:
        improvements.append("Use a clearer structure: setup, decision, tradeoff, and validation.")

    if depth < 55:
        improvements.append("Go deeper on failure modes, tradeoffs, and validation steps.")

    evidence = []
    if matched_terms:
        evidence.append(f"Matched concepts: {', '.join(matched_terms[:4])}")
    if technical_matches:
        evidence.append(f"Technical signals: {', '.join(technical_matches[:4])}")
    evidence.append(f"Answer length: {word_count} words")
    if specificity >= 65:
        evidence.append("Included concrete evidence or measurable criteria.")

    return AnswerEvaluation(
        score=score,
        keyword_coverage=keyword_coverage,
        clarity=clarity,
        specificity=specificity,
        depth=depth,
        evidence=evidence,
        strengths=strengths[:3],
        improvements=improvements[:3],
    )


def build_session_insights(turns: list[InterviewTurn]) -> SessionInsights:
    scores = [turn.evaluation.score for turn in turns]
    grounding = [turn.evaluation.keyword_coverage for turn in turns]
    clarity = [turn.evaluation.clarity for turn in turns]
    specificity = [turn.evaluation.specificity for turn in turns]
    depth = [turn.evaluation.depth for turn in turns]

    strengths = _dedupe(
        strength
        for turn in turns
        for strength in turn.evaluation.strengths
        if strength
    )[:4]
    improvements = _dedupe(
        item
        for turn in turns
        for item in turn.evaluation.improvements
        if item
    )[:4]

    overall = round(mean(scores)) if scores else 0
    recommendation = (
        "Strong signal. Advance to the next technical round."
        if overall >= 75
        else "Mixed signal. Move forward with a focused follow-up on weaker areas."
        if overall >= 58
        else "Needs more evidence. Re-screen with emphasis on fundamentals and applied reasoning."
    )

    return SessionInsights(
        overall_score=overall,
        strengths=strengths or ["Completed the full interview with useful signal."],
        improvements=improvements or ["Push further on depth and operational tradeoffs."],
        signal=[
            SignalScore(label="Role Fit", score=round(mean(scores)) if scores else 0),
            SignalScore(label="Grounding", score=round(mean(grounding)) if grounding else 0),
            SignalScore(label="Communication", score=round(mean(clarity)) if clarity else 0),
            SignalScore(label="Problem Solving", score=round(mean(depth)) if depth else 0),
            SignalScore(label="Specificity", score=round(mean(specificity)) if specificity else 0),
        ],
        recommendation=recommendation,
    )


def _expected_terms(question: InterviewQuestion) -> list[str]:
    terms = {
        question.focus_topic.lower(),
        *[source.topic.lower() for source in question.sources],
    }
    for source in question.sources:
        for keyword in source.metadata.get("keywords", [])[:5]:
            terms.add(str(keyword).lower())
    filtered: list[str] = []
    for term in terms:
        if not term:
            continue
        if " " not in term or len(term.split()) <= 3:
            filtered.append(term)
        if " " in term:
            filtered.extend(token for token in term.split() if len(token) > 3)
    return filtered


def _dedupe(items):
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
