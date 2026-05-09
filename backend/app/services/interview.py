from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import InterviewSession as InterviewSessionModel
from backend.app.db.models import InterviewTurn as InterviewTurnModel
from backend.app.roles import QuestionBlueprint, RoleDefinition, get_role
from backend.app.schemas import (
    AnswerResponse,
    InterviewQuestion,
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
        plan = self._build_interview_plan(role, profile)
        first_focus = plan["focus_areas"][0]
        first_question = self._generate_question(role, profile, first_focus, question_number=1)

        session = InterviewSessionModel(
            candidate_name=profile.candidate_name,
            role=role.value,
            resume_filename=resume_filename,
            resume_text=resume_text,
            resume_profile=jsonable_encoder(profile),
            interview_plan=plan,
            total_questions=self.settings.interview_question_count,
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
        evaluation = evaluate_answer(question, payload.answer_text)
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
        role = get_role(session.role)
        profile = ResumeProfile.model_validate(session.resume_profile)
        plan = session.interview_plan
        blueprint = role.blueprints[answered_count]
        next_focus = self._select_next_focus(role, profile, plan, blueprint, question, evaluation)
        next_question = self._generate_question(
            role,
            profile,
            next_focus,
            question_number=answered_count + 1,
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
            return SessionSummary.model_validate(session.summary)
        if session.status != "completed":
            raise ValueError("Interview session is still in progress.")
        summary = self._build_summary(session)
        session.summary = jsonable_encoder(summary)
        self.db.commit()
        return summary

    def _build_interview_plan(self, role: RoleDefinition, profile: ResumeProfile) -> dict:
        focus_areas = []
        used_topics: set[str] = set()
        for blueprint in role.blueprints:
            query = self._build_query(role, profile, blueprint)
            retrieved = self.knowledge.retrieve(role.value, [query], top_k=self.settings.retrieval_top_k)
            selected = self._choose_primary_source(retrieved, used_topics)
            topic = selected.topic if selected else blueprint.stage.lower()
            used_topics.add(topic)
            difficulty = self._calibrate_difficulty(role, profile, blueprint)
            source_mode = "primary" if any(
                source.metadata.get("source_kind", "").startswith("primary") for source in retrieved
            ) else "fallback"
            focus_areas.append(
                {
                    "stage": blueprint.stage,
                    "question_type": blueprint.question_type,
                    "difficulty": difficulty,
                    "base_difficulty": blueprint.difficulty,
                    "lens": blueprint.lens,
                    "query": query,
                    "topic": topic,
                    "sources": [source.model_dump() for source in retrieved],
                    "source_mode": source_mode,
                }
            )
        return {
            "candidate_summary": profile.summary,
            "focus_areas": focus_areas,
        }

    def _select_next_focus(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        plan: dict,
        blueprint: QuestionBlueprint,
        previous_question: InterviewQuestion,
        evaluation,
    ) -> dict:
        next_index = previous_question.index
        planned_focus = plan["focus_areas"][next_index]
        if evaluation.score >= 80:
            planned_focus["difficulty"] = self._shift_difficulty(planned_focus["difficulty"], 1)
            planned_focus["stage"] = f"{blueprint.stage} Stretch"
            return planned_focus
        if evaluation.score >= 35:
            return planned_focus

        adaptive_query = (
            f"{role.label} fundamentals for {previous_question.focus_topic} "
            f"with failure modes, tradeoffs, and concrete validation steps"
        )
        adaptive_sources = self.knowledge.retrieve(
            role.value,
            [adaptive_query, planned_focus["query"]],
            top_k=self.settings.retrieval_top_k,
        )
        planned_focus["query"] = adaptive_query
        planned_focus["topic"] = previous_question.focus_topic
        planned_focus["question_type"] = "scenario"
        planned_focus["difficulty"] = self._shift_difficulty(previous_question.difficulty, -1)
        planned_focus["stage"] = f"{blueprint.stage} Follow-up"
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
        )
        return InterviewQuestion(
            id=str(uuid4()),
            index=question_number,
            total=self.settings.interview_question_count,
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
        blueprint: QuestionBlueprint,
    ) -> str:
        anchors = profile.skills[:3] or profile.domains[:2] or list(role.core_topics[:2])
        anchor = anchors[0]
        lens_queries = {
            "candidate_background": f"{role.label} interview topics tied to {anchor} and practical project tradeoffs",
            "retrieval": f"{role.label} retrieval augmented generation chunking embeddings reranking using {anchor}",
            "implementation": f"{role.label} implementation design tradeoffs for {anchor}",
            "evaluation": f"{role.label} evaluation failure modes monitoring feedback loops around {anchor}",
            "production": f"{role.label} production architecture scalability monitoring for {anchor}",
            "service_debugging": f"{role.label} latency debugging database api reliability for {anchor}",
            "reliability": f"{role.label} idempotency consistency observability incident response around {anchor}",
            "frontend_state": f"{role.label} react rendering state management browser performance around {anchor}",
            "quality": f"{role.label} quality testing accessibility observability validation around {anchor}",
            "tradeoffs": f"{role.label} product architecture client server boundaries tradeoffs around {anchor}",
            "pipeline": f"{role.label} pipeline orchestration data quality lineage around {anchor}",
            "incident_response": f"{role.label} incident response slo observability rollback around {anchor}",
        }
        return lens_queries.get(
            blueprint.lens,
            f"{role.label} {blueprint.stage.lower()} {anchor}",
        )

    def _calibrate_difficulty(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        blueprint: QuestionBlueprint,
    ) -> str:
        score = self._role_alignment_score(role, profile)
        shift = 0
        if score >= 4:
            shift = 1
        elif score <= 1 and blueprint.difficulty in {"deep", "system"}:
            shift = -1
        return self._shift_difficulty(blueprint.difficulty, shift)

    def _role_alignment_score(self, role: RoleDefinition, profile: ResumeProfile) -> int:
        resume_terms = " ".join(
            profile.skills + profile.technologies + profile.domains + profile.highlights
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
        order = ["warmup", "core", "deep", "system"]
        try:
            index = order.index(difficulty)
        except ValueError:
            return "core"
        return order[max(0, min(len(order) - 1, index + shift))]

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
        return SessionSummary(
            session_id=session.id,
            role=session.role,
            candidate=session.candidate_name,
            duration_sec=duration_sec,
            resume_profile=ResumeProfile.model_validate(session.resume_profile),
            transcript=turns,
            insights=insights,
        )
