import os
import uuid
import time
import json
import hashlib
from typing import List, Dict, Any
import numpy as np
import ollama

try:
    import faiss  # pip install faiss-cpu
except ImportError as e:
    raise ImportError("FAISS not installed. Run: pip install faiss-cpu") from e


def _safe_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced metadata safety with rule information preservation."""
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
    """Enhanced document ID generation with rule awareness."""
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))

    # Include rule information in hash for better uniqueness
    rule_info = {}
    if metadata:
        rule_info = {
            "rule_id": metadata.get("rule_id", ""),
            "alert_name": metadata.get("alert_name", ""),
            "doctype": metadata.get("doctype", ""),
        }

    h.update(
        json.dumps(_safe_meta(rule_info), sort_keys=True, default=str).encode(
            "utf-8", errors="ignore"
        )
    )
    return h.hexdigest() + "-" + uuid.uuid4().hex[:8]


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def ensure_model(self) -> None:
        """Ensure the embedding model is available."""
        models = ollama.list().get("models", [])
        names = [m.get("name", "") for m in models]
        if self.model not in names:
            print(f"⚠️ {self.model} not found. Pulling...")
            ollama.pull(self.model)
            print(f"✅ {self.model} pulled")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
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
    """L2 normalize embeddings."""
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

    def exists(self) -> bool:
        return os.path.exists(self.index_path) and os.path.exists(self.meta_path)

    def _init_index(self, dim: int):
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
        """Enhanced add method with rule-aware metadata."""
        if embeddings is None or embeddings.size == 0:
            return

        if embeddings.ndim != 2:
            raise ValueError(
                f"Expected 2D embeddings [N, D], got shape {embeddings.shape}"
            )

        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32, copy=False)

        dim = embeddings.shape[1]
        if self.index is None:
            self._init_index(dim)
        elif self.index.d != dim:
            raise ValueError(
                f"Embedding dim mismatch: index dim {self.index.d} vs batch dim {dim}"
            )

        # Enhanced metadata processing
        enhanced_metadatas = []
        for meta, doc in zip(metadatas, documents):
            enhanced_meta = _safe_meta(meta)

            # Add document statistics
            enhanced_meta["doc_length"] = len(doc)
            enhanced_meta["has_rule_content"] = bool(
                "rule" in doc.lower() and any(c.isdigit() for c in doc)
            )

            enhanced_metadatas.append(enhanced_meta)

        normed = _l2_normalize(embeddings)
        self.index.add(normed)
        self.ids.extend(ids)
        self.metadatas.extend(enhanced_metadatas)
        self.documents.extend(documents)

    def count(self) -> int:
        return 0 if self.index is None else self.index.ntotal

    def persist(self):
        """Persist index with enhanced metadata."""
        if self.index is None:
            return

        faiss.write_index(self.index, self.index_path)
        sidecar = {
            "ids": self.ids,
            "metadatas": self.metadatas,
            "documents": self.documents,
            "dim": self.index.d,
            "stats": {
                "total_docs": len(self.documents),
                "rule_docs": sum(
                    1 for m in self.metadatas if m.get("has_rule_content")
                ),
                "tracker_docs": sum(
                    1 for m in self.metadatas if m.get("doctype") == "tracker_row"
                ),
                "rulebook_docs": sum(
                    1 for m in self.metadatas if m.get("doctype") == "rulebook"
                ),
            },
        }

        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(sidecar, f, ensure_ascii=False)

    def _load(self):
        """Load index with stats reporting."""
        self.index = faiss.read_index(self.index_path)
        with open(self.meta_path, "r", encoding="utf-8") as f:
            sidecar = json.load(f)

        self.ids = sidecar.get("ids", [])
        self.metadatas = sidecar.get("metadatas", [])
        self.documents = sidecar.get("documents", [])

        # Print stats if available
        stats = sidecar.get("stats", {})
        if stats:
            print(
                f"📊 Loaded index: {stats.get('total_docs', 0)} docs "
                f"({stats.get('rule_docs', 0)} rule-related, "
                f"{stats.get('tracker_docs', 0)} tracker, "
                f"{stats.get('rulebook_docs', 0)} rulebook)"
            )

    def query(self, query_emb: np.ndarray, k: int = 5) -> Dict[str, Any]:
        """Enhanced query with rule-aware scoring."""
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

        q = _l2_normalize(query_emb.astype(np.float32, copy=False))
        scores, idxs = self.index.search(
            q, min(k * 2, self.index.ntotal)
        )  # Get more for filtering

        idxs_row = np.asarray(idxs).reshape(-1).tolist()
        scores_row = np.asarray(scores).reshape(-1).tolist()

        out_ids, out_docs, out_metas, out_scores = [], [], [], []

        for i, s in zip(idxs_row, scores_row):
            if i == -1:
                continue

            out_ids.append(self.ids[i])
            out_docs.append(self.documents[i])
            out_metas.append(self.metadatas[i])
            out_scores.append(float(s))

        # Return top-k results
        return {
            "ids": out_ids[:k],
            "scores": out_scores[:k],
            "documents": out_docs[:k],
            "metadatas": out_metas[:k],
        }


def prepare_simple_docs(
    all_chunks: List[Any], max_chars: int = 10000
) -> List[Dict[str, Any]]:
    """Enhanced document preparation with rule awareness."""
    docs = []
    for d in all_chunks:
        try:
            content = getattr(d, "page_content", None) or (
                d.get("page_content", "") if isinstance(d, dict) else ""
            )
        except Exception:
            content = ""

        try:
            meta = (
                getattr(d, "metadata", None)
                or (d.get("metadata", {}) if isinstance(d, dict) else {})
                or {}
            )
        except Exception:
            meta = {}

        content = str(content)[:max_chars]

        # Enhanced metadata with rule detection
        safe_meta = _safe_meta(meta)
        if not safe_meta.get("has_rule_content"):
            safe_meta["has_rule_content"] = bool(
                "rule" in content.lower() and any(c.isdigit() for c in content)
            )

        docs.append({"text": content, "meta": safe_meta})

    return docs


def faiss_index_exists(
    persist_dir: str = "vector_store_faiss", index_name: str = "soc_rag"
) -> bool:
    """Check if FAISS index exists."""
    idx = FaissIndexer(persist_dir=persist_dir, index_name=index_name)
    return idx.exists()


def index_chunks_with_ollama_faiss(
    all_chunks: List[Any],
    persist_dir: str = "vector_store_faiss",
    index_name: str = "faiss",
    model: str = "nomic-embed-text",
    batch_size: int = 16,
) -> Dict[str, Any]:
    """Enhanced indexing with rule-aware processing."""
    os.environ.setdefault("OLLAMA_TIMEOUT", "120")
    start = time.time()

    print(f"[Step3] [FAISS] Initializing enhanced embedder/model={model}")
    embedder = OllamaEmbedder(model=model)
    embedder.ensure_model()

    simple_docs = prepare_simple_docs(all_chunks)

    # Enhanced statistics
    rule_docs = sum(1 for d in simple_docs if d["meta"].get("has_rule_content"))
    tracker_docs = sum(
        1 for d in simple_docs if d["meta"].get("doctype") == "tracker_row"
    )
    rulebook_docs = sum(
        1 for d in simple_docs if d["meta"].get("doctype") == "rulebook"
    )

    print(
        f"📊 Processing {len(simple_docs)} docs: {rule_docs} rule-related, "
        f"{tracker_docs} tracker, {rulebook_docs} rulebook"
    )

    # Primary content index
    content_indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)

    total = len(simple_docs)
    added = 0

    for i in range(0, total, batch_size):
        batch = simple_docs[i : i + batch_size]
        texts = [b["text"] for b in batch]

        t0 = time.time()
        embs = embedder.embed_texts(texts)
        t1 = time.time()

        ids = [_doc_id(texts[j], batch[j]["meta"]) for j in range(len(batch))]
        metas = [{**batch[j]["meta"], "len": len(texts[j])} for j in range(len(batch))]
        docs = [texts[j] for j in range(len(batch))]

        content_indexer.add(embs, ids, metas, docs)
        added += len(batch)

        print(
            f"[Step3] [FAISS] Added {added}/{total} "
            f"(emb {t1 - t0:.2f}s, total {time.time() - start:.2f}s)"
        )

    content_indexer.persist()
    elapsed = time.time() - start

    print(
        f"[Step3] [FAISS] Enhanced index completed. "
        f"count={content_indexer.count()} in {elapsed:.2f}s"
    )

    return {
        "total": total,
        "indexed": added,
        "elapsed_sec": round(elapsed, 2),
        "count": content_indexer.count(),
        "stats": {
            "rule_docs": rule_docs,
            "tracker_docs": tracker_docs,
            "rulebook_docs": rulebook_docs,
        },
    }


# ---------- Enhanced Key index (rule id + alert name) ----------


def build_rule_key_strings(rule_keys: List[Dict[str, Any]]) -> List[str]:
    """Enhanced rule key string building with better patterns."""
    out = []
    for r in rule_keys:
        rid = (r.get("rule_id") or "").strip()
        aname = (r.get("alert_name") or "").strip()
        fname = r.get("source") or ""
        rowi = r.get("row_index")

        keyparts = []
        if rid:
            # Enhanced rule patterns
            keyparts.extend(
                [
                    f"rule:{rid}",
                    f"rule#{rid}",
                    f"rule {rid}",
                    f"rule-{rid}",
                    f"rule {int(rid)}",
                    f"rule#{int(rid)}",
                ]
            )

        if aname:
            keyparts.extend([f"alert:{aname}", aname, f"rule:{aname}", f"{aname} rule"])

        # Combine rule and alert name
        if rid and aname:
            keyparts.extend(
                [f"rule {rid} {aname}", f"rule#{rid} {aname}", f"{aname} rule {rid}"]
            )

        # Create comprehensive key string
        key_string = " | ".join(keyparts) if keyparts else f"{fname}:{rowi}"
        out.append(key_string)

    return out


def index_rule_keys_with_ollama_faiss(
    rule_keys_path: str = "artifacts/rule_keys.json",
    persist_dir: str = "vector_store_faiss",
    index_name: str = "soc_rag_keys",
    model: str = "nomic-embed-text",
    batch_size: int = 32,
) -> Dict[str, Any]:
    """Enhanced rule key indexing."""
    if not os.path.exists(rule_keys_path):
        return {"total": 0, "indexed": 0, "elapsed_sec": 0.0, "count": 0}

    with open(rule_keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both old and new format
    if isinstance(data, dict) and "rule_keys" in data:
        key_rows = data["rule_keys"]
    else:
        key_rows = data

    embedder = OllamaEmbedder(model=model)
    embedder.ensure_model()

    texts = build_rule_key_strings(key_rows)
    key_indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)

    start = time.time()
    total = len(texts)
    added = 0

    print(f"[Step3b] [FAISS] Building enhanced rule key index for {total} rules")

    for i in range(0, total, batch_size):
        batch_texts = texts[i : i + batch_size]
        embs = embedder.embed_texts(batch_texts)

        metas = []
        ids = []
        docs = []

        for j, t in enumerate(batch_texts):
            rec = key_rows[i + j]
            meta = _safe_meta(
                {
                    "doctype": "rule_key",
                    "rule_id": rec.get("rule_id"),
                    "alert_name": rec.get("alert_name"),
                    "source": rec.get("source"),
                    "row_index": rec.get("row_index"),
                    "has_rule_content": True,
                    "description": rec.get("description", ""),
                }
            )

            metas.append(meta)
            ids.append(_doc_id(t, meta))
            docs.append(t)

        key_indexer.add(embs, ids, metas, docs)
        added += len(batch_texts)
        print(f"[Step3b] [FAISS] Keys added {added}/{total}")

    key_indexer.persist()
    elapsed = time.time() - start

    print(
        f"[Step3b] [FAISS] Enhanced key index completed. "
        f"count={key_indexer.count()} in {elapsed:.2f}s"
    )

    return {
        "total": total,
        "indexed": added,
        "elapsed_sec": round(elapsed, 2),
        "count": key_indexer.count(),
    }
