from __future__ import annotations

import hashlib
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.app.config import get_settings
from backend.app.roles import get_role, list_roles
from backend.app.schemas import RetrievedSource

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "into",
    "from",
    "your",
    "when",
    "where",
    "what",
    "how",
    "have",
    "will",
    "than",
    "then",
    "they",
    "their",
    "about",
    "should",
    "must",
    "also",
    "such",
    "each",
    "over",
    "under",
    "using",
    "used",
}


class KnowledgeBaseService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = chromadb.PersistentClient(
            path=str(settings.vector_store_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model_name
        )

    def ensure_seeded(self, force: bool = False) -> dict[str, int]:
        seeded: dict[str, int] = {}
        for role in list_roles():
            seeded[role.value] = self._ensure_role_seeded(role.value, force=force)
        return seeded

    def retrieve(self, role_value: str, queries: list[str], top_k: int | None = None) -> list[RetrievedSource]:
        role = get_role(role_value)
        collection = self._get_collection(role.value)
        top_k = top_k or self.settings.retrieval_top_k

        merged: dict[str, RetrievedSource] = {}
        for query in queries:
            result = collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            ids = result.get("ids", [[]])[0]

            for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
                semantic = 1.0 / (1.0 + float(distance or 0.0))
                lexical = self._lexical_overlap(query, document)
                score = round((semantic * 0.75 + lexical * 0.25) * 100, 2)
                normalized_metadata = dict(metadata or {})
                keyword_value = normalized_metadata.get("keywords", "")
                normalized_metadata["keywords"] = [
                    item.strip() for item in str(keyword_value).split(",") if item.strip()
                ]
                source = RetrievedSource(
                    chunk_id=chunk_id,
                    title=normalized_metadata.get("title", role.label),
                    topic=normalized_metadata.get("topic", "general"),
                    score=score,
                    excerpt=self._excerpt(document),
                    metadata=normalized_metadata,
                )
                existing = merged.get(chunk_id)
                if existing is None or source.score > existing.score:
                    merged[chunk_id] = source

        return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:top_k]

    def _ensure_role_seeded(self, role_value: str, force: bool = False) -> int:
        role = get_role(role_value)
        collection = self._get_collection(role_value)
        if collection.count() and not force:
            return collection.count()
        if force and collection.count():
            self.client.delete_collection(role.collection_name)
            collection = self._create_collection(role_value)

        document_path = self.settings.knowledge_base_dir / role.knowledge_file
        chunks = self._chunk_markdown(document_path)
        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def _get_collection(self, role_value: str) -> Collection:
        role = get_role(role_value)
        try:
            return self.client.get_collection(
                role.collection_name,
                embedding_function=self.embedding_function,
            )
        except Exception:
            return self._create_collection(role_value)

    def _create_collection(self, role_value: str) -> Collection:
        role = get_role(role_value)
        return self.client.get_or_create_collection(
            role.collection_name,
            embedding_function=self.embedding_function,
            metadata={"description": role.label},
        )

    def _chunk_markdown(self, path: Path) -> list[dict]:
        text = path.read_text(encoding="utf-8")
        sections: list[tuple[str, str]] = []
        current_heading = "Overview"
        current_lines: list[str] = []

        for line in text.splitlines():
            if line.startswith("#"):
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines).strip()))
                    current_lines = []
                current_heading = line.lstrip("#").strip()
                continue
            current_lines.append(line)

        if current_lines:
            sections.append((current_heading, "\n".join(current_lines).strip()))

        chunks: list[dict] = []
        for heading, body in sections:
            words = body.split()
            if not words:
                continue
            start = 0
            chunk_index = 0
            while start < len(words):
                end = min(len(words), start + 180)
                chunk_words = words[start:end]
                chunk_text = " ".join(chunk_words)
                chunk_id = hashlib.sha1(f"{path.name}:{heading}:{chunk_index}".encode()).hexdigest()
                keywords = self._extract_keywords(chunk_text)
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": chunk_text,
                        "metadata": {
                            "source_file": path.name,
                            "title": heading,
                            "topic": heading.lower(),
                            "keywords": ", ".join(keywords),
                        },
                    }
                )
                if end == len(words):
                    break
                start = max(end - 40, start + 1)
                chunk_index += 1
        return chunks

    def _extract_keywords(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z][a-z0-9/+.-]{2,}", text.lower())
        counts = Counter(token for token in tokens if token not in STOPWORDS)
        return [token for token, _ in counts.most_common(8)]

    def _lexical_overlap(self, query: str, document: str) -> float:
        q_terms = set(self._extract_keywords(query))
        d_terms = set(self._extract_keywords(document))
        if not q_terms:
            return 0.0
        return len(q_terms & d_terms) / len(q_terms)

    def _excerpt(self, text: str, limit: int = 280) -> str:
        return text[: limit - 3].strip() + "..." if len(text) > limit else text.strip()


@lru_cache
def get_knowledge_service() -> KnowledgeBaseService:
    return KnowledgeBaseService()
