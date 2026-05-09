from __future__ import annotations

import hashlib
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import CrossEncoder
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

SHARED_COLLECTION_NAME = "shared_source_knowledge"
EXCLUDED_SOURCE_NAME_PARTS = (
    "assignment",
    "intern assignment",
)


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
        self._reranker: CrossEncoder | None = None

    def ensure_seeded(self, force: bool = False) -> dict[str, int]:
        primary_docs = self._source_documents()
        if primary_docs:
            count = self._ensure_shared_seeded(force=force)
            return {role.value: count for role in list_roles()}

        seeded: dict[str, int] = {}
        for role in list_roles():
            seeded[role.value] = self._ensure_role_seeded(role.value, force=force)
        return seeded

    def retrieve(self, role_value: str, queries: list[str], top_k: int | None = None) -> list[RetrievedSource]:
        role = get_role(role_value)
        collection = self._get_retrieval_collection(role.value)
        top_k = top_k or self.settings.retrieval_top_k
        collection_count = collection.count()
        if collection_count == 0:
            return []

        merged: dict[str, RetrievedSource] = {}
        candidate_k = min(max(top_k * 4, top_k), collection_count)
        for query in queries:
            result = collection.query(
                query_texts=[query],
                n_results=candidate_k,
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

        candidates = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        if self.settings.enable_reranking and candidates:
            candidates = self._rerank(" ".join(queries), candidates)
        return candidates[:top_k]

    def _ensure_role_seeded(self, role_value: str, force: bool = False) -> int:
        role = get_role(role_value)
        collection = self._get_collection(role_value)
        if collection.count() and not force and self._collection_is_current(collection):
            return collection.count()
        if collection.count() and not self._collection_is_current(collection):
            self.client.delete_collection(role.collection_name)
            collection = self._create_collection(role_value)
        if force and collection.count():
            self.client.delete_collection(role.collection_name)
            collection = self._create_collection(role_value)

        chunks = self._load_role_chunks(role)
        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def _ensure_shared_seeded(self, force: bool = False) -> int:
        collection = self._get_shared_collection()
        if collection.count() and not force and self._collection_is_current(collection):
            return collection.count()
        if collection.count() and not self._collection_is_current(collection):
            self.client.delete_collection(SHARED_COLLECTION_NAME)
            collection = self._create_shared_collection()
        if force and collection.count():
            self.client.delete_collection(SHARED_COLLECTION_NAME)
            collection = self._create_shared_collection()

        chunks = self._load_source_chunks()
        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def source_status(self) -> dict[str, dict]:
        status: dict[str, dict] = {}
        primary_docs = self._source_documents()
        for role in list_roles():
            status[role.value] = {
                "primary_source": bool(primary_docs),
                "documents": [path.name for path in primary_docs],
                "fallback_file": role.knowledge_file,
                "collection": SHARED_COLLECTION_NAME if primary_docs else role.collection_name,
            }
        return status

    def _get_retrieval_collection(self, role_value: str) -> Collection:
        if self._source_documents():
            return self._get_shared_collection()
        return self._get_collection(role_value)

    def _get_shared_collection(self) -> Collection:
        try:
            return self.client.get_collection(
                SHARED_COLLECTION_NAME,
                embedding_function=self.embedding_function,
            )
        except Exception:
            return self._create_shared_collection()

    def _create_shared_collection(self) -> Collection:
        return self.client.get_or_create_collection(
            SHARED_COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={
                "description": "Shared source knowledge base",
                "embedding_model": self.settings.embedding_model_name,
            },
        )

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
            metadata={
                "description": role.label,
                "embedding_model": self.settings.embedding_model_name,
            },
        )

    def _collection_is_current(self, collection: Collection) -> bool:
        metadata = collection.metadata or {}
        return metadata.get("embedding_model") == self.settings.embedding_model_name

    def _load_role_chunks(self, role) -> list[dict]:
        fallback_path = self.settings.knowledge_base_dir / role.knowledge_file
        return self._chunk_markdown(fallback_path, role.value, "fallback_corpus")

    def _load_source_chunks(self) -> list[dict]:
        chunks: list[dict] = []
        for path in self._source_documents():
            if path.suffix.lower() == ".pdf":
                chunks.extend(self._chunk_pdf(path, "shared", "primary_book"))
            else:
                chunks.extend(self._chunk_text_document(path, "shared", "primary_corpus"))
        return chunks

    def _source_documents(self) -> list[Path]:
        source_dir = self.settings.knowledge_base_dir / "source_docs"
        if not source_dir.exists():
            return []
        return sorted(
            path
            for path in source_dir.iterdir()
            if path.is_file() and self._is_supported_source_file(path)
        )

    def _is_supported_source_file(self, path: Path) -> bool:
        supported = {".pdf", ".txt", ".md", ".markdown"}
        lowered_name = path.name.lower()
        if lowered_name == "readme.md":
            return False
        if any(name_part in lowered_name for name_part in EXCLUDED_SOURCE_NAME_PARTS):
            return False
        return path.suffix.lower() in supported

    def _chunk_pdf(self, path: Path, role_value: str, source_kind: str) -> list[dict]:
        reader = PdfReader(str(path))
        chunks: list[dict] = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            chunks.extend(
                self._chunk_text(
                    text=page_text,
                    source_file=path.name,
                    title=path.stem.replace("-", " ").replace("_", " ").title(),
                    role_value=role_value,
                    source_kind=source_kind,
                    base_metadata={"page": page_number},
                )
            )
        return chunks

    def _chunk_text_document(self, path: Path, role_value: str, source_kind: str) -> list[dict]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return self._chunk_text(
            text=text,
            source_file=path.name,
            title=path.stem.replace("-", " ").replace("_", " ").title(),
            role_value=role_value,
            source_kind=source_kind,
            base_metadata={},
        )

    def _chunk_markdown(self, path: Path, role_value: str, source_kind: str) -> list[dict]:
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
            chunks.extend(
                self._chunk_text(
                    text=body,
                    source_file=path.name,
                    title=heading,
                    role_value=role_value,
                    source_kind=source_kind,
                    base_metadata={},
                )
            )
        return chunks

    def _chunk_text(
        self,
        text: str,
        source_file: str,
        title: str,
        role_value: str,
        source_kind: str,
        base_metadata: dict,
    ) -> list[dict]:
        words = text.split()
        if not words:
            return []

        chunks: list[dict] = []
        start = 0
        chunk_index = 0
        while start < len(words):
            end = min(len(words), start + 260)
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            topic = self._infer_topic(title, chunk_text)
            chunk_id = hashlib.sha1(
                f"{role_value}:{source_file}:{title}:{base_metadata}:{chunk_index}".encode()
            ).hexdigest()
            keywords = self._extract_keywords(chunk_text)
            metadata = {
                "source_file": source_file,
                "source_kind": source_kind,
                "title": title,
                "topic": topic,
                "keywords": ", ".join(keywords),
                **base_metadata,
            }
            chunks.append({"id": chunk_id, "text": chunk_text, "metadata": metadata})
            if end == len(words):
                break
            start = max(end - 70, start + 1)
            chunk_index += 1
        return chunks

    def _rerank(self, query: str, sources: list[RetrievedSource]) -> list[RetrievedSource]:
        try:
            if self._reranker is None:
                self._reranker = CrossEncoder(self.settings.reranker_model_name)
            pairs = [(query, f"{source.title}\n{source.excerpt}") for source in sources]
            rerank_scores = self._reranker.predict(pairs)
        except Exception:
            return sources

        scored_sources: list[RetrievedSource] = []
        for source, rerank_score in zip(sources, rerank_scores):
            normalized_score = float(rerank_score)
            source.metadata["rerank_score"] = round(normalized_score, 4)
            source.score = round(source.score * 0.35 + normalized_score * 12.0, 2)
            scored_sources.append(source)
        return sorted(scored_sources, key=lambda item: item.score, reverse=True)

    def _infer_topic(self, title: str, text: str) -> str:
        title_topic = title.strip().lower()
        if title_topic and title_topic != "overview":
            return title_topic
        keywords = self._extract_keywords(text)
        return " ".join(keywords[:3]) if keywords else "general"

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
