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
        scores, idxs = self.index.search(q, k)
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
        return {
            "ids": out_ids,
            "scores": out_scores,
            "documents": out_docs,
            "metadatas": out_metas,
        }


def prepare_simple_docs(
    all_chunks: List[Any], max_chars: int = 3000
) -> List[Dict[str, Any]]:
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
        docs.append({"text": content, "meta": _safe_meta(meta)})
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
            f"[Step3] [FAISS] Added {added}/{total} (emb {t1 - t0:.2f}s, total {time.time() - start:.2f}s)"
        )
    content_indexer.persist()

    elapsed = time.time() - start
    print(
        f"[Step3] [FAISS] Content index completed. count={content_indexer.count()} in {elapsed:.2f}s"
    )

    return {
        "total": total,
        "indexed": added,
        "elapsed_sec": round(elapsed, 2),
        "count": content_indexer.count(),
    }


# ---------- Key index (rule id + alert name) ----------


def build_rule_key_strings(rule_keys: List[Dict[str, Any]]) -> List[str]:
    out = []
    for r in rule_keys:
        rid = (r.get("rule_id") or "").strip()
        aname = (r.get("alert_name") or "").strip()
        fname = r.get("source") or ""
        rowi = r.get("row_index")
        keyparts = []
        if rid:
            keyparts.append(f"rule:{rid}")
            keyparts.append(f"rule#{rid}")
            keyparts.append(f"rule {rid}")
        if aname:
            keyparts.append(f"alert:{aname}")
            keyparts.append(aname)
        # minimal unique join
        out.append(" | ".join(keyparts) if keyparts else f"{fname}:{rowi}")
    return out


def index_rule_keys_with_ollama_faiss(
    rule_keys_path: str = "artifacts/rule_keys.json",
    persist_dir: str = "vector_store_faiss",
    index_name: str = "soc_rag_keys",
    model: str = "nomic-embed-text",
    batch_size: int = 32,
) -> Dict[str, Any]:
    if not os.path.exists(rule_keys_path):
        return {"total": 0, "indexed": 0, "elapsed_sec": 0.0, "count": 0}

    with open(rule_keys_path, "r", encoding="utf-8") as f:
        key_rows = json.load(f)

    embedder = OllamaEmbedder(model=model)
    embedder.ensure_model()

    texts = build_rule_key_strings(key_rows)
    key_indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)
    start = time.time()

    total = len(texts)
    added = 0
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
        f"[Step3b] [FAISS] Key index completed. count={key_indexer.count()} in {elapsed:.2f}s"
    )
    return {
        "total": total,
        "indexed": added,
        "elapsed_sec": round(elapsed, 2),
        "count": key_indexer.count(),
    }
