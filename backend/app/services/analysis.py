from __future__ import annotations

import json
import re
from statistics import mean
from typing import Any

from backend.app.config import get_settings
from backend.app.roles import RoleDefinition
from backend.app.schemas import (
    AnswerEvaluation,
    InterviewQuestion,
    InterviewTurn,
    ResumeProfile,
    SessionInsights,
    SignalScore,
)

STRUCTURE_CUES = (
    "first",
    "second",
    "third",
    "because",
    "tradeoff",
    "trade-off",
    "finally",
    "step",
    "then",
    "for example",
)
HEDGE_CUES = ("maybe", "i guess", "sort of", "kind of", "not sure", "probably", "basically")
QUESTION_DIMENSION_CUES = {
    "tradeoff": ("tradeoff", "trade-off", "alternative", "compare", "choose", "decision"),
    "validation": ("test", "validate", "metric", "measure", "benchmark", "experiment"),
    "debugging": ("debug", "inspect", "root cause", "logs", "trace", "hypothesis"),
    "scale": ("scale", "latency", "throughput", "load", "p95", "p99", "capacity"),
    "security": ("security", "iam", "auth", "encrypt", "permission", "owasp", "least privilege"),
    "operations": ("monitor", "alert", "rollback", "deploy", "canary", "observability"),
    "implementation": ("api", "schema", "index", "cache", "queue", "state", "component", "pipeline"),
}
TECHNICAL_SIGNALS = tuple(sorted({term for terms in QUESTION_DIMENSION_CUES.values() for term in terms}))
_SHARED_SENTENCE_MODEL = None


class LocalEvaluatorLLM:
    _shared_pipelines: dict[str, Any] = {}
    _shared_unavailable_models: set[str] = set()

    def __init__(self) -> None:
        self.settings = get_settings()

    def evaluate(self, prompt: str) -> dict[str, Any] | None:
        if not self.settings.enable_local_answer_evaluation:
            return None
        for model_name in self._model_candidates():
            if model_name in LocalEvaluatorLLM._shared_unavailable_models:
                continue
            try:
                generator = self._pipeline_for_model(model_name)
                if generator is None:
                    continue
                output = generator(
                    prompt,
                    max_new_tokens=self.settings.answer_evaluator_max_new_tokens,
                    do_sample=False,
                    return_full_text=False,
                    pad_token_id=getattr(generator.tokenizer, "eos_token_id", None),
                )[0]
                return _parse_json_object(str(output.get("generated_text", "")))
            except Exception:
                LocalEvaluatorLLM._shared_unavailable_models.add(model_name)
        return None

    def _pipeline_for_model(self, model_name: str):
        if model_name in LocalEvaluatorLLM._shared_pipelines:
            return LocalEvaluatorLLM._shared_pipelines[model_name]
        if self.settings.answer_evaluator_local_files_only and not self._model_is_cached(model_name):
            LocalEvaluatorLLM._shared_unavailable_models.add(model_name)
            return None
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            local_files_only=self.settings.answer_evaluator_local_files_only,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            local_files_only=self.settings.answer_evaluator_local_files_only,
        )
        generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
        LocalEvaluatorLLM._shared_pipelines[model_name] = generator
        return generator

    def _model_candidates(self) -> list[str]:
        return _dedupe(
            [
                self.settings.answer_evaluator_model_name,
                *self.settings.answer_evaluator_fallback_model_names,
            ]
        )

    def _model_is_cached(self, model_name: str) -> bool:
        try:
            from huggingface_hub import try_to_load_from_cache

            cached_config = try_to_load_from_cache(model_name, "config.json")
            return isinstance(cached_config, str)
        except Exception:
            return False


def evaluate_answer(
    question: InterviewQuestion,
    answer_text: str,
    profile: ResumeProfile | None = None,
    role: RoleDefinition | None = None,
) -> AnswerEvaluation:
    cleaned_answer = _clean_answer(answer_text)
    expected_answer = _expected_answer(question, profile, role)
    llm_payload = LocalEvaluatorLLM().evaluate(
        _build_evaluator_prompt(question, cleaned_answer, expected_answer, profile, role)
    )
    if llm_payload:
        return _evaluation_from_llm_payload(llm_payload, question, cleaned_answer, expected_answer)
    return _semantic_rubric_evaluation(question, cleaned_answer, expected_answer, profile, role)


def build_session_insights(turns: list[InterviewTurn]) -> SessionInsights:
    scores = [turn.evaluation.score for turn in turns]
    technical = [_metric(turn.evaluation, "technical_depth", "depth") for turn in turns]
    communication = [_metric(turn.evaluation, "communication", "clarity") for turn in turns]
    problem_solving = [
        _metric(turn.evaluation, "practical_reasoning", "specificity") for turn in turns
    ]
    correctness = [_metric(turn.evaluation, "correctness", "keyword_coverage") for turn in turns]

    strengths = _dedupe(
        strength for turn in turns for strength in turn.evaluation.strengths if strength
    )[:5]
    weaknesses = _dedupe(
        weakness for turn in turns for weakness in turn.evaluation.weaknesses if weakness
    )[:5]
    improvements = _dedupe(
        item
        for turn in turns
        for item in [*turn.evaluation.improvements, turn.evaluation.improvement_suggestion]
        if item
    )[:5]
    skill_improvements = _dedupe(
        item
        for turn in turns
        for item in [*turn.evaluation.missing_concepts, *turn.evaluation.improvements]
        if item
    )[:6]

    overall = round(mean(scores)) if scores else 0
    technical_rating = round(mean(technical)) if technical else 0
    communication_rating = round(mean(communication)) if communication else 0
    problem_solving_rating = round(mean(problem_solving)) if problem_solving else 0
    readiness_level = _readiness_level(overall, technical_rating, communication_rating)
    recommendation = _recommendation(overall, readiness_level)

    return SessionInsights(
        overall_score=overall,
        strengths=strengths or ["Gave enough signal to complete a technical screen."],
        weaknesses=weaknesses or ["No severe weakness surfaced, but deeper follow-up is still useful."],
        improvements=improvements or ["Give more concrete examples, tradeoffs, and validation details."],
        signal=[
            SignalScore(label="Technical Rating", score=technical_rating),
            SignalScore(label="Communication Rating", score=communication_rating),
            SignalScore(label="Problem Solving Rating", score=problem_solving_rating),
            SignalScore(label="Concept Coverage", score=round(mean(correctness)) if correctness else 0),
        ],
        recommendation=recommendation,
        technical_rating=technical_rating,
        communication_rating=communication_rating,
        problem_solving_rating=problem_solving_rating,
        recommended_skill_improvements=skill_improvements
        or ["Practice explaining architecture, failure modes, metrics, and validation."],
        readiness_level=readiness_level,
    )


def _build_evaluator_prompt(
    question: InterviewQuestion,
    answer_text: str,
    expected_answer: str,
    profile: ResumeProfile | None,
    role: RoleDefinition | None,
) -> str:
    source_context = [
        {
            "title": source.title,
            "topic": source.topic,
            "excerpt": source.excerpt,
            "keywords": _metadata_keywords(source.metadata),
        }
        for source in question.sources[:4]
    ]
    resume_context = {
        "summary": profile.summary if profile else "",
        "skills": profile.skills[:12] if profile else [],
        "projects": [project.model_dump() for project in profile.projects[:4]] if profile else [],
        "experience": [item.model_dump() for item in profile.work_experience[:3]] if profile else [],
    }
    role_context = {
        "role": role.label if role else "",
        "topics": list(role.core_topics[:10]) if role else [],
    }
    return (
        "You are a senior technical interviewer evaluating one candidate answer.\n"
        "Score the answer semantically, not by keyword matching. Be fair but strict.\n"
        "Validate technical correctness, conceptual understanding, completeness, clarity, practical reasoning, "
        "confidence, and communication quality.\n"
        "Return JSON only with these keys: score, correctness, technical_depth, completeness, clarity, "
        "practical_reasoning, communication, confidence, expected_answer, evaluation_summary, strengths, "
        "weaknesses, missing_concepts, improvement_suggestion.\n"
        "Scores are integers from 0 to 100. Keep feedback recruiter-like and concise.\n\n"
        f"Role context: {json.dumps(role_context, ensure_ascii=True)}\n"
        f"Resume context: {json.dumps(resume_context, ensure_ascii=True)[:4200]}\n"
        f"Retrieved knowledge: {json.dumps(source_context, ensure_ascii=True)[:3600]}\n"
        f"Question: {question.prompt}\n"
        f"Expected answer draft: {expected_answer}\n"
        f"Candidate answer: {answer_text[:5000]}\n"
    )


def _evaluation_from_llm_payload(
    payload: dict[str, Any],
    question: InterviewQuestion,
    answer_text: str,
    fallback_expected_answer: str,
) -> AnswerEvaluation:
    score = _score(payload.get("score"))
    correctness = _score(payload.get("correctness"))
    technical_depth = _score(payload.get("technical_depth"))
    completeness = _score(payload.get("completeness"))
    clarity = _score(payload.get("clarity"))
    practical_reasoning = _score(payload.get("practical_reasoning"))
    communication = _score(payload.get("communication"))
    confidence = _score(payload.get("confidence"))
    expected_answer = _clean_answer(str(payload.get("expected_answer") or fallback_expected_answer))
    strengths = _string_list(payload.get("strengths"))[:4]
    weaknesses = _string_list(payload.get("weaknesses"))[:4]
    missing_concepts = _string_list(payload.get("missing_concepts"))[:6]
    improvement = _clean_answer(str(payload.get("improvement_suggestion") or "Add concrete tradeoffs, examples, and validation details."))
    summary = _clean_answer(str(payload.get("evaluation_summary") or _fallback_summary(score, question)))

    if not score:
        score = round(
            correctness * 0.34
            + technical_depth * 0.2
            + completeness * 0.15
            + practical_reasoning * 0.15
            + communication * 0.11
            + confidence * 0.05
        )
    if not strengths and score >= 60:
        strengths = ["Shows partial understanding of the question and role context."]
    if not weaknesses and score < 80:
        weaknesses = ["Needs sharper technical detail and validation reasoning."]

    return AnswerEvaluation(
        score=_score(score),
        keyword_coverage=correctness,
        clarity=clarity or communication,
        specificity=practical_reasoning,
        depth=technical_depth,
        correctness=correctness,
        technical_depth=technical_depth,
        completeness=completeness,
        practical_reasoning=practical_reasoning,
        communication=communication or clarity,
        confidence=confidence,
        expected_answer=expected_answer,
        evaluation_summary=summary,
        missing_concepts=missing_concepts,
        weaknesses=weaknesses,
        improvement_suggestion=improvement,
        evidence=[
            "Evaluated with local LLM semantic rubric.",
            f"Answer length: {len(_tokens(answer_text))} words.",
        ],
        strengths=strengths,
        improvements=[improvement],
    )


def _semantic_rubric_evaluation(
    question: InterviewQuestion,
    answer_text: str,
    expected_answer: str,
    profile: ResumeProfile | None,
    role: RoleDefinition | None,
) -> AnswerEvaluation:
    words = _tokens(answer_text)
    word_count = len(words)
    concepts = _expected_concepts(question, profile, role)
    semantic_alignment = _semantic_similarity(answer_text, expected_answer)
    concept_coverage = _concept_coverage(answer_text, concepts)
    correctness = round(semantic_alignment * 0.58 + concept_coverage * 0.42)
    technical_depth = _technical_depth_score(answer_text, word_count)
    completeness = _completeness_score(question.prompt, answer_text, word_count)
    practical_reasoning = _practical_reasoning_score(answer_text)
    communication = _communication_score(answer_text, word_count)
    confidence = _confidence_score(answer_text, word_count)

    if word_count < 18:
        correctness = min(correctness, 35)
        technical_depth = min(technical_depth, 30)
        completeness = min(completeness, 28)
        practical_reasoning = min(practical_reasoning, 25)
    if _looks_like_no_answer(answer_text):
        correctness = min(correctness, 20)
        technical_depth = min(technical_depth, 18)
        completeness = min(completeness, 18)

    score = round(
        correctness * 0.34
        + technical_depth * 0.2
        + completeness * 0.15
        + practical_reasoning * 0.15
        + communication * 0.11
        + confidence * 0.05
    )
    missing = _missing_concepts(answer_text, concepts)
    strengths = _strengths(correctness, technical_depth, communication, practical_reasoning)
    weaknesses = _weaknesses(correctness, technical_depth, completeness, practical_reasoning, communication)
    improvement = _improvement_suggestion(missing, weaknesses, question.focus_topic)

    return AnswerEvaluation(
        score=_score(score),
        keyword_coverage=_score(concept_coverage),
        clarity=communication,
        specificity=practical_reasoning,
        depth=technical_depth,
        correctness=correctness,
        technical_depth=technical_depth,
        completeness=completeness,
        practical_reasoning=practical_reasoning,
        communication=communication,
        confidence=confidence,
        expected_answer=expected_answer,
        evaluation_summary=_fallback_summary(score, question),
        missing_concepts=missing[:6],
        weaknesses=weaknesses[:4],
        improvement_suggestion=improvement,
        evidence=[
            f"Semantic alignment: {semantic_alignment}/100.",
            f"Concept coverage: {concept_coverage}/100.",
            f"Answer length: {word_count} words.",
        ],
        strengths=strengths[:4],
        improvements=[improvement],
    )


def _expected_answer(
    question: InterviewQuestion,
    profile: ResumeProfile | None,
    role: RoleDefinition | None,
) -> str:
    concepts = _expected_concepts(question, profile, role)
    evidence = _best_source_sentences(question)
    project_names = [project.name for project in profile.projects[:3]] if profile else []
    role_label = role.label if role else "the target role"
    context = (
        f"in the context of {', '.join(project_names[:2])}"
        if project_names
        else f"for {role_label}"
    )
    concept_text = ", ".join(concepts[:6]) if concepts else question.focus_topic
    evidence_text = " ".join(evidence[:2])
    expected = (
        f"A strong answer should explain {question.focus_topic} {context}, cover {concept_text}, "
        "and connect the concept to an implementation or architecture decision. It should discuss the "
        "main tradeoffs, likely failure modes, how the approach would be tested or measured, and what "
        "monitoring or rollback plan would make it production-ready."
    )
    if evidence_text:
        expected += f" Relevant knowledge context: {evidence_text}"
    return _compact(expected, 900)


def _expected_concepts(
    question: InterviewQuestion,
    profile: ResumeProfile | None,
    role: RoleDefinition | None,
) -> list[str]:
    concepts: list[str] = [question.focus_topic]
    question_lower = question.prompt.lower()
    concepts.extend(signal for signal in TECHNICAL_SIGNALS if signal in question_lower)
    concepts.extend(
        token
        for token in _tokens(question.prompt)
        if len(token) > 4
        and token
        not in {
            "would",
            "could",
            "should",
            "under",
            "about",
            "explain",
            "context",
            "question",
        }
    )
    concepts.extend(source.topic for source in question.sources[:4])
    for source in question.sources[:4]:
        concepts.extend(str(item) for item in _metadata_keywords(source.metadata)[:6])
    if role:
        concepts.extend(role.core_topics[:8])
    if profile:
        resume_terms = [
            *profile.skills,
            *profile.technologies,
            *profile.frameworks,
            *profile.tools,
            *profile.domain_expertise,
        ]
        concepts.extend(term for term in resume_terms if term.lower() in question_lower)
    return _dedupe(_normalize_concept(item) for item in concepts if item)[:18]


def _best_source_sentences(question: InterviewQuestion) -> list[str]:
    sentences: list[tuple[str, int]] = []
    query_terms = set(_tokens(f"{question.prompt} {question.focus_topic}"))
    for source in question.sources[:4]:
        for sentence in re.split(r"(?<=[.!?])\s+", source.excerpt):
            sentence = sentence.strip()
            if len(sentence.split()) < 8 or _front_matter(sentence):
                continue
            score = sum(1 for token in query_terms if token in sentence.lower())
            sentences.append((sentence, score))
    return [item for item, _ in sorted(sentences, key=lambda pair: pair[1], reverse=True)[:3]]


def _semantic_similarity(answer_text: str, expected_answer: str) -> int:
    if not answer_text.strip() or not expected_answer.strip():
        return 0
    try:
        from sentence_transformers import SentenceTransformer

        global _SHARED_SENTENCE_MODEL
        if _SHARED_SENTENCE_MODEL is None:
            _SHARED_SENTENCE_MODEL = SentenceTransformer(get_settings().embedding_model_name)
        model = _SHARED_SENTENCE_MODEL
        vectors = model.encode([answer_text, expected_answer], normalize_embeddings=True)
        similarity = float(sum(float(a) * float(b) for a, b in zip(vectors[0], vectors[1])))
        return _score(round((similarity + 1.0) * 50))
    except Exception:
        answer_terms = set(_tokens(answer_text))
        expected_terms = set(_tokens(expected_answer))
        if not expected_terms:
            return 0
        return _score(round(len(answer_terms & expected_terms) / len(expected_terms) * 100))


def _concept_coverage(answer_text: str, concepts: list[str]) -> int:
    if not concepts:
        return 0
    answer_lower = answer_text.lower()
    hits = 0
    weighted_total = 0
    for concept in concepts:
        weight = 2 if " " in concept else 1
        weighted_total += weight
        tokens = [token for token in _tokens(concept) if len(token) > 3]
        direct = concept.lower() in answer_lower
        partial = bool(tokens) and sum(1 for token in tokens if _token_present(token, answer_lower)) >= max(1, len(tokens) // 2)
        if direct or partial:
            hits += weight
    return _score(round(hits / max(weighted_total, 1) * 100))


def _technical_depth_score(answer_text: str, word_count: int) -> int:
    lower = answer_text.lower()
    signal_hits = sum(1 for term in TECHNICAL_SIGNALS if term in lower)
    design_hits = sum(
        1
        for term in ("architecture", "data flow", "schema", "contract", "edge case", "failure mode")
        if term in lower
    )
    return _score(22 + min(34, word_count // 3) + min(28, signal_hits * 4) + min(16, design_hits * 5))


def _completeness_score(question_text: str, answer_text: str, word_count: int) -> int:
    lower_question = question_text.lower()
    lower_answer = answer_text.lower()
    requested_dimensions = [
        label
        for label, cues in QUESTION_DIMENSION_CUES.items()
        if any(cue in lower_question for cue in cues)
    ]
    if not requested_dimensions:
        requested_dimensions = ["implementation", "validation"]
    covered = 0
    for label in requested_dimensions:
        if any(cue in lower_answer for cue in QUESTION_DIMENSION_CUES[label]):
            covered += 1
    coverage = round(covered / len(requested_dimensions) * 100)
    length_bonus = 12 if word_count >= 80 else 6 if word_count >= 45 else 0
    return _score(round(coverage * 0.78 + length_bonus))


def _practical_reasoning_score(answer_text: str) -> int:
    lower = answer_text.lower()
    group_hits = sum(
        1
        for cues in QUESTION_DIMENSION_CUES.values()
        if any(cue in lower for cue in cues)
    )
    metric_hits = len(re.findall(r"\b\d+(?:ms|s|%|x|k|m|gb|mb|qps|rps)?\b", lower))
    return _score(25 + min(48, group_hits * 9) + min(18, metric_hits * 5) + (9 if "example" in lower else 0))


def _communication_score(answer_text: str, word_count: int) -> int:
    lower = answer_text.lower()
    structure = sum(1 for cue in STRUCTURE_CUES if cue in lower)
    sentence_count = max(1, len(re.findall(r"[.!?]", answer_text)))
    length_score = 25 if 55 <= word_count <= 260 else 15 if word_count >= 25 else 5
    ramble_penalty = 12 if word_count > 360 and sentence_count < 4 else 0
    return _score(35 + min(28, structure * 6) + length_score - ramble_penalty)


def _confidence_score(answer_text: str, word_count: int) -> int:
    lower = answer_text.lower()
    hedges = sum(lower.count(cue) for cue in HEDGE_CUES)
    concrete_verbs = sum(
        1
        for verb in ("measure", "verify", "implement", "isolate", "compare", "monitor", "rollback")
        if verb in lower
    )
    return _score(52 + min(28, concrete_verbs * 5) + min(15, word_count // 16) - min(30, hedges * 7))


def _strengths(correctness: int, depth: int, communication: int, practical: int) -> list[str]:
    strengths: list[str] = []
    if correctness >= 70:
        strengths.append("Aligned the answer with the core technical concept.")
    if depth >= 70:
        strengths.append("Included meaningful technical detail beyond surface-level definitions.")
    if practical >= 70:
        strengths.append("Connected the answer to testing, operations, metrics, or failure handling.")
    if communication >= 70:
        strengths.append("Communicated the reasoning in a structured, readable way.")
    return strengths or ["Provided a usable starting point but needs more technical precision."]


def _weaknesses(correctness: int, depth: int, completeness: int, practical: int, communication: int) -> list[str]:
    weaknesses: list[str] = []
    if correctness < 60:
        weaknesses.append("Technical correctness is incomplete or only loosely connected to the question.")
    if depth < 60:
        weaknesses.append("Technical depth is thin; the answer needs architecture, edge cases, and tradeoffs.")
    if completeness < 60:
        weaknesses.append("The answer misses parts of what the interviewer asked for.")
    if practical < 60:
        weaknesses.append("Practical reasoning is underdeveloped; add tests, metrics, monitoring, and failure handling.")
    if communication < 55:
        weaknesses.append("Communication needs clearer structure and more direct reasoning.")
    return weaknesses


def _improvement_suggestion(missing: list[str], weaknesses: list[str], focus_topic: str) -> str:
    if missing:
        return f"Re-answer with {', '.join(missing[:3])}, then tie those concepts to a concrete design decision and validation plan."
    if weaknesses:
        return f"Strengthen the answer on {focus_topic} with a specific example, tradeoff, metric, and failure-handling step."
    return "Add one measurable example and one explicit tradeoff to make the answer interview-ready."


def _missing_concepts(answer_text: str, concepts: list[str]) -> list[str]:
    lower = answer_text.lower()
    missing: list[str] = []
    for concept in concepts:
        tokens = [token for token in _tokens(concept) if len(token) > 3]
        if concept.lower() in lower:
            continue
        if tokens and any(_token_present(token, lower) for token in tokens):
            continue
        missing.append(concept)
    return missing


def _parse_json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _metric(evaluation: AnswerEvaluation, primary: str, fallback: str) -> int:
    value = int(getattr(evaluation, primary, 0) or 0)
    return value or int(getattr(evaluation, fallback, 0) or 0)


def _readiness_level(overall: int, technical: int, communication: int) -> str:
    if overall >= 85 and technical >= 80:
        return "Ready for advanced technical round"
    if overall >= 75 and technical >= 70:
        return "Ready for next round"
    if overall >= 60 and communication >= 60:
        return "Borderline: needs targeted follow-up"
    return "Not interview-ready yet"


def _recommendation(overall: int, readiness: str) -> str:
    if overall >= 82:
        return f"{readiness}. Strong signal; advance with deeper system-design follow-up."
    if overall >= 68:
        return f"{readiness}. Proceed only if the next round probes the missing technical areas."
    if overall >= 52:
        return f"{readiness}. Re-screen after focused practice on fundamentals and applied reasoning."
    return f"{readiness}. Do not advance without substantial improvement in technical depth."


def _fallback_summary(score: int, question: InterviewQuestion) -> str:
    if score >= 80:
        return f"Strong answer on {question.focus_topic} with good technical and practical signal."
    if score >= 60:
        return f"Partially correct answer on {question.focus_topic}, but it needs deeper validation and tradeoff detail."
    return f"Weak answer on {question.focus_topic}; key concepts and practical reasoning were missing or unclear."


def _clean_answer(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9+.#/-]{2,}", text.lower())


def _token_present(token: str, text: str) -> bool:
    if token in text:
        return True
    variants = {
        "scalability": ("scale", "scaling"),
        "authentication": ("auth", "login"),
        "authorization": ("authz", "permission", "access"),
        "observability": ("monitor", "logging", "tracing", "metrics"),
        "deployment": ("deploy", "rollout"),
        "optimization": ("optimize", "performance"),
        "evaluation": ("evaluate", "metric", "measure"),
    }
    if any(variant in text for variant in variants.get(token, ())):
        return True
    return len(token) >= 6 and token[:5] in text


def _normalize_concept(concept: str) -> str:
    clean = re.sub(r"\s+", " ", str(concept).strip(" :-")).lower()
    if len(clean) > 80:
        clean = clean[:80].rsplit(" ", 1)[0]
    return clean


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_compact(_clean_answer(str(item)), 220) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [_compact(_clean_answer(value), 220)]
    return []


def _score(value: Any) -> int:
    try:
        if isinstance(value, dict):
            value = value.get("score", value.get("value", 0))
        return max(0, min(100, round(float(value))))
    except Exception:
        return 0


def _compact(text: str, limit: int) -> str:
    clean = _clean_answer(text)
    return clean[: limit - 3].rstrip() + "..." if len(clean) > limit else clean


def _dedupe(items) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        clean = _clean_answer(str(item))
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        ordered.append(clean)
    return ordered


def _front_matter(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(token in lowered for token in ("copyright", "isbn", "table of contents", "download pdf"))


def _looks_like_no_answer(answer_text: str) -> bool:
    lower = answer_text.lower().strip()
    return any(token in lower for token in ("i don't know", "i do not know", "no idea", "not sure"))


def _metadata_keywords(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("keywords", [])
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
