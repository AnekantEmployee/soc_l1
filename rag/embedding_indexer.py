# embeddings_indexer_faiss.py
import os
import uuid
import time
import json
import math
import hashlib
from typing import List, Dict, Any, Tuple

import numpy as np
import ollama

try:
    import faiss  # pip install faiss-cpu
except ImportError as e:
    raise ImportError("FAISS not installed. Run: pip install faiss-cpu") from e


class SimpleDoc:
    def __init__(self, page_content: str, metadata: Dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata or {}


def _safe_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    safe = {}
    for k, v in (meta or {}).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            safe[k] = v
        else:
            try:
                safe[k] = json.dumps(v, default=str)
            except Exception:
                safe[k] = str(v)
    return safe


def _doc_id(text: str, metadata: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    h.update(
        json.dumps(_safe_meta(metadata), sort_keys=True, default=str).encode(
            "utf-8", errors="ignore"
        )
    )
    return h.hexdigest() + "-" + uuid.uuid4().hex[:8]


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def ensure_model(self) -> None:
        models = ollama.list().get("models", [])
        names = [m.get("name", "") for m in models]
        if self.model not in names:
            print(f"⚠️ {self.model} not found. Pulling...")
            ollama.pull(self.model)
            print(f"✅ {self.model} pulled")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        resp = ollama.embed(model=self.model, input=texts)
        embs = resp.get("embeddings", [])
        arr = np.array(embs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2:
            raise ValueError(f"Unexpected embedding shape from Ollama: {arr.shape}")
        return arr


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    return x / norms


class FaissIndexer:
    def __init__(
        self, persist_dir: str = "vector_store_faiss", index_name: str = "faiss"
    ):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self.index_path = os.path.join(self.persist_dir, f"{index_name}.index")
        self.meta_path = os.path.join(self.persist_dir, f"{index_name}.meta.json")
        self.index = None
        self.ids: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.documents: List[str] = []

        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            self._load()
        # else: will initialize after first batch when dim is known

    def exists(self) -> bool:
        return os.path.exists(self.index_path) and os.path.exists(self.meta_path)

    def _init_index(self, dim: int):
        # Cosine similarity via normalized vectors + inner product
        if dim <= 0:
            raise ValueError(f"Invalid embedding dimension: {dim}")
        self.index = faiss.IndexFlatIP(dim)

    def add(
        self,
        embeddings: np.ndarray,
        ids: List[str],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ):
        if embeddings is None or embeddings.size == 0:
            return
        if embeddings.ndim != 2:
            raise ValueError(
                f"Expected 2D embeddings [N, D], got shape {embeddings.shape}"
            )
        # Ensure float32
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32, copy=False)
        dim = embeddings.shape[1]
        if self.index is None:
            self._init_index(dim)
        elif self.index.d != dim:
            raise ValueError(
                f"Embedding dim mismatch: index dim {self.index.d} vs batch dim {dim}"
            )

        normed = _l2_normalize(embeddings)
        self.index.add(normed)
        self.ids.extend(ids)
        self.metadatas.extend(metadatas)
        self.documents.extend(documents)

    def count(self) -> int:
        return 0 if self.index is None else self.index.ntotal

    def persist(self):
        if self.index is None:
            return
        faiss.write_index(self.index, self.index_path)
        sidecar = {
            "ids": self.ids,
            "metadatas": self.metadatas,
            "documents": self.documents,
            "dim": self.index.d,
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(sidecar, f, ensure_ascii=False)

    def _load(self):
        self.index = faiss.read_index(self.index_path)
        with open(self.meta_path, "r", encoding="utf-8") as f:
            sidecar = json.load(f)
        self.ids = sidecar.get("ids", [])
        self.metadatas = sidecar.get("metadatas", [])
        self.documents = sidecar.get("documents", [])

    def query(self, query_emb: np.ndarray, k: int = 5) -> Dict[str, Any]:
        # Validate and shape the query embedding
        if query_emb is None:
            return {"ids": [], "scores": [], "documents": [], "metadatas": []}
        if isinstance(query_emb, list):
            query_emb = np.array(query_emb, dtype=np.float32)
        if getattr(query_emb, "size", 0) == 0:
            return {"ids": [], "scores": [], "documents": [], "metadatas": []}
        if query_emb.ndim == 1:
            query_emb = query_emb.reshape(1, -1)

        if self.index is None or self.index.ntotal == 0:
            return {"ids": [], "scores": [], "documents": [], "metadatas": []}

        # Normalize and search
        q = _l2_normalize(query_emb.astype(np.float32, copy=False))
        scores, idxs = self.index.search(q, k)

        # Ensure ndarray
        if not isinstance(scores, np.ndarray):
            scores = np.array(scores)
        if not isinstance(idxs, np.ndarray):
            idxs = np.array(idxs)

        # Take first row only (single-query)
        idxs_row = idxs
        scores_row = scores

        # Convert to flat Python lists of scalars
        idxs_list = [int(i) for i in np.asarray(idxs_row).reshape(-1).tolist()]
        scores_list = [float(s) for s in np.asarray(scores_row).reshape(-1).tolist()]

        out_ids, out_docs, out_metas, out_scores = [], [], [], []
        for i, s in zip(idxs_list, scores_list):
            if i == -1:
                continue
            out_ids.append(self.ids[i])
            out_docs.append(self.documents[i])
            out_metas.append(self.metadatas[i])
            out_scores.append(s)

        return {
            "ids": out_ids,
            "scores": out_scores,
            "documents": out_docs,
            "metadatas": out_metas,
        }


def prepare_simple_docs(
    all_chunks: List[Any], max_chars: int = 3000
) -> List[SimpleDoc]:
    docs = []
    for d in all_chunks:
        content = getattr(d, "page_content", None) or (
            d.get("page_content", "") if isinstance(d, dict) else ""
        )
        meta = (
            getattr(d, "metadata", None)
            or (d.get("metadata", {}) if isinstance(d, dict) else {})
            or {}
        )
        content = str(content)[:max_chars]
        docs.append(SimpleDoc(content, _safe_meta(meta)))
    return docs


def faiss_index_exists(
    persist_dir: str = "vector_store_faiss", index_name: str = "soc_rag"
) -> bool:
    idx = FaissIndexer(persist_dir=persist_dir, index_name=index_name)
    return idx.exists()


def index_chunks_with_ollama_faiss(
    all_chunks: List[Any],
    persist_dir: str = "vector_store_faiss",
    index_name: str = "faiss",
    model: str = "nomic-embed-text",
    batch_size: int = 16,
) -> Dict[str, Any]:
    os.environ.setdefault("OLLAMA_TIMEOUT", "120")
    start = time.time()
    print(f"[Step3] [FAISS] Initializing embedder/model={model}")
    embedder = OllamaEmbedder(model=model)
    embedder.ensure_model()

    simple_docs = prepare_simple_docs(all_chunks)
    indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)

    total = len(simple_docs)
    added = 0
    for i in range(0, total, batch_size):
        batch = simple_docs[i : i + batch_size]
        texts = [b.page_content for b in batch]

        t0 = time.time()
        embs = embedder.embed_texts(texts)
        t1 = time.time()
        ids = [_doc_id(texts[j], batch[j].metadata) for j in range(len(batch))]
        metas = [{**batch[j].metadata, "len": len(texts[j])} for j in range(len(batch))]
        docs = [texts[j] for j in range(len(batch))]

        indexer.add(embs, ids, metas, docs)
        added += len(batch)
        print(
            f"[Step3] [FAISS] Added {added}/{total} (emb {t1 - t0:.2f}s, total {time.time() - start:.2f}s)"
        )

    indexer.persist()
    elapsed = time.time() - start
    print(f"[Step3] [FAISS] Completed. count={indexer.count()} in {elapsed:.2f}s")
    return {
        "total": total,
        "indexed": added,
        "elapsed_sec": round(elapsed, 2),
        "count": indexer.count(),
    }


def query_faiss(
    query_text: str,
    model: str = "nomic-embed-text",
    persist_dir: str = "vector_store_faiss",
    index_name: str = "faiss",
    k: int = 5,
) -> Dict[str, Any]:
    embedder = OllamaEmbedder(model=model)
    q_emb = embedder.embed_texts([query_text])
    indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)
    return indexer.query(q_emb, k=k)
