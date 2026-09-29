import math

from ..config import settings


def _normalize(vector):
    vector = [float(value) for value in vector or []]
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


class MemoryVectorStore:
    """Ephemeral in-process cosine index. Used when Chroma is unavailable, e.g. serverless builds."""

    def __init__(self):
        self._rows: dict[str, dict] = {}

    def add(self, chunk_id: int, document_id: int, filename: str, page: int, text: str, embedding: list[float]):
        self._rows[str(chunk_id)] = {
            "document_id": document_id,
            "filename": filename,
            "page": page,
            "text": text,
            "vector": _normalize(embedding),
        }

    def delete_document(self, document_id: int):
        for key in [k for k, row in self._rows.items() if row["document_id"] == document_id]:
            self._rows.pop(key, None)

    def search(self, query_embedding: list[float], limit: int = 5):
        if not self._rows:
            return []
        query = _normalize(query_embedding)
        scored = []
        for row in self._rows.values():
            similarity = sum(a * b for a, b in zip(query, row["vector"]))
            scored.append((row, max(0.0, min(1.0, similarity))))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            {
                "document_id": row["document_id"],
                "filename": row["filename"],
                "page": row["page"],
                "excerpt": row["text"],
                "relevance_score": round(score, 4),
            }
            for row, score in scored[:limit]
        ]


class ChromaVectorStore:
    """Persistent local Chroma collection. Chroma telemetry is explicitly disabled."""

    def __init__(self):
        import chromadb

        self.client = chromadb.PersistentClient(
            path=settings.chroma_path, settings=chromadb.Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            "sentinel_enterprise_knowledge", metadata={"hnsw:space": "cosine"}
        )

    def add(self, chunk_id: int, document_id: int, filename: str, page: int, text: str, embedding: list[float]):
        self.collection.upsert(
            ids=[str(chunk_id)],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{"document_id": document_id, "filename": filename, "page": page}],
        )

    def delete_document(self, document_id: int):
        self.collection.delete(where={"document_id": document_id})

    def search(self, query_embedding: list[float], limit: int = 5):
        if self.collection.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "document_id": int(meta["document_id"]),
                "filename": meta["filename"],
                "page": int(meta["page"]),
                "excerpt": text,
                "relevance_score": round(max(0.0, 1.0 - float(distance)), 4),
            }
            for text, meta, distance in zip(
                result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]


_store = None


def vector_store():
    global _store
    if _store is None:
        if settings.serverless:
            _store = MemoryVectorStore()
        else:
            try:
                _store = ChromaVectorStore()
            except Exception:
                _store = MemoryVectorStore()
    return _store


def vector_store_kind() -> str:
    return type(vector_store()).__name__
