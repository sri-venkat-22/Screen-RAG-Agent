from __future__ import annotations

from collections import Counter
import random
import re
from datetime import datetime
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import InterviewSession as InterviewSessionModel
from backend.app.db.models import InterviewTurn as InterviewTurnModel
from backend.app.roles import RoleDefinition, get_role
from backend.app.schemas import (
    AnswerResponse,
    InterviewQuestion,
    InterviewResult,
    InterviewTurn,
    ResumeProfile,
    SessionSummary,
    StartSessionResponse,
    SubmitAnswerRequest,
)
from backend.app.services.analysis import build_session_insights, evaluate_answer
from backend.app.services.knowledge import get_knowledge_service
from backend.app.services.question_generation import QuestionComposer
from backend.app.services.resume import build_resume_profile, extract_resume_text


QUESTION_BUCKET_WEIGHTS = {
    "skill": 0.30,
    "project": 0.30,
    "scenario": 0.25,
    "theory": 0.15,
}

BUCKET_FLOW = (
    "skill",
    "scenario",
    "project",
    "theory",
    "skill",
    "project",
    "scenario",
    "theory",
    "project",
)

ROLE_REAL_WORLD_SCENARIOS: dict[str, tuple[str, ...]] = {
    "frontend": (
        "optimize a slow React page with unnecessary renders",
        "reduce bundle size without breaking user workflows",
        "fix a state management bug that appears after navigation",
        "debug hydration or rendering mismatches in production",
        "improve accessibility and keyboard behavior in a complex component",
    ),
    "backend": (
        "scale an API under traffic spikes",
        "debug a slow database query in production",
        "design rate limiting and abuse protection",
        "improve cache correctness without serving stale critical data",
        "make background jobs idempotent after retries",
    ),
    "cloud": (
        "recover a failed cloud deployment with minimal downtime",
        "debug IAM permissions blocking a service rollout",
        "right-size infrastructure during a traffic surge",
        "design monitoring and alerting for a customer-facing workload",
        "reduce cloud cost while preserving availability",
    ),
    "devops": (
        "debug a failing CI/CD pipeline before release",
        "recover a Kubernetes deployment with failing readiness probes",
        "design a safe canary rollout and rollback plan",
        "investigate an SLO breach using logs, metrics, and traces",
        "automate infrastructure drift detection",
    ),
    "ai-ml": (
        "debug model overfitting after a promising offline experiment",
        "handle data imbalance in a production classifier",
        "design an inference pipeline with latency constraints",
        "evaluate retrieval quality in a RAG system",
        "monitor model drift after deployment",
    ),
    "data": (
        "debug a delayed batch pipeline with downstream dashboard impact",
        "design data quality checks for unreliable source data",
        "handle backfills without corrupting analytical tables",
        "optimize a warehouse model for common queries",
        "trace lineage for a broken metric",
    ),
    "data-analyst": (
        "investigate a dashboard metric that suddenly changed",
        "design an experiment readout for a product feature",
        "debug a SQL query that double-counts users",
        "choose visualizations for an executive decision review",
        "define a trustworthy north-star metric",
    ),
    "cybersecurity": (
        "threat-model a new authenticated API",
        "triage a suspicious login spike",
        "fix an OWASP-style vulnerability before release",
        "design logging for incident detection",
        "review least-privilege access for a cloud service",
    ),
    "testing": (
        "design test coverage for a risky release",
        "debug a flaky Playwright or Selenium test",
        "choose what belongs in unit, integration, and e2e tests",
        "build quality gates for CI without blocking every release",
        "prioritize defects found late in a sprint",
    ),
    "fullstack": (
        "debug an end-to-end feature with UI, API, and database symptoms",
        "decide where client/server logic should live",
        "design authentication across frontend and backend boundaries",
        "optimize a slow product workflow across the stack",
        "ship a feature safely with tests and rollback",
    ),
    "software": (
        "debug a correctness issue in a production feature",
        "choose data structures for a performance-sensitive workflow",
        "refactor a brittle module without changing behavior",
        "design tests around edge cases and failure modes",
        "reason about scalability tradeoffs in a small system",
    ),
}

ROLE_THEORY_TOPICS: dict[str, tuple[str, ...]] = {
    "frontend": (
        "React reconciliation and rendering lifecycle",
        "browser event loop and network loading",
        "accessibility semantics and focus management",
        "client-side caching and state consistency",
    ),
    "backend": (
        "database transactions and isolation",
        "HTTP semantics and API contracts",
        "caching consistency and invalidation",
        "network timeouts, retries, and idempotency",
    ),
    "cloud": (
        "networking, load balancing, and DNS",
        "identity and access management",
        "availability zones and disaster recovery",
        "observability signals and alert design",
    ),
    "devops": (
        "Kubernetes deployment primitives",
        "SLOs, error budgets, and incident response",
        "CI/CD release strategies",
        "infrastructure as code state management",
    ),
    "ai-ml": (
        "bias variance and overfitting",
        "precision, recall, calibration, and evaluation",
        "embedding retrieval and ranking",
        "model deployment and drift monitoring",
    ),
    "data": (
        "batch versus streaming processing",
        "data modeling and normalization",
        "partitioning, indexing, and warehouse performance",
        "data lineage and quality guarantees",
    ),
    "data-analyst": (
        "SQL joins, aggregation, and window functions",
        "statistical significance and experiment design",
        "metric definitions and bias",
        "dashboard design principles",
    ),
    "cybersecurity": (
        "authentication versus authorization",
        "OWASP vulnerabilities",
        "encryption and key management",
        "threat modeling fundamentals",
    ),
    "testing": (
        "test pyramid and test scope",
        "boundary value and equivalence partitioning",
        "flakiness and determinism",
        "release risk and defect triage",
    ),
}


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.knowledge = get_knowledge_service()
        self.question_composer = QuestionComposer()

    async def start_session(
        self,
        role_value: str,
        candidate_name: str | None,
        resume_filename: str,
        resume_bytes: bytes,
    ) -> StartSessionResponse:
        role = get_role(role_value)
        resume_text = extract_resume_text(resume_filename, resume_bytes)
        if not resume_text.strip():
            raise ValueError("The uploaded resume did not contain readable text.")

        profile = build_resume_profile(resume_text, role_value, candidate_name)
        total_questions = self._question_count_for_role(role)
        session_seed = uuid4().hex
        plan = self._build_interview_plan(role, profile, total_questions, session_seed)
        first_focus = plan["focus_areas"][0]
        first_question = self._generate_question(
            role,
            profile,
            first_focus,
            question_number=1,
            question_total=total_questions,
            session_seed=session_seed,
            history_prompts=self._recent_question_prompts(role.value),
        )

        session = InterviewSessionModel(
            candidate_name=profile.candidate_name,
            role=role.value,
            resume_filename=resume_filename,
            resume_text=resume_text,
            resume_profile=jsonable_encoder(profile),
            interview_plan=plan,
            total_questions=total_questions,
        )
        self.db.add(session)
        self.db.flush()

        turn = InterviewTurnModel(
            session_id=session.id,
            question_index=1,
            question_payload=jsonable_encoder(first_question),
            retrieval_trace={"query": first_focus["query"], "sources": first_focus["sources"]},
        )
        self.db.add(turn)
        self.db.commit()
        self.db.refresh(session)

        return StartSessionResponse(
            session_id=session.id,
            candidate=profile.candidate_name,
            role=role.value,
            resume_profile=profile,
            question=first_question,
        )

    def submit_answer(self, session_id: str, payload: SubmitAnswerRequest) -> AnswerResponse:
        session = self.db.get(InterviewSessionModel, session_id)
        if session is None:
            raise ValueError("Interview session not found.")
        if session.status == "completed":
            raise ValueError("This interview session is already complete.")

        current_turn = self._get_active_turn(session)
        if current_turn is None:
            raise ValueError("No active question is available for this session.")

        question = InterviewQuestion.model_validate(current_turn.question_payload)
        role = get_role(session.role)
        profile = ResumeProfile.model_validate(session.resume_profile)
        evaluation = evaluate_answer(question, payload.answer_text, profile=profile, role=role)
        current_turn.answer_text = payload.answer_text.strip()
        current_turn.answer_seconds = payload.answer_seconds
        current_turn.evaluation_payload = jsonable_encoder(evaluation)
        current_turn.answered_at = datetime.utcnow()

        answered_count = session.current_question_index + 1
        if answered_count >= session.total_questions:
            session.current_question_index = answered_count
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            summary = self._build_summary(session)
            session.summary = jsonable_encoder(summary)
            self.db.commit()
            return AnswerResponse(done=True, latest_evaluation=evaluation, summary=summary)

        session.current_question_index = answered_count
        plan = session.interview_plan
        next_focus = self._select_next_focus(role, profile, plan, question, evaluation, payload.answer_text)
        next_question = self._generate_question(
            role,
            profile,
            next_focus,
            question_number=answered_count + 1,
            question_total=session.total_questions,
            session_seed=plan.get("session_seed", session.id),
            history_prompts=[
                *self._session_question_prompts(session),
                *self._recent_question_prompts(role.value, exclude_session_id=session.id),
            ],
        )

        next_turn = InterviewTurnModel(
            session_id=session.id,
            question_index=answered_count + 1,
            question_payload=jsonable_encoder(next_question),
            retrieval_trace={"query": next_focus["query"], "sources": next_focus["sources"]},
        )
        self.db.add(next_turn)
        session.interview_plan = plan
        self.db.commit()

        return AnswerResponse(
            done=False,
            latest_evaluation=evaluation,
            next_question=next_question,
        )

    def get_summary(self, session_id: str) -> SessionSummary:
        session = self.db.get(InterviewSessionModel, session_id)
        if session is None:
            raise ValueError("Interview session not found.")
        if session.summary:
            try:
                summary = SessionSummary.model_validate(session.summary)
                if summary.results:
                    return summary
            except ValidationError:
                pass
        if session.status != "completed":
            raise ValueError("Interview session is still in progress.")
        summary = self._build_summary(session)
        session.summary = jsonable_encoder(summary)
        self.db.commit()
        return summary

    def _question_count_for_role(self, role: RoleDefinition) -> int:
        requested = max(1, self.settings.interview_question_count)
        return min(requested, 10)

    def _build_interview_plan(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        question_count: int,
        session_seed: str,
    ) -> dict:
        rng = random.Random(session_seed)
        buckets = self._question_buckets(role, profile, rng)
        quotas = self._bucket_quotas(question_count, buckets, rng)
        bucket_sequence = self._bucket_sequence(quotas, rng)
        usage = {
            "bucket": Counter(),
            "project": Counter(),
            "skill": Counter(),
            "concept": Counter(),
            "question_type": Counter(),
        }
        focus_areas: list[dict] = []
        used_topics: set[str] = set()

        for index, bucket in enumerate(bucket_sequence):
            covered_before = {
                "projects": list(usage["project"].keys()),
                "skills": list(usage["skill"].keys()),
                "concepts": list(usage["concept"].keys()),
                "buckets": dict(usage["bucket"]),
            }
            anchor = self._select_bucket_anchor(bucket, buckets[bucket], usage, index, rng, quotas)
            question_type = self._question_type_for_focus(bucket, anchor, usage, index, rng)
            difficulty = self._difficulty_for_focus(bucket, profile, index, rng)
            query = self._build_query(role, profile, anchor, question_type, difficulty, index)
            retrieved = self.knowledge.retrieve(role.value, [query], top_k=self.settings.retrieval_top_k)
            selected = self._choose_primary_source(retrieved, used_topics)
            topic = self._focus_topic(anchor, selected, role, index)
            used_topics.add(topic)
            source_mode = "primary" if any(
                source.metadata.get("source_kind", "").startswith("primary") for source in retrieved
            ) else "fallback"
            focus_areas.append(
                {
                    "stage": self._stage_label(anchor, question_type),
                    "question_type": question_type,
                    "difficulty": difficulty,
                    "base_difficulty": difficulty,
                    "planner_bucket": bucket,
                    "lens": anchor["type"],
                    "selected_lens": anchor.get("selected_lens"),
                    "query": query,
                    "topic": topic,
                    "anchor": anchor["label"],
                    "anchor_type": anchor["type"],
                    "anchor_category": anchor.get("category"),
                    "skills": anchor.get("skills", []),
                    "project": anchor.get("project"),
                    "project_complexity": anchor.get("project_complexity"),
                    "experience": anchor.get("experience"),
                    "scenario": anchor.get("scenario"),
                    "theory_topic": anchor.get("theory_topic"),
                    "covered_before": covered_before,
                    "sources": [source.model_dump() for source in retrieved],
                    "source_mode": source_mode,
                    "planner_note": self._planner_note(bucket, anchor, quotas),
                }
            )
        return {
            "session_seed": session_seed,
            "candidate_summary": profile.summary,
            "question_distribution": quotas,
            "bucket_sequence": bucket_sequence,
            "resume_anchors": [anchor for anchors in buckets.values() for anchor in anchors],
            "focus_areas": focus_areas,
        }

    def _question_buckets(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        rng: random.Random,
    ) -> dict[str, list[dict]]:
        buckets = {
            "skill": self._skill_anchors(role, profile),
            "project": self._project_anchors(role, profile),
            "scenario": self._scenario_anchors(role, profile),
            "theory": self._theory_anchors(role, profile),
        }
        fallback = self._candidate_anchors(role, profile)
        for bucket, anchors in buckets.items():
            if anchors:
                continue
            buckets[bucket] = [
                {
                    **fallback[index % len(fallback)],
                    "bucket": bucket,
                    "usage_key": f"{bucket}:{fallback[index % len(fallback)].get('label', bucket).lower()}",
                }
                for index in range(min(3, len(fallback)))
            ]
        for anchors in buckets.values():
            rng.shuffle(anchors)
        return buckets

    def _skill_anchors(self, role: RoleDefinition, profile: ResumeProfile) -> list[dict]:
        weighted = self._role_weighted_terms(role, profile)
        resume_terms = self._dedupe_strings(
            [
                *weighted,
                *profile.skills,
                *profile.technologies,
                *profile.frameworks,
                *profile.tools,
            ]
        )
        anchors: list[dict] = []
        for term in resume_terms[:18]:
            category = self._skill_category(term)
            anchors.append(
                {
                    "type": "skill",
                    "bucket": "skill",
                    "label": term,
                    "text": f"{term} from the candidate resume, category: {category}",
                    "skills": [term],
                    "category": category,
                    "selected_lens": self._skill_lens(term, category),
                    "usage_key": term.lower(),
                    "max_questions": 1,
                }
            )
        return anchors

    def _project_anchors(self, role: RoleDefinition, profile: ResumeProfile) -> list[dict]:
        scored_projects = [
            (self._project_complexity_score(role, project), index, project)
            for index, project in enumerate(profile.projects)
        ]
        scored_projects.sort(key=lambda item: (-item[0], item[1]))
        anchors: list[dict] = []
        for score, index, project in scored_projects:
            anchors.append(
                {
                    "type": "project",
                    "bucket": "project",
                    "label": project.name,
                    "text": project.description,
                    "skills": project.technologies or self._terms_for_text(project.description, profile),
                    "project": project.model_dump(),
                    "project_complexity": score,
                    "project_index": index,
                    "usage_key": project.name.lower(),
                    "max_questions": 1,
                }
            )
        return anchors

    def _scenario_anchors(self, role: RoleDefinition, profile: ResumeProfile) -> list[dict]:
        anchors: list[dict] = []
        for experience in [*profile.work_experience, *profile.internships]:
            label = experience.title
            anchors.append(
                {
                    "type": "experience",
                    "bucket": "scenario",
                    "label": label,
                    "text": experience.description,
                    "skills": experience.technologies or self._terms_for_text(experience.description, profile),
                    "experience": experience.model_dump(),
                    "scenario": f"real-world follow-up from {label}",
                    "selected_lens": "applied work-experience scenario",
                    "usage_key": f"experience:{label.lower()}",
                    "max_questions": 1,
                }
            )
        scenario_pool = ROLE_REAL_WORLD_SCENARIOS.get(role.value, ROLE_REAL_WORLD_SCENARIOS["software"])
        role_terms = self._role_weighted_terms(role, profile)
        for index, scenario in enumerate(scenario_pool):
            anchors.append(
                {
                    "type": "role_scenario",
                    "bucket": "scenario",
                    "label": scenario,
                    "text": f"{scenario} for {role.label}",
                    "skills": role_terms[index : index + 3] or role_terms[:3],
                    "scenario": scenario,
                    "selected_lens": "real engineering incident",
                    "usage_key": f"scenario:{scenario.lower()}",
                    "max_questions": 1,
                }
            )
        return anchors

    def _theory_anchors(self, role: RoleDefinition, profile: ResumeProfile) -> list[dict]:
        topics = self._dedupe_strings(
            [
                *ROLE_THEORY_TOPICS.get(role.value, ()),
                *role.core_topics,
                "DBMS fundamentals",
                "operating system fundamentals",
                "networking fundamentals",
                "object-oriented design",
                "data structures and algorithms",
                "secure software development lifecycle",
            ]
        )
        resume_terms = self._role_weighted_terms(role, profile)
        return [
            {
                "type": "theory",
                "bucket": "theory",
                "label": topic,
                "text": f"{topic} connected to {role.label}",
                "skills": resume_terms[index : index + 2] or resume_terms[:2],
                "theory_topic": topic,
                "selected_lens": "core fundamentals",
                "usage_key": f"theory:{topic.lower()}",
                "max_questions": 1,
            }
            for index, topic in enumerate(topics[:14])
        ]

    def _bucket_quotas(
        self,
        question_count: int,
        buckets: dict[str, list[dict]],
        rng: random.Random,
    ) -> dict[str, int]:
        available = [bucket for bucket in QUESTION_BUCKET_WEIGHTS if buckets.get(bucket)]
        if not available:
            return {"scenario": question_count}
        if question_count <= len(available):
            ranked = sorted(
                available,
                key=lambda bucket: (-QUESTION_BUCKET_WEIGHTS[bucket], rng.random()),
            )
            return {bucket: 1 if bucket in ranked[:question_count] else 0 for bucket in available}

        quotas = {bucket: 1 for bucket in available}
        remaining = question_count - len(available)
        total_weight = sum(QUESTION_BUCKET_WEIGHTS[bucket] for bucket in available)
        fractional: list[tuple[float, str]] = []
        for bucket in available:
            raw = remaining * QUESTION_BUCKET_WEIGHTS[bucket] / total_weight
            add = int(raw)
            quotas[bucket] += add
            fractional.append((raw - add, bucket))
        assigned = sum(quotas.values())
        tie_priority = {"skill": 0, "project": 1, "scenario": 2, "theory": 3}
        fractional.sort(
            key=lambda item: (
                -item[0],
                -QUESTION_BUCKET_WEIGHTS[item[1]],
                tie_priority.get(item[1], 9),
            )
        )
        while assigned < question_count:
            for _, bucket in fractional:
                if assigned >= question_count:
                    break
                quotas[bucket] += 1
                assigned += 1
        if quotas.get("project") and buckets.get("project"):
            max_per_project = self._max_project_questions(
                quotas["project"],
                len(buckets["project"]),
            )
            for anchor in buckets["project"]:
                anchor["max_questions"] = max_per_project
        return quotas

    def _bucket_sequence(self, quotas: dict[str, int], rng: random.Random) -> list[str]:
        remaining = Counter({bucket: count for bucket, count in quotas.items() if count > 0})
        sequence: list[str] = []
        flow_index = 0
        while sum(remaining.values()) > 0:
            last = sequence[-1] if sequence else None
            choice = None
            for offset in range(len(BUCKET_FLOW)):
                preferred = BUCKET_FLOW[(flow_index + offset) % len(BUCKET_FLOW)]
                if remaining.get(preferred, 0) > 0 and preferred != last:
                    choice = preferred
                    flow_index = (flow_index + offset + 1) % len(BUCKET_FLOW)
                    break
            if choice is None:
                candidates = [
                    bucket
                    for bucket, count in remaining.items()
                    if count > 0 and bucket != last
                ] or [bucket for bucket, count in remaining.items() if count > 0]
                choice = max(candidates, key=lambda bucket: (remaining[bucket], rng.random()))
            sequence.append(choice)
            remaining[choice] -= 1
        return sequence

    def _select_bucket_anchor(
        self,
        bucket: str,
        anchors: list[dict],
        usage: dict[str, Counter],
        index: int,
        rng: random.Random,
        quotas: dict[str, int],
    ) -> dict:
        candidates = [
            anchor
            for anchor in anchors
            if usage[self._usage_counter_name(bucket)][anchor.get("usage_key", anchor["label"].lower())]
            < anchor.get("max_questions", 1)
        ] or anchors
        candidates = sorted(
            candidates,
            key=lambda anchor: (
                usage[self._usage_counter_name(bucket)][anchor.get("usage_key", anchor["label"].lower())],
                -int(anchor.get("project_complexity", 0)),
                rng.random(),
            ),
        )
        selected = dict(candidates[0])
        counter_name = self._usage_counter_name(bucket)
        usage_key = selected.get("usage_key", selected["label"].lower())
        previous_uses = usage[counter_name][usage_key]
        selected["usage_count"] = previous_uses + 1
        if bucket == "project":
            selected["selected_lens"] = self._project_lens(previous_uses, index)
        elif bucket == "skill":
            selected["selected_lens"] = selected.get("selected_lens") or self._skill_lens(
                selected["label"],
                selected.get("category", "technical skill"),
            )
        elif bucket == "scenario":
            selected["selected_lens"] = selected.get("selected_lens") or "real-world engineering scenario"
        else:
            selected["selected_lens"] = selected.get("selected_lens") or "core fundamentals"

        usage[counter_name][usage_key] += 1
        usage["bucket"][bucket] += 1
        usage["concept"][self._concept_usage_key(selected)] += 1
        if bucket == "project" and quotas.get("project", 0) > len(anchors):
            selected["planner_limit"] = f"Project usage capped at {selected.get('max_questions', 1)} questions."
        return selected

    def _usage_counter_name(self, bucket: str) -> str:
        if bucket == "project":
            return "project"
        if bucket == "skill":
            return "skill"
        return "concept"

    def _question_type_for_focus(
        self,
        bucket: str,
        anchor: dict,
        usage: dict[str, Counter],
        index: int,
        rng: random.Random,
    ) -> str:
        type_pool = {
            "skill": ["coding", "debugging", "scenario", "problem_solving"],
            "project": ["architecture", "debugging", "project", "scenario", "behavioral"],
            "scenario": ["debugging", "scenario", "problem_solving", "architecture"],
            "theory": ["theoretical", "problem_solving"],
        }.get(bucket, ["scenario"])
        forced_type = None
        if bucket == "project" and anchor.get("selected_lens") == "architecture and system boundaries":
            forced_type = "architecture"
        elif bucket == "project" and anchor.get("selected_lens") == "implementation and debugging":
            forced_type = "debugging"
        elif bucket == "project" and anchor.get("selected_lens") == "scalability, security, and reliability":
            forced_type = "scenario"
        if forced_type:
            usage["question_type"][forced_type] += 1
            return forced_type
        offset = (index + int(rng.random() * len(type_pool))) % len(type_pool)
        ordered = [type_pool[(offset + step) % len(type_pool)] for step in range(len(type_pool))]
        selected = min(ordered, key=lambda item: (usage["question_type"][item], ordered.index(item)))
        usage["question_type"][selected] += 1
        return selected

    def _difficulty_for_focus(
        self,
        bucket: str,
        profile: ResumeProfile,
        index: int,
        rng: random.Random,
    ) -> str:
        advanced = profile.seniority in {"advanced", "intermediate"}
        pools = {
            "skill": ["medium", "medium", "hard", "easy" if not advanced else "hard"],
            "project": ["medium", "hard", "medium", "hard" if advanced else "medium"],
            "scenario": ["medium", "hard", "medium", "hard" if advanced else "medium"],
            "theory": ["easy", "medium", "medium", "hard" if advanced else "easy"],
        }
        pool = pools.get(bucket, ["medium"])
        if index == 0 and profile.seniority in {"early-career", "emerging"}:
            return "easy" if bucket == "theory" else "medium"
        return pool[(index + rng.randrange(len(pool))) % len(pool)]

    def _project_complexity_score(self, role: RoleDefinition, project) -> int:
        text = f"{project.name} {project.description} {' '.join(project.technologies)}".lower()
        score = len(project.technologies) * 4 + min(24, len(project.description.split()) // 4)
        score += self._anchor_relevance(
            role,
            {
                "label": project.name,
                "text": project.description,
                "skills": project.technologies,
            },
        )
        score += sum(
            3
            for token in (
                "scale",
                "deploy",
                "optimize",
                "security",
                "latency",
                "pipeline",
                "kubernetes",
                "cloud",
                "evaluation",
                "monitoring",
            )
            if token in text
        )
        return score

    def _max_project_questions(self, project_quota: int, project_count: int) -> int:
        if project_count <= 0:
            return 0
        return min(3, max(1, (project_quota + project_count - 1) // project_count))

    def _project_lens(self, previous_uses: int, index: int) -> str:
        lenses = (
            "architecture and system boundaries",
            "implementation and debugging",
            "scalability, security, and reliability",
            "tradeoffs and ownership",
        )
        return lenses[(previous_uses + index) % len(lenses)]

    def _skill_category(self, term: str) -> str:
        lowered = term.lower()
        if lowered in {"react", "next.js", "vue", "angular", "tailwind", "css", "html"}:
            return "frontend framework"
        if lowered in {"node.js", "express", "fastapi", "django", "flask", "spring boot"}:
            return "backend framework"
        if lowered in {"postgresql", "mysql", "mongodb", "redis", "elasticsearch", "sql"}:
            return "database or storage"
        if lowered in {"docker", "kubernetes", "jenkins", "github actions", "gitlab ci", "terraform", "ansible"}:
            return "devops tool"
        if lowered in {"aws", "gcp", "azure"}:
            return "cloud platform"
        if lowered in {"pytorch", "tensorflow", "scikit-learn", "langchain", "llamaindex", "chromadb", "faiss"}:
            return "ai/ml library"
        if lowered in {"python", "java", "javascript", "typescript", "go", "rust", "c++", "c#"}:
            return "programming language"
        return "technical skill"

    def _skill_lens(self, term: str, category: str) -> str:
        lowered = term.lower()
        if lowered == "react":
            return "hooks, reconciliation, rendering, and optimization"
        if lowered in {"docker", "kubernetes"}:
            return "deployment, scaling, networking, and rollout safety"
        if lowered in {"aws", "gcp", "azure"}:
            return "IAM, deployment, monitoring, cost, and reliability"
        if lowered in {"langchain", "llamaindex", "chromadb", "faiss", "rag", "llm"}:
            return "retrieval, evaluation, grounding, and production tradeoffs"
        if category == "database or storage":
            return "data modeling, query performance, consistency, and operational safety"
        if category == "programming language":
            return "implementation, correctness, testing, and debugging"
        return f"{category} applied design, tradeoffs, and failure modes"

    def _concept_usage_key(self, anchor: dict) -> str:
        return str(
            anchor.get("theory_topic")
            or anchor.get("scenario")
            or anchor.get("label")
            or anchor.get("text")
            or "concept"
        ).lower()

    def _planner_note(self, bucket: str, anchor: dict, quotas: dict[str, int]) -> str:
        if bucket == "project":
            return (
                f"Project bucket: use {anchor['label']} only for this project-focused turn. "
                f"Do not drift to another project. Planned project quota is {quotas.get('project', 0)}."
            )
        if bucket == "skill":
            return (
                f"Skill bucket: focus on {anchor['label']} as a resume skill/tool, not a project recap."
            )
        if bucket == "scenario":
            return "Scenario bucket: simulate a realistic company engineering problem for the selected role."
        return "Theory bucket: ask a concise fundamentals question connected to the role."

    def _dedupe_strings(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            clean = str(item).strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            result.append(clean)
        return result

    def _select_next_focus(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        plan: dict,
        previous_question: InterviewQuestion,
        evaluation,
        answer_text: str,
    ) -> dict:
        next_index = previous_question.index
        planned_focus = dict(plan["focus_areas"][next_index])
        answer_terms = self._answer_terms(answer_text, profile)
        if evaluation.score >= 80:
            planned_focus["difficulty"] = self._shift_difficulty(planned_focus["difficulty"], 1)
            planned_focus["question_type"] = self._stretch_question_type(planned_focus["question_type"])
            planned_focus["stage"] = f"{planned_focus['stage']} Stretch"
            planned_focus["adaptive_directive"] = (
                f"The previous answer was strong. Increase depth while staying in the planned "
                f"{planned_focus.get('planner_bucket', 'interview')} bucket around {planned_focus.get('anchor')}. "
                f"Optionally build on: {', '.join(answer_terms[:4])}."
            )
        elif evaluation.score >= 45:
            planned_focus["adaptive_directive"] = (
                f"Ask the planned {planned_focus.get('planner_bucket', 'interview')} focus around "
                f"{planned_focus.get('anchor')} as a contextual follow-up. Connect lightly to prior answer terms: "
                f"{', '.join(answer_terms[:4])}, but do not repeat the previous question or switch projects."
            )
        else:
            planned_focus["difficulty"] = self._shift_difficulty(previous_question.difficulty, -1)
            if planned_focus.get("planner_bucket") == "theory":
                planned_focus["question_type"] = "theoretical"
            elif planned_focus.get("planner_bucket") == "skill":
                planned_focus["question_type"] = "theoretical"
            else:
                planned_focus["question_type"] = "scenario"
            planned_focus["stage"] = f"{planned_focus['stage']} Foundation"
            planned_focus["adaptive_directive"] = (
                f"The previous answer was thin. Ask the planned topic {planned_focus.get('topic')} at a more "
                "foundational level with a concrete example. Keep the planned anchor and avoid repeating the previous topic."
            )

        adaptive_query = self._adaptive_query(role, planned_focus, previous_question, answer_terms, evaluation.score)
        adaptive_sources = self.knowledge.retrieve(
            role.value,
            [adaptive_query, planned_focus["query"]],
            top_k=self.settings.retrieval_top_k,
        )
        planned_focus["query"] = adaptive_query
        planned_focus["sources"] = [source.model_dump() for source in adaptive_sources]
        planned_focus["source_mode"] = "primary" if any(
            source.metadata.get("source_kind", "").startswith("primary") for source in adaptive_sources
        ) else "fallback"
        return planned_focus

    def _generate_question(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        question_number: int,
        question_total: int,
        session_seed: str,
        history_prompts: list[str],
    ) -> InterviewQuestion:
        sources = focus["sources"]
        focus_topic = focus["topic"]
        source_keywords = self._source_keywords(sources)
        draft = self.question_composer.compose(
            role=role,
            profile=profile,
            focus=focus,
            question_number=question_number,
            source_keywords=source_keywords,
            history_prompts=history_prompts,
            global_history_prompts=[],
            session_seed=session_seed,
        )
        return InterviewQuestion(
            id=str(uuid4()),
            index=question_number,
            total=question_total,
            type=focus["question_type"],
            difficulty=focus["difficulty"],
            stage=focus["stage"],
            prompt=draft.prompt,
            hint=draft.hint,
            focus_topic=focus_topic,
            query=focus["query"],
            sources=sources,
            rationale=draft.rationale,
        )

    def _build_query(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        anchor: dict,
        question_type: str,
        difficulty: str,
        index: int,
    ) -> str:
        anchor_text = " ".join(
            [
                anchor.get("label", ""),
                anchor.get("text", ""),
                " ".join(anchor.get("skills", [])),
                str(anchor.get("selected_lens", "")),
                str(anchor.get("category", "")),
                str(anchor.get("scenario", "")),
                str(anchor.get("theory_topic", "")),
                profile.summary,
            ]
        )
        role_topics = " ".join(role.core_topics[index % len(role.core_topics) : index % len(role.core_topics) + 2])
        bucket = anchor.get("bucket", anchor.get("type", "general"))
        return (
            f"{role.label} balanced technical interview bucket {bucket} {question_type} "
            f"{difficulty} difficulty target anchor {anchor_text} role topics {role_topics} "
            f"senior interviewer realistic company problem concepts tradeoffs implementation "
            f"debugging architecture validation performance security scalability"
        )

    def _candidate_anchors(self, role: RoleDefinition, profile: ResumeProfile) -> list[dict]:
        anchors: list[dict] = []
        for project in profile.projects:
            anchors.append(
                {
                    "type": "project",
                    "label": project.name,
                    "text": project.description,
                    "skills": project.technologies or self._terms_for_text(project.description, profile),
                    "project": project.model_dump(),
                }
            )
        for experience in [*profile.work_experience, *profile.internships]:
            anchors.append(
                {
                    "type": "experience",
                    "label": experience.title,
                    "text": experience.description,
                    "skills": experience.technologies or self._terms_for_text(experience.description, profile),
                    "experience": experience.model_dump(),
                }
            )
        for certification in profile.certifications[:4]:
            anchors.append(
                {
                    "type": "certification",
                    "label": certification,
                    "text": certification,
                    "skills": self._terms_for_text(certification, profile),
                }
            )
        for skill in self._role_weighted_terms(role, profile)[:10]:
            anchors.append(
                {
                    "type": "skill",
                    "label": skill,
                    "text": f"{skill} in the context of {role.label}",
                    "skills": [skill],
                }
            )
        for topic in role.core_topics:
            anchors.append(
                {
                    "type": "role_concept",
                    "label": topic,
                    "text": f"{topic} for {role.label}",
                    "skills": self._terms_for_text(topic, profile),
                }
            )
        return anchors or [
            {
                "type": "resume",
                "label": profile.summary,
                "text": profile.full_text_digest or profile.summary,
                "skills": profile.skills[:4],
            }
        ]

    def _role_weighted_terms(self, role: RoleDefinition, profile: ResumeProfile) -> list[str]:
        terms = [
            *profile.skills,
            *profile.technologies,
            *profile.frameworks,
            *profile.tools,
            *profile.domain_expertise,
        ]
        role_text = " ".join(role.core_topics + role.query_seeds).lower()
        scored: list[tuple[str, int]] = []
        generic_tokens = {"systems", "system", "engineering", "engineer", "design", "role", "using"}
        for term in dict.fromkeys(terms):
            lowered = term.lower()
            score = 3 if lowered in role_text else 1
            score += sum(1 for token in lowered.split() if token not in generic_tokens and token in role_text)
            scored.append((term, score))
        ranked = sorted(scored, key=lambda item: (-item[1], item[0]))
        relevant = [term for term, score in ranked if score >= 2]
        return relevant or [term for term, _ in ranked[:8]]

    def _anchor_relevance(self, role: RoleDefinition, anchor: dict) -> int:
        role_text = " ".join(role.core_topics + role.query_seeds).lower()
        anchor_text = " ".join(
            [
                str(anchor.get("label", "")),
                str(anchor.get("text", "")),
                " ".join(anchor.get("skills", [])),
            ]
        ).lower()
        return sum(1 for token in re.findall(r"[a-z][a-z0-9+.#-]{2,}", role_text) if token in anchor_text)

    def _question_type_sequence(
        self,
        profile: ResumeProfile,
        question_count: int,
        rng: random.Random,
    ) -> list[str]:
        pool = [
            "project",
            "scenario",
            "debugging",
            "coding",
            "architecture",
            "theoretical",
            "problem_solving",
            "behavioral",
        ]
        if not profile.projects:
            pool.remove("project")
        if profile.seniority in {"early-career", "emerging"}:
            pool.insert(1, "theoretical")
        rng.shuffle(pool)
        if profile.projects and "project" in pool:
            pool.insert(0, pool.pop(pool.index("project")))
        sequence: list[str] = []
        while len(sequence) < question_count:
            sequence.extend(pool)
            rng.shuffle(pool)
        return sequence[:question_count]

    def _difficulty_sequence(
        self,
        profile: ResumeProfile,
        question_count: int,
        rng: random.Random,
    ) -> list[str]:
        if profile.seniority in {"advanced", "intermediate"}:
            base = ["medium", "hard", "medium", "hard", "easy"]
        elif profile.seniority == "early-career":
            base = ["easy", "medium", "easy", "medium", "hard"]
        else:
            base = ["easy", "medium", "medium", "hard", "medium"]
        offset = rng.randrange(len(base))
        sequence = [base[(offset + index) % len(base)] for index in range(question_count)]
        if sequence:
            sequence[0] = "easy" if profile.seniority == "early-career" else "medium"
        return sequence

    def _focus_topic(self, anchor: dict, selected, role: RoleDefinition, index: int) -> str:
        label = str(anchor.get("label") or role.core_topics[index % len(role.core_topics)])
        source_topic = selected.topic if selected else role.core_topics[index % len(role.core_topics)]
        if str(source_topic).lower() in {"role expectations", "overview", "general"}:
            source_topic = role.core_topics[index % len(role.core_topics)]
        if anchor.get("bucket") == "skill":
            return f"{label}: {anchor.get('selected_lens') or source_topic}"
        if anchor.get("type") == "project":
            return f"{label}: {anchor.get('selected_lens') or source_topic}"
        if anchor.get("bucket") == "scenario":
            return f"{label}: {source_topic}"
        if anchor.get("bucket") == "theory":
            return f"{label} fundamentals"
        if anchor.get("type") == "skill":
            return f"{label} depth in {source_topic}"
        return f"{label} and {source_topic}"

    def _stage_label(self, anchor: dict, question_type: str) -> str:
        bucket = anchor.get("bucket")
        if bucket == "skill":
            return "Resume Skill Deep Dive"
        if bucket == "project":
            return "Project Rotation"
        if bucket == "scenario":
            return "Real-World Scenario"
        if bucket == "theory":
            return "Core Fundamentals"
        label = str(anchor.get("type", "resume")).replace("_", " ").title()
        type_label = question_type.replace("_", " ").title()
        if label.lower() == type_label.lower():
            return f"{label} Deep Dive"
        return f"{label} {type_label}"

    def _adaptive_query(
        self,
        role: RoleDefinition,
        planned_focus: dict,
        previous_question: InterviewQuestion,
        answer_terms: list[str],
        score: int,
    ) -> str:
        depth = "advanced tradeoffs failure modes" if score >= 80 else "fundamentals examples" if score < 45 else "applied follow-up"
        return (
            f"{role.label} {planned_focus.get('question_type')} {planned_focus.get('difficulty')} "
            f"{planned_focus.get('topic')} following previous topic {previous_question.focus_topic} "
            f"answer terms {' '.join(answer_terms[:6])} {depth} validation observability"
        )

    def _answer_terms(self, answer_text: str, profile: ResumeProfile) -> list[str]:
        answer_lower = answer_text.lower()
        candidates = [
            *profile.skills,
            *profile.technologies,
            *profile.frameworks,
            *profile.tools,
            *profile.domain_expertise,
        ]
        matched = [term for term in candidates if term.lower() in answer_lower]
        if matched:
            return matched
        tokens = re.findall(r"[a-z][a-z0-9+.#-]{3,}", answer_lower)
        stop = {"that", "this", "with", "would", "should", "could", "have", "from", "then", "first"}
        return [token for token in tokens if token not in stop][:8]

    def _stretch_question_type(self, previous_type: str) -> str:
        transitions = {
            "theoretical": "scenario",
            "scenario": "debugging",
            "debugging": "architecture",
            "coding": "problem_solving",
            "project": "architecture",
            "behavioral": "project",
            "architecture": "debugging",
            "problem_solving": "architecture",
            "open": "scenario",
            "code": "problem_solving",
            "system": "debugging",
        }
        return transitions.get(previous_type, "scenario")

    def _role_alignment_score(self, role: RoleDefinition, profile: ResumeProfile) -> int:
        resume_terms = " ".join(
            profile.skills
            + profile.technologies
            + profile.frameworks
            + profile.tools
            + profile.domains
            + profile.domain_expertise
            + profile.highlights
        ).lower()
        topic_hits = 0
        for topic in role.core_topics:
            topic_tokens = [token for token in topic.split() if len(token) > 3]
            if any(token in resume_terms for token in topic_tokens):
                topic_hits += 1
        seniority_bonus = {"early-career": 0, "emerging": 1, "intermediate": 2, "advanced": 3}.get(
            profile.seniority,
            1,
        )
        years_bonus = min(profile.experience_years or 0, 5) // 2
        return topic_hits + seniority_bonus + years_bonus

    def _shift_difficulty(self, difficulty: str, shift: int) -> str:
        aliases = {"warmup": "easy", "core": "medium", "deep": "hard", "system": "hard"}
        difficulty = aliases.get(difficulty, difficulty)
        order = ["easy", "medium", "hard"]
        try:
            index = order.index(difficulty)
        except ValueError:
            return "medium"
        return order[max(0, min(len(order) - 1, index + shift))]

    def _terms_for_text(self, text: str, profile: ResumeProfile) -> list[str]:
        lowered = text.lower()
        terms = [
            *profile.skills,
            *profile.technologies,
            *profile.frameworks,
            *profile.tools,
            *profile.domain_expertise,
        ]
        return [term for term in terms if term.lower() in lowered][:8]

    def _source_keywords(self, sources: list[dict]) -> list[str]:
        keywords: list[str] = []
        seen: set[str] = set()
        for source in sources:
            for keyword in source.get("metadata", {}).get("keywords", []):
                keyword = str(keyword)
                if keyword in seen:
                    continue
                seen.add(keyword)
                keywords.append(keyword)
        return keywords

    def _choose_primary_source(self, sources, used_topics: set[str]):
        for source in sources:
            if source.topic not in used_topics:
                return source
        return sources[0] if sources else None

    def _session_question_prompts(self, session: InterviewSessionModel) -> list[str]:
        prompts: list[str] = []
        for turn in session.turns:
            payload = turn.question_payload or {}
            prompt = payload.get("prompt")
            if prompt:
                prompts.append(str(prompt))
        return prompts

    def _recent_question_prompts(
        self,
        role_value: str,
        limit: int = 60,
        exclude_session_id: str | None = None,
    ) -> list[str]:
        query = (
            self.db.query(InterviewTurnModel)
            .join(InterviewSessionModel, InterviewTurnModel.session_id == InterviewSessionModel.id)
            .filter(InterviewSessionModel.role == role_value)
            .order_by(InterviewTurnModel.asked_at.desc())
            .limit(limit)
        )
        prompts: list[str] = []
        for turn in query:
            if exclude_session_id and turn.session_id == exclude_session_id:
                continue
            payload = turn.question_payload or {}
            prompt = payload.get("prompt")
            if prompt:
                prompts.append(str(prompt))
        return prompts

    def _get_active_turn(self, session: InterviewSessionModel) -> InterviewTurnModel | None:
        target_index = session.current_question_index + 1
        for turn in session.turns:
            if turn.question_index == target_index:
                return turn
        return None

    def _build_summary(self, session: InterviewSessionModel) -> SessionSummary:
        turns = [
            InterviewTurn(
                question=InterviewQuestion.model_validate(turn.question_payload),
                answer=turn.answer_text or "",
                answer_seconds=turn.answer_seconds or 0,
                evaluation=turn.evaluation_payload,
            )
            for turn in session.turns
            if turn.answer_text and turn.evaluation_payload
        ]
        duration_sec = int(
            ((session.completed_at or datetime.utcnow()) - session.started_at).total_seconds()
        )
        insights = build_session_insights(turns)
        results = [
            InterviewResult(
                index=turn.question.index,
                question=turn.question.prompt,
                candidate_answer=self._clean_report_answer(turn.answer),
                expected_answer=turn.evaluation.expected_answer,
                ai_evaluation=turn.evaluation,
                score=turn.evaluation.score,
                score_out_of_10=round(turn.evaluation.score / 10, 1),
                improvement_suggestion=turn.evaluation.improvement_suggestion
                or (turn.evaluation.improvements[0] if turn.evaluation.improvements else ""),
                answer_seconds=turn.answer_seconds,
            )
            for turn in turns
        ]
        return SessionSummary(
            session_id=session.id,
            role=session.role,
            candidate=session.candidate_name,
            duration_sec=duration_sec,
            resume_profile=ResumeProfile.model_validate(session.resume_profile),
            results=results,
            transcript=turns,
            insights=insights,
        )

    def _clean_report_answer(self, answer: str, limit: int = 700) -> str:
        cleaned = re.sub(r"\s+", " ", answer.strip())
        return cleaned[: limit - 3].rstrip() + "..." if len(cleaned) > limit else cleaned
