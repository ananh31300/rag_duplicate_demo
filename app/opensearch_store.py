from __future__ import annotations

from datetime import date

from opensearchpy import OpenSearch

from app.models import SearchHit
from app.interfaces import Embedder
from app.postgres import PostgresManifest


class OpenSearchVectorStore:
    def __init__(self, url: str, index: str, manifest: PostgresManifest, embedder: Embedder) -> None:
        self._client = OpenSearch(url, timeout=30)
        self._index = index
        self._manifest = manifest
        self._embedder = embedder

    def reset(self) -> None:
        if self._client.indices.exists(index=self._index):
            self._client.indices.delete(index=self._index)
        self._client.indices.create(
            index=self._index,
            body={"mappings": {"properties": {
                "embedding": {"type": "knn_vector", "dimension": self._embedder.dimensions},
                "instrument_id": {"type": "keyword"},
                "version_id": {"type": "keyword"},
                "semantic_chunk_id": {"type": "keyword"},
                "text": {"type": "text"},
                "effective_from": {"type": "date"},
                "effective_to": {"type": "date"}
            }}},
        )

    def stage_version(self, version_id: str) -> int:
        with self._manifest.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT dv.instrument_id, lc.semantic_chunk_id, lc.chunk_hash, lc.text,
                          lc.effective_from, lc.effective_to
                   FROM legal_chunk lc JOIN document_version dv ON dv.version_id=lc.version_id
                   WHERE lc.version_id=%s ORDER BY lc.semantic_chunk_id""",
                (version_id,),
            )
            rows = cursor.fetchall()
        for row in rows:
            document_id = f"{version_id}:{row['semantic_chunk_id']}:{row['chunk_hash'][:12]}"
            self._client.index(
                index=self._index,
                id=document_id,
                body={
                    "instrument_id": row["instrument_id"],
                    "version_id": version_id,
                    "semantic_chunk_id": row["semantic_chunk_id"],
                    "text": row["text"],
                    "embedding": self._embedder.embed(row["text"]),
                    "effective_from": row["effective_from"].isoformat(),
                    "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
                },
                refresh=True,
            )
        return len(rows)

    def search(self, query: str, as_of: date, top_k: int = 3) -> list[SearchHit]:
        active_versions = self._manifest.active_version_ids(as_of)
        if not active_versions:
            return []
        response = self._client.search(
            index=self._index,
            body={
                "size": top_k,
                "query": {"script_score": {
                    "query": {"bool": {"filter": [
                        {"terms": {"version_id": active_versions}},
                        {"range": {"effective_from": {"lte": as_of.isoformat()}}},
                        {"bool": {"should": [
                            {"bool": {"must_not": {"exists": {"field": "effective_to"}}}},
                            {"range": {"effective_to": {"gt": as_of.isoformat()}}}
                        ], "minimum_should_match": 1}}
                    ]}},
                    "script": {
                        "source": "cosineSimilarity(params.query, doc['embedding']) + 1.0",
                        "params": {"query": self._embedder.embed(query)},
                    },
                }},
            },
        )
        hits: list[SearchHit] = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            hits.append(SearchHit(
                instrument_id=source["instrument_id"],
                version_id=source["version_id"],
                semantic_chunk_id=source["semantic_chunk_id"],
                text=source["text"],
                score=float(hit["_score"]),
                effective_from=date.fromisoformat(source["effective_from"]),
                effective_to=date.fromisoformat(source["effective_to"]) if source.get("effective_to") else None,
            ))
        return hits

    def document_count(self) -> int:
        self._client.indices.refresh(index=self._index)
        return int(self._client.count(index=self._index)["count"])

