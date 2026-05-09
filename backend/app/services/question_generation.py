from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.config import get_settings
from backend.app.roles import RoleDefinition
from backend.app.schemas import ResumeProfile


@dataclass(frozen=True)
class QuestionDraft:
    prompt: str
    hint: str | None
    rationale: str


class QuestionComposer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._pipeline = None

    def compose(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        question_number: int,
        source_keywords: list[str],
    ) -> QuestionDraft:
        evidence = self._evidence_sentence(focus)
        generated = self._try_model_question(role, profile, focus, evidence, source_keywords)
        prompt = generated or self._compose_evidence_question(
            role=role,
            profile=profile,
            focus=focus,
            evidence=evidence,
            source_keywords=source_keywords,
        )
        hint = self._build_hint(focus, source_keywords, evidence)
        rationale = self._build_rationale(role, profile, focus, question_number, evidence)
        return QuestionDraft(prompt=prompt, hint=hint, rationale=rationale)

    def _try_model_question(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        evidence: str,
        source_keywords: list[str],
    ) -> str | None:
        if not self.settings.enable_local_question_generation:
            return None

        try:
            if self._pipeline is None:
                from transformers import pipeline

                self._pipeline = pipeline(
                    "text2text-generation",
                    model=self.settings.question_generator_model_name,
                    tokenizer=self.settings.question_generator_model_name,
                    device=-1,
                )
            model_input = (
                "Write one specific technical interview question. "
                f"Role: {role.label}. Candidate profile: {profile.summary}. "
                f"Question type: {focus['question_type']}. Difficulty: {focus['difficulty']}. "
                f"Focus topic: {focus['topic']}. Source evidence: {evidence}. "
                f"Important terms: {', '.join(source_keywords[:6])}. "
                "Ask for reasoning, tradeoffs, and validation. Return only the question."
            )
            output = self._pipeline(model_input, max_new_tokens=96, do_sample=False)[0]
            return self._clean_question(output.get("generated_text", ""))
        except Exception:
            return None

    def _compose_evidence_question(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        evidence: str,
        source_keywords: list[str],
    ) -> str:
        candidate_anchor = ", ".join(profile.skills[:3] or profile.domains[:2] or ["your recent work"])
        topic = focus["topic"]
        keyword_text = ", ".join(source_keywords[:4]) if source_keywords else topic
        difficulty = focus["difficulty"]
        question_type = focus["question_type"]

        if question_type == "open":
            ask = (
                "describe a real project decision, the tradeoff you accepted, and how you measured whether it worked"
            )
        elif question_type == "code":
            ask = (
                "sketch the implementation path, including data structures, APIs or pipeline steps, and the checks you would add"
            )
        elif question_type == "system":
            ask = (
                "design the production architecture, including scaling limits, observability, rollout risk, and failure recovery"
            )
        else:
            ask = (
                "diagnose a realistic failure, explain likely causes, and prioritize fixes with validation signals"
            )

        article = "an" if role.label[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
        return (
            f"For {article} {role.label} screen at {difficulty} depth, connect your background in {candidate_anchor} "
            f"to the source idea that {evidence}. Focusing on {topic} and {keyword_text}, can you {ask}?"
        )

    def _build_hint(self, focus: dict, source_keywords: list[str], evidence: str) -> str | None:
        checkpoints = source_keywords[:4]
        if checkpoints:
            return f"Consider: {', '.join(checkpoints)}."
        if evidence:
            return f"Ground your answer in: {evidence[:140]}."
        return None

    def _build_rationale(
        self,
        role: RoleDefinition,
        profile: ResumeProfile,
        focus: dict,
        question_number: int,
        evidence: str,
    ) -> str:
        source_mode = "primary source" if focus.get("source_mode") == "primary" else "fallback corpus"
        anchor = ", ".join(profile.skills[:2] or profile.domains[:2] or [role.label])
        return (
            f"Q{question_number} targets {focus['topic']} at {focus['difficulty']} difficulty using "
            f"{source_mode} retrieval. It connects {anchor} from the resume with the retrieved idea: {evidence}"
        )

    def _evidence_sentence(self, focus: dict) -> str:
        sources = focus.get("sources", [])
        if not sources:
            return focus.get("topic", "the selected role topic")

        keywords = set()
        for source in sources:
            keywords.update(source.get("metadata", {}).get("keywords", [])[:5])

        sentences: list[str] = []
        for source in sources[:3]:
            sentences.extend(self._split_sentences(source.get("excerpt", "")))

        if not sentences:
            return sources[0].get("excerpt", focus.get("topic", "the selected role topic"))[:220]

        def score(sentence: str) -> int:
            lowered = sentence.lower()
            return sum(1 for keyword in keywords if str(keyword).lower() in lowered)

        chosen = max(sentences, key=score)
        return chosen[:260].strip()

    def _split_sentences(self, text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if len(sentence.strip().split()) >= 8
        ]

    def _clean_question(self, generated_text: str) -> str | None:
        text = generated_text.strip().strip('"')
        text = re.sub(r"^(question|q)\s*[:.-]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text.split()) < 10:
            return None
        if not text.endswith("?"):
            text = f"{text}?"
        return text
