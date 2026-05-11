from __future__ import annotations

import json
import hashlib
import math
import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.app.config import get_settings
from backend.app.roles import RoleDefinition
from backend.app.schemas import ResumeProfile

QUESTION_TYPE_GUIDANCE = {
    "theoretical": "test conceptual depth and force the candidate to explain why the idea matters",
    "coding": "ask for implementation structure, edge cases, and verification, not syntax trivia",
    "scenario": "place the candidate in a realistic work situation with constraints",
    "debugging": "ask them to diagnose symptoms, form hypotheses, inspect signals, and fix safely",
    "project": "anchor directly to a resume project and probe design decisions",
    "behavioral": "probe technical ownership, tradeoffs, collaboration, and learning",
    "architecture": "ask for system design, scaling, reliability, data flow, and risk management",
    "problem_solving": "ask for a concrete plan to solve an unfamiliar but role-relevant problem",
}

DIFFICULTY_GUIDANCE = {
    "easy": "foundation-level but not generic; ask for clear understanding and one concrete example",
    "medium": "applied depth; require tradeoffs, design choices, and validation",
    "hard": "senior-style reasoning; require constraints, failure modes, scaling, and observability",
}


@dataclass(frozen=True)
class QuestionDraft:
    prompt: str
    hint: str | None
    rationale: str


class LocalQuestionLLM:
    _shared_pipelines: dict[str, Any] = {}
    _shared_unavailable_models: set[str] = set()

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(self, prompt: str, seed: int) -> str | None:
        if not self.settings.enable_local_question_generation:
            return None
        for model_name in self._model_candidates():
            if model_name in LocalQuestionLLM._shared_unavailable_models:
                continue
            try:
                generator = self._pipeline_for_model(model_name)
                if generator is None:
                    continue
                from transformers import set_seed

                set_seed(seed)
                output = generator(
                    prompt,
                    max_new_tokens=self.settings.question_generator_max_new_tokens,
                    do_sample=True,
                    temperature=0.82,
                    top_p=0.94,
                    return_full_text=False,
                    pad_token_id=getattr(generator.tokenizer, "eos_token_id", None),
                )[0]
                return str(output.get("generated_text", "")).strip()
            except Exception:
                LocalQuestionLLM._shared_unavailable_models.add(model_name)
        return None

    def _pipeline_for_model(self, model_name: str):
        if model_name in LocalQuestionLLM._shared_pipelines:
            return LocalQuestionLLM._shared_pipelines[model_name]
        if self.settings.question_generator_local_files_only and not self._model_is_cached(model_name):
            LocalQuestionLLM._shared_unavailable_models.add(model_name)
            return None
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            local_files_only=self.settings.question_generator_local_files_only,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            local_files_only=self.settings.question_generator_local_files_only,
        )
        generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
        LocalQuestionLLM._shared_pipelines[model_name] = generator
        return generator

    def _model_candidates(self) -> list[str]:
        return self._dedupe(
            [
                self.settings.question_generator_model_name,
                *self.settings.question_generator_fallback_model_names,
            ]
        )

    def _model_is_cached(self, model_name: str) -> bool:
        try:
            from huggingface_hub import try_to_load_from_cache

            cached_config = try_to_load_from_cache(
                model_name,
                "config.json",
            )
            return isinstance(cached_config, str)
        except Exception:
            return False

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result


class QuestionMemory:
    _shared_embedding_model = None
    _shared_embedding_unavailable = False
    _shared_vector_collection = None
    _shared_vector_unavailable = False

    def __init__(self) -> None:
        self.settings = get_settings()

    def max_similarity(self, candidate: str, history: list[str], role_value: str | None = None) -> float:
        clean_history = [item for item in history if item.strip()]
        embedding_score = self._embedding_similarity(candidate, clean_history) if clean_history else 0.0
        lexical_score = (
            max(self._lexical_similarity(candidate, item) for item in clean_history)
            if clean_history
            else 0.0
        )
        vector_score = self._vector_memory_similarity(candidate, role_value) if role_value else 0.0
        return max(embedding_score, lexical_score, vector_score)

    def remember(self, prompt: str, role_value: str, session_seed: str) -> None:
        collection = self._vector_collection()
        if collection is None:
            return
        normalized = prompt.strip()
        if not normalized:
            return
        memory_id = hashlib.sha1(f"{role_value}:{normalized}".encode()).hexdigest()
        try:
            collection.upsert(
                ids=[memory_id],
                documents=[normalized],
                metadatas=[
                    {
                        "role": role_value,
                        "session_seed": session_seed,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                ],
            )
        except Exception:
            QuestionMemory._shared_vector_unavailable = True

    def _embedding_similarity(self, candidate: str, history: list[str]) -> float:
        if QuestionMemory._shared_embedding_unavailable:
            return 0.0
        try:
            if QuestionMemory._shared_embedding_model is None:
                from sentence_transformers import SentenceTransformer

                QuestionMemory._shared_embedding_model = SentenceTransformer(self.settings.embedding_model_name)
            vectors = QuestionMemory._shared_embedding_model.encode([candidate, *history], normalize_embeddings=True)
            candidate_vector = vectors[0]
            best = 0.0
            for vector in vectors[1:]:
                score = float(sum(float(a) * float(b) for a, b in zip(candidate_vector, vector)))
                best = max(best, score)
            return best
        except Exception:
            QuestionMemory._shared_embedding_unavailable = True
            return 0.0

    def _vector_memory_similarity(self, candidate: str, role_value: str | None) -> float:
        collection = self._vector_collection()
        if collection is None:
            return 0.0
        try:
            result = collection.query(
                query_texts=[candidate],
                n_results=8,
                where={"role": role_value} if role_value else None,
                include=["distances"],
            )
            distances = result.get("distances", [[]])[0]
            if not distances:
                return 0.0
            return max(max(0.0, 1.0 - float(distance or 0.0)) for distance in distances)
        except Exception:
            return 0.0

    def _vector_collection(self):
        if QuestionMemory._shared_vector_unavailable:
            return None
        if QuestionMemory._shared_vector_collection is not None:
            return QuestionMemory._shared_vector_collection
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

            client = chromadb.PersistentClient(
                path=str(self.settings.vector_store_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=self.settings.embedding_model_name
            )
            QuestionMemory._shared_vector_collection = client.get_or_create_collection(
                "interview_question_memory",
                embedding_function=embedding_function,
                metadata={
                    "description": "Semantic memory for generated interview questions",
                    "embedding_model": self.settings.embedding_model_name,
                    "hnsw:space": "cosine",
                },
            )
            return QuestionMemory._shared_vector_collection
        except Exception:
            QuestionMemory._shared_vector_unavailable = True
            return None

    def _lexical_similarity(self, left: str, right: str) -> float:
        left_terms = self._terms(left)
        right_terms = self._terms(right)
        if not left_terms or not right_terms:
            return 0.0
        overlap = len(left_terms & right_terms)
        return overlap / math.sqrt(len(left_terms) * len(right_terms))

    def _terms(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z][a-z0-9+.#-]{2,}", text.lower())
            if token
            not in {
                "the",
                "and",
                "for",
                "with",
                "your",
                "would",
                "what",
                "how",
                "why",
                "when",
                "this",
                "that",
                "you",
                "are",
            }
        }


class QuestionComposer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LocalQuestionLLM()
        self.memory = QuestionMemory()

    def compose(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        question_number: int,
        source_keywords: list[str],
        history_prompts: list[str],
        global_history_prompts: list[str],
        session_seed: str,
    ) -> QuestionDraft:
        evidence = self._evidence_sentence(focus)
        history = self._dedupe([*history_prompts, *global_history_prompts])
        threshold = self.settings.question_similarity_threshold
        best_prompt = ""
        best_similarity = 1.0
        best_hint = None
        rng = random.Random(f"{session_seed}:{question_number}:{focus.get('topic')}")

        for attempt in range(max(1, self.settings.question_regeneration_attempts)):
            seed = rng.randint(1, 10_000_000)
            model_prompt = self._build_llm_prompt(
                role=role,
                profile=profile,
                focus=focus,
                evidence=evidence,
                source_keywords=source_keywords,
                history=history,
                attempt=attempt,
                seed=seed,
            )
            generated = self.llm.generate(model_prompt, seed=seed)
            question, hint = self._parse_model_output(generated)
            if not question:
                question = self._synthesize_question(role, profile, focus, evidence, attempt, seed)
                hint = self._build_hint(focus, source_keywords, attempt)

            question = self._clean_question(question)
            similarity = self.memory.max_similarity(question, history, role.value)
            if similarity < best_similarity:
                best_prompt = question
                best_similarity = similarity
                best_hint = hint
            if similarity <= threshold:
                self.memory.remember(question, role.value, session_seed)
                rationale = self._build_rationale(
                    role,
                    profile,
                    focus,
                    question_number,
                    evidence,
                    similarity,
                    used_llm=generated is not None,
                )
                return QuestionDraft(prompt=question, hint=hint, rationale=rationale)

        diversified = self._force_diversify(role, focus, profile, question_number, session_seed)
        self.memory.remember(diversified, role.value, session_seed)
        rationale = self._build_rationale(
            role,
            profile,
            focus,
            question_number,
            evidence,
            best_similarity,
            used_llm=False,
        )
        return QuestionDraft(prompt=diversified, hint=best_hint, rationale=rationale)

    def _build_llm_prompt(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        evidence: str,
        source_keywords: list[str],
        history: list[str],
        attempt: int,
        seed: int,
    ) -> str:
        profile_payload = {
            "candidate": profile.candidate_name,
            "summary": profile.summary,
            "skills": profile.skills,
            "technologies": profile.technologies,
            "tools": profile.tools,
            "frameworks": profile.frameworks,
            "certifications": profile.certifications,
            "projects": [project.model_dump() for project in profile.projects],
            "work_experience": [item.model_dump() for item in profile.work_experience],
            "internships": [item.model_dump() for item in profile.internships],
            "achievements": profile.achievements,
            "education": profile.education,
            "domain_expertise": profile.domain_expertise,
            "resume_digest": profile.full_text_digest,
        }
        focus_payload = {
            "role": role.label,
            "planner_bucket": focus.get("planner_bucket"),
            "stage": focus.get("stage"),
            "question_type": focus.get("question_type"),
            "difficulty": focus.get("difficulty"),
            "topic": focus.get("topic"),
            "anchor": focus.get("anchor"),
            "anchor_type": focus.get("anchor_type"),
            "anchor_category": focus.get("anchor_category"),
            "selected_lens": focus.get("selected_lens"),
            "project": focus.get("project"),
            "experience": focus.get("experience"),
            "scenario": focus.get("scenario"),
            "theory_topic": focus.get("theory_topic"),
            "adaptive_directive": focus.get("adaptive_directive"),
            "planner_note": focus.get("planner_note"),
            "covered_before": focus.get("covered_before"),
            "retrieved_keywords": source_keywords[:10],
            "retrieved_evidence": evidence,
            "source_excerpts": [
                {
                    "title": source.get("title"),
                    "topic": source.get("topic"),
                    "excerpt": source.get("excerpt"),
                }
                for source in focus.get("sources", [])[:4]
            ],
        }
        return (
            "You are a senior technical interviewer. Generate exactly one fresh interview question.\n"
            "Think like a Llama/Qwen/DeepSeek/Mixtral evaluator internally, but output only JSON.\n"
            "Hard rules:\n"
            "- The question must be specific to the candidate resume, selected role, and retrieved knowledge.\n"
            "- The question must feel like it came from a real senior engineer, not a chatbot or question bank.\n"
            "- It must not repeat or paraphrase any previous question.\n"
            "- It must not use a static template or ask trivia detached from the resume.\n"
            "- It must not be a generic definition question unless difficulty is easy and the resume shows no depth.\n"
            "- It must reference a project, skill, tool, framework, certification, internship, or experience from the resume.\n"
            "- Respect the planner_bucket exactly: skill questions must focus on the selected skill, project questions on the selected project, scenario questions on the company-style scenario, and theory questions on fundamentals.\n"
            "- Do not drift back to a different or more detailed project when the current bucket is skill, scenario, or theory.\n"
            "- If planner_bucket is project, use only the selected project and avoid other resume projects.\n"
            "- If covered_before lists a project, skill, or concept, avoid repeating it unless the current focus explicitly selected it.\n"
            "- Prefer architecture decisions, debugging, scale, security, performance, deployment, and validation.\n"
            "- If the resume mentions React, probe hooks, reconciliation, state, rendering, or optimization.\n"
            "- If it mentions Kubernetes, probe deployments, scaling, networking, rollout safety, or service discovery.\n"
            "- If it mentions AI/ML, probe data pipelines, training, evaluation, deployment, drift, or model failure modes.\n"
            "- If it mentions cloud or DevOps, probe IAM, CI/CD, Docker, monitoring, automation, cost, and reliability.\n"
            "- Return JSON with keys question and hint.\n\n"
            f"Generation nonce: {seed}-{attempt}\n"
            f"Role context: {json.dumps(role.core_topics)}\n"
            f"Resume profile: {json.dumps(profile_payload, ensure_ascii=True)[:5200]}\n"
            f"Question focus: {json.dumps(focus_payload, ensure_ascii=True)[:3600]}\n"
            f"Previous questions to avoid: {json.dumps(history[-12:], ensure_ascii=True)}\n"
            f"Question type guidance: {QUESTION_TYPE_GUIDANCE.get(str(focus.get('question_type')), '')}\n"
            f"Difficulty guidance: {DIFFICULTY_GUIDANCE.get(str(focus.get('difficulty')), '')}\n"
        )

    def _parse_model_output(self, generated: str | None) -> tuple[str | None, str | None]:
        if not generated:
            return None, None
        match = re.search(r"\{.*\}", generated, flags=re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
                question = str(payload.get("question", "")).strip()
                hint = str(payload.get("hint", "")).strip() or None
                return question or None, hint
            except Exception:
                pass
        lines = [line.strip() for line in generated.splitlines() if line.strip()]
        for line in lines:
            if "?" in line:
                return line, None
        return None, None

    def _synthesize_question(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        evidence: str,
        attempt: int,
        seed: int,
    ) -> str:
        rng = random.Random(seed)
        question_type = str(focus.get("question_type", "scenario"))
        difficulty = str(focus.get("difficulty", "medium"))
        anchor = self._anchor_text(profile, focus, attempt)
        project = focus.get("project")
        project_name = project.get("name") if isinstance(project, dict) else None
        concept = self._concept_phrase(focus, evidence, attempt)
        constraint = self._constraint_phrase(role, profile, focus, attempt)
        depth_clause = self._depth_clause(difficulty, question_type)
        role_label = role.label
        role_article = "an" if role_label[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
        anchor_context = self._anchor_context(role, focus, anchor)

        if question_type == "project":
            variant = seed % 5
            if variant == 1:
                return (
                    f"If {project_name or anchor} had to support a much larger user base, which part of the "
                    f"{concept} design would you revisit first, and what measurement would drive that decision?"
                )
            if variant == 2:
                return (
                    f"What was the riskiest assumption behind {concept} in {project_name or anchor}, and how would you "
                    f"design an experiment or test to validate it before users depended on it?"
                )
            if variant == 3:
                return (
                    f"Explain how you would deploy the {concept} part of {project_name or anchor} safely. "
                    f"What rollout, monitoring, and rollback choices would you make under {constraint}?"
                )
            if variant == 4:
                return (
                    f"Looking back at {project_name or anchor}, what would you redesign around {concept} if security, "
                    f"latency, and maintainability all mattered at the same time?"
                )
            return (
                f"In your project {project_name or anchor}, explain the most important technical decision around "
                f"{concept}. What alternatives did you consider, what tradeoff did you accept, and {depth_clause}?"
            )
        if question_type == "coding":
            return (
                f"Using {anchor} as the context, outline the implementation for a {concept} component. "
                f"Describe the data structures or APIs, edge cases, and the tests you would write under {constraint}."
            )
        if question_type == "debugging":
            symptom = rng.choice(("latency spike", "incorrect output", "deployment failure", "data inconsistency"))
            article = "an" if symptom[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
            return (
                f"Suppose {anchor_context} starts showing {article} {symptom} related to {concept}. "
                f"What would you inspect first, how would you isolate the root cause, and {depth_clause}?"
            )
        if question_type == "architecture":
            return (
                f"Design how you would evolve {project_name or anchor} for production use as {role_article} {role_label}. "
                f"Focus on {concept}, {constraint}, failure recovery, and how you would monitor the system."
            )
        if question_type == "behavioral":
            return (
                f"Tell me about a time from your resume where {anchor} forced a difficult technical tradeoff. "
                f"How did you decide, who was affected, and what did you learn about {concept}?"
            )
        if question_type == "theoretical":
            return (
                f"Connect {concept} from the knowledge base to {anchor_context}. "
                f"What is the underlying principle, where does it break down, and what example from your work proves you understand it?"
            )
        if question_type == "problem_solving":
            return (
                f"You are asked to add {concept} to {project_name or anchor} within two weeks. "
                f"What plan would you propose, what risks would you de-risk first, and {depth_clause}?"
            )
        return (
            f"For the {role_label} role, use {anchor_context} to reason through {concept}. "
            f"What would you build, what could fail, and how would you validate the result?"
        )

    def _anchor_text(self, profile: ResumeProfile, focus: dict, attempt: int) -> str:
        anchor = str(focus.get("anchor") or "").strip()
        if anchor:
            return anchor
        candidates = [
            *[project.name for project in profile.projects],
            *profile.skills,
            *profile.technologies,
            *profile.tools,
            *profile.frameworks,
            *profile.domain_expertise,
        ]
        if not candidates:
            return "your strongest resume project"
        return candidates[attempt % len(candidates)]

    def _project_payload(self, profile: ResumeProfile, attempt: int) -> dict[str, Any]:
        if not profile.projects:
            return {}
        return profile.projects[attempt % len(profile.projects)].model_dump()

    def _anchor_context(self, role: RoleDefinition, focus: dict, anchor: str) -> str:
        anchor_type = str(focus.get("anchor_type") or "")
        bucket = str(focus.get("planner_bucket") or "")
        if anchor_type == "project":
            return f"your resume project {anchor}"
        if anchor_type == "skill" or bucket == "skill":
            return f"your resume skill or tool {anchor}"
        if anchor_type == "experience":
            return f"your work experience with {anchor}"
        if anchor_type == "role_scenario" or bucket == "scenario":
            return f"a realistic {role.label} scenario around {anchor}"
        if anchor_type == "theory" or bucket == "theory":
            return f"the core {role.label} fundamental {anchor}"
        if anchor_type in {"certification"}:
            return f"your resume evidence around {anchor}"
        return f"the {role.label} focus area {anchor} connected to your resume projects"

    def _concept_phrase(self, focus: dict, evidence: str, attempt: int) -> str:
        topic = str(focus.get("topic") or "").strip()
        anchor = str(focus.get("anchor") or "").strip()
        if anchor:
            topic = re.sub(rf"^{re.escape(anchor)}\s*:\s*", "", topic, flags=re.IGNORECASE)
            topic = re.sub(rf"^{re.escape(anchor)}\s+and\s+", "", topic, flags=re.IGNORECASE)
            topic = re.sub(rf"^{re.escape(anchor)}\s+depth\s+in\s+", "", topic, flags=re.IGNORECASE)
        keywords = [
            keyword
            for source in focus.get("sources", [])
            for keyword in source.get("metadata", {}).get("keywords", [])[:4]
            if str(keyword).lower()
            not in {
                "data",
                "model",
                "models",
                "using",
                "based",
                "learning",
                "expected",
                "need",
                "used",
                "independent",
                "systems",
                "system",
                "approach",
            }
        ]
        candidates = [topic, *keywords, evidence]
        candidates = [item for item in candidates if item]
        concept = candidates[0] if candidates else "the core technical risk"
        return re.sub(r"\s+", " ", str(concept)).strip()[:120]

    def _constraint_phrase(self, role: RoleDefinition, profile: ResumeProfile, focus: dict, attempt: int) -> str:
        signals = [
            "high traffic",
            "limited latency budget",
            "cloud deployment constraints",
            "security and access-control requirements",
            "data quality uncertainty",
            "small-team maintainability",
            *role.core_topics[:4],
            *profile.domain_expertise[:4],
        ]
        return signals[attempt % len(signals)]

    def _depth_clause(self, difficulty: str, question_type: str) -> str:
        if difficulty in {"hard", "deep", "system"}:
            return "how would you prove the design is reliable under failure"
        if difficulty in {"medium", "core"}:
            return "how would you measure whether your approach worked"
        if question_type == "theoretical":
            return "what simple example would you use to explain it"
        return "what would you check to avoid a basic mistake"

    def _build_hint(self, focus: dict, source_keywords: list[str], attempt: int) -> str | None:
        checkpoints = self._dedupe([*source_keywords[:5], *focus.get("skills", [])[:4]])
        if checkpoints:
            return f"Touch on {', '.join(checkpoints[:4])}; include tradeoffs and validation."
        if focus.get("adaptive_directive"):
            return str(focus["adaptive_directive"])
        return None

    def _build_rationale(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        question_number: int,
        evidence: str,
        similarity: float,
        used_llm: bool,
    ) -> str:
        anchor = self._anchor_text(profile, focus, question_number)
        source_labels = self._source_labels(focus)
        model_name = self.settings.question_generator_model_name if used_llm else "dynamic fallback generator"
        return (
            f"Q{question_number} is a {focus.get('difficulty')} {focus.get('question_type')} "
            f"{focus.get('planner_bucket', 'interview')} question for {role.label}, anchored to {anchor}. "
            f"It uses retrieved evidence from {source_labels}: "
            f"{evidence[:170].rstrip('.')}. Anti-repetition max similarity was {similarity:.2f}; "
            f"generation source: {model_name}."
        )

    def _evidence_sentence(self, focus: dict) -> str:
        sources = focus.get("sources", [])
        if not sources:
            return str(focus.get("topic") or "the selected role topic")
        candidates: list[tuple[str, int]] = []
        keywords = {
            str(keyword).lower()
            for source in sources
            for keyword in source.get("metadata", {}).get("keywords", [])[:6]
        }
        for source in sources[:5]:
            for sentence in self._split_sentences(source.get("excerpt", "")):
                if self._looks_like_front_matter(sentence):
                    continue
                lowered = sentence.lower()
                score = sum(1 for keyword in keywords if keyword in lowered)
                score += sum(1 for token in str(focus.get("query", "")).lower().split() if token in lowered)
                candidates.append((sentence, score))
        if not candidates:
            return str(sources[0].get("excerpt", focus.get("topic", "the selected role topic")))[:260]
        return max(candidates, key=lambda item: item[1])[0][:260].strip()

    def _split_sentences(self, text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if len(sentence.strip().split()) >= 8
        ]

    def _looks_like_front_matter(self, sentence: str) -> bool:
        lowered = sentence.lower()
        boilerplate = (
            "download pdf",
            "copyright",
            "all rights reserved",
            "isbn",
            "table of contents",
        )
        return any(token in lowered for token in boilerplate)

    def _source_labels(self, focus: dict) -> str:
        labels: list[str] = []
        for source in focus.get("sources", [])[:3]:
            metadata = source.get("metadata", {})
            label = metadata.get("source_file") or source.get("title")
            if label and label not in labels:
                labels.append(str(label))
        return ", ".join(labels) if labels else "the role knowledge base"

    def _force_diversify(
        self,
        role: RoleDefinition,
        focus: dict,
        profile: ResumeProfile,
        question_number: int,
        session_seed: str,
    ) -> str:
        seed = sum(ord(char) for char in f"{session_seed}:{question_number}:{focus.get('anchor')}") + 7919
        return self._synthesize_question(
            role=role,
            profile=profile,
            focus=focus,
            evidence=str(focus.get("topic", "")),
            attempt=0,
            seed=seed,
        )

    def _clean_question(self, text: str) -> str:
        clean = text.strip().strip('"')
        clean = re.sub(r"^(question|q)\s*[:.-]\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"[ \t]+", " ", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
        if "?" not in clean and not re.search(r"\n[A-D]\.", clean):
            clean = clean.rstrip(".")
            clean = f"{clean}?"
        return clean

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = str(item).lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(str(item).strip())
        return result
