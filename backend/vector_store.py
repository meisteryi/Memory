import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

DEFAULT_CHROMA_DIR = os.environ.get("CHROMA_DIR", "chroma_data")
COLLECTION_NAME = "gallery_photos"

class VectorStore:
    def __init__(self, persist_dir: str = DEFAULT_CHROMA_DIR):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    def add_or_update_photo(
        self,
        photo_id: str,
        text_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        단일 사진 벡터 인덱싱:
        text_content = background_details + " " + people_traits + " " + atmosphere + " " + location_name
        """
        meta = metadata or {}
        # ChromaDB 메타데이터는 bool, int, float, str 만 허용
        sanitized_meta = {
            k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))
        }
        self.collection.upsert(
            ids=[photo_id],
            documents=[text_content],
            metadatas=[sanitized_meta]
        )

    def query_similar(
        self,
        query_text: str,
        n_results: int = 5,
        allowed_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        비정형 시맨틱 쿼리 검색:
        allowed_ids가 주어지면 해당 ID군 내에서만 검색 (하이브리드 필터링).
        allowed_ids가 비어있거나 None이면 전체 대상 검색 (소프트 Fallback).
        """
        count = self.collection.count()
        if count == 0:
            return []

        # Chroma query filter
        where_filter = None
        # ChromaDB allows filtering by id using where_document or passing allowed IDs or filtering afterwards
        # Note: Chroma supports ids filter in get(), but in query(), if allowed_ids is given:
        effective_n = min(n_results, count)

        # Chroma's query doesn't directly support `ids=[...]` parameter in older versions,
        # but we can filter by metadata or query with larger n_results and filter by allowed_ids,
        # or use metadata where clause. Let's do a robust implementation:
        if allowed_ids is not None and len(allowed_ids) > 0:
            # Query more results to ensure we catch allowed_ids, or query up to count
            target_fetch = min(max(n_results * 5, 20), count)
            results = self.collection.query(
                query_texts=[query_text],
                n_results=target_fetch
            )
            filtered_matches = []
            allowed_set = set(allowed_ids)
            if results and results.get("ids") and len(results["ids"]) > 0:
                for idx, pid in enumerate(results["ids"][0]):
                    if pid in allowed_set:
                        dist = results["distances"][0][idx] if "distances" in results and results["distances"] else 0.0
                        doc = results["documents"][0][idx] if "documents" in results and results["documents"] else ""
                        filtered_matches.append({
                            "id": pid,
                            "distance": dist,
                            "similarity": 1.0 - dist,  # cosine distance to similarity
                            "document": doc
                        })
                        if len(filtered_matches) >= n_results:
                            break
            # If filtered_matches has items, return them!
            if filtered_matches:
                return filtered_matches

        # Fallback / unfiltered search
        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(n_results, count)
        )
        matches = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            for idx, pid in enumerate(results["ids"][0]):
                dist = results["distances"][0][idx] if "distances" in results and results["distances"] else 0.0
                doc = results["documents"][0][idx] if "documents" in results and results["documents"] else ""
                matches.append({
                    "id": pid,
                    "distance": dist,
                    "similarity": 1.0 - dist,
                    "document": doc
                })
        return matches

# 싱글톤 인스턴스 팩토리
_vector_store_instance = None

def get_vector_store(persist_dir: str = DEFAULT_CHROMA_DIR) -> VectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore(persist_dir)
    return _vector_store_instance

