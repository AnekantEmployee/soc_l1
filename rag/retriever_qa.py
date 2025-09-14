# rag/retriever_qa.py

import os
import re
import json
from typing import List, Dict, Any, Tuple
import ollama
import numpy as np

from .embedding_indexer import OllamaEmbedder, FaissIndexer

# ---------------------------
# Query understanding helpers
# ---------------------------

RULE_PAT = re.compile(r"(?:\brule\b\s*#?\s*)(\d{1,4})\b", flags=re.I)
JUST_NUMBER_PAT = re.compile(r"^\s*(\d{1,4})\s*$")


def parse_rule_id(q: str) -> str:
    """Extract a 3-digit rule id if present (e.g., '002'). Returns '' if none."""
    if not q:
        return ""
    m = RULE_PAT.search(q)
    if m:
        return m.group(1).zfill(3)
    m2 = JUST_NUMBER_PAT.match(q)
    if m2:
        return m2.group(1).zfill(3)
    return ""


def classify_query(q: str) -> Dict[str, bool]:
    """Classify query intent so we can prioritize tracker or rulebook."""
    s = (q or "").lower()
    is_rule = (
        bool(parse_rule_id(q))
        or ("rule" in s)
        or ("remediation" in s)
        or ("procedure" in s)
        or ("steps" in s)
        or ("assigned" in s and "privileged" in s)
        or ("privileged role" in s)
    )

    tracker_signals = any(
        t in s
        for t in [
            "count",
            "counts",
            "total",
            "priority",
            "priorities",
            "status",
            "statuses",
            "opened",
            "closed",
            "resolved",
            "sla",
            "owner",
            "assignee",
            "reported time",
            "response time",
            "resolved time",
            "incident",
            "ticket",
            "daily",
            "weekly",
            "summary",
            "dashboard",
            "category",
            "categories",
        ]
    )

    return {"about_rule": is_rule, "about_tracker": tracker_signals or not is_rule}


def expand_tracker_queries(q: str) -> List[str]:
    """Expansion specialized for tracker facts."""
    base = (q or "").strip()
    variants = [
        base,
        f"{base} tracker",
        f"{base} incident row",
        f"{base} status priority owner",
        f"{base} reported time response time resolved time",
    ]
    return [v for v in dict.fromkeys(v.strip() for v in variants if v.strip())]


def expand_rulebook_queries(q: str) -> List[str]:
    """Expansion specialized for rulebooks."""
    base = (q or "").strip()
    rid = parse_rule_id(q)
    variants = [
        base,
        f"{base} rulebook",
        f"{base} procedure steps remediation escalation",
    ]

    if rid:
        n = int(rid)
        variants += [
            f"Rule {rid}",
            f"Rule #{rid}",
            f"Rule#{rid}",
            f"Rule {n}",
            f"Rule {rid} procedure remediation",
            f"Rule {rid} triage investigation steps",
        ]

    # Handle alert name queries
    if "privileged role" in base.lower() or "assigned" in base.lower():
        variants += [
            "User Assigned Privileged Role",
            "New User Assigned to Privileged Role",
            "privileged role assignment",
            "Rule 014",
            "Rule#014",
        ]

    return [v for v in dict.fromkeys(v.strip() for v in variants if v.strip())]


def _retrieve_any(
    queries: List[str],
    indexer: FaissIndexer,
    embedder: OllamaEmbedder,
    k_per_query: int,
) -> Dict[str, Any]:
    ids: List[str] = []
    docs: List[str] = []
    metas: List[Dict[str, Any]] = []
    scores: List[float] = []
    seen = set()

    for q in queries:
        qemb = embedder.embed_texts([q])
        res = indexer.query(qemb, k=k_per_query)
        for i, s, d, m in zip(
            res["ids"], res["scores"], res["documents"], res["metadatas"]
        ):
            if i in seen:
                continue
            seen.add(i)
            ids.append(i)
            scores.append(float(s))
            docs.append(d)
            metas.append(m)

    # Sort by score desc
    order = sorted(range(len(ids)), key=lambda j: scores[j], reverse=True)
    return {
        "ids": [ids[j] for j in order],
        "scores": [scores[j] for j in order],
        "documents": [docs[j] for j in order],
        "metadatas": [metas[j] for j in order],
    }


def _is_tracker_meta(meta: Dict[str, Any]) -> bool:
    dt = str((meta or {}).get("doctype") or "").lower()
    src = str((meta or {}).get("source") or "").lower()
    return dt == "tracker_row" or src == "tracker_sheet" or "tracker" in src


def _is_rulebook_meta(meta: Dict[str, Any]) -> bool:
    dt = str((meta or {}).get("doctype") or "").lower()
    src = str((meta or {}).get("source") or "").lower()
    ft = str((meta or {}).get("filetype") or "").lower()
    return dt == "rulebook" or ft in {"csv", "xlsx"} or "rule" in src.lower()


def _filter_empty_tracker_rows(hits: List[Tuple]) -> List[Tuple]:
    """Filter out tracker rows that are mostly null/empty."""
    filtered = []
    for i, s, d, m in hits:
        try:
            if _is_tracker_meta(m):
                # Parse JSON and check if mostly empty
                data = json.loads(d)
                # Count non-null values
                non_null_count = sum(
                    1 for v in data.values() if v is not None and str(v).strip() != ""
                )
                # Keep only if at least 5 fields have data
                if non_null_count >= 5:
                    filtered.append((i, s, d, m))
            else:
                filtered.append((i, s, d, m))
        except Exception:
            # If can't parse, keep it
            filtered.append((i, s, d, m))
    return filtered


def retrieve_dual_source(
    query: str,
    persist_dir: str = "vector_store_faiss",
    index_name: str = "soc_rag",
    embed_model: str = "nomic-embed-text",
    k_tracker: int = 2,  # Reduced to 2 as requested
    k_rulebook: int = 5,  # Keep 5 for rulebooks
) -> Dict[str, Any]:
    """Perform targeted retrievals and return source-separated results."""
    embedder = OllamaEmbedder(model=embed_model)
    indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)

    cls = classify_query(query)
    tracker_qs = expand_tracker_queries(query) if cls["about_tracker"] else [query]
    rule_qs = expand_rulebook_queries(query) if cls["about_rule"] else [query]

    raw = _retrieve_any(
        tracker_qs + rule_qs, indexer, embedder, k_per_query=max(k_tracker, k_rulebook)
    )

    # Partition by source
    tracker_hits = []
    rule_hits = []

    for i, s, d, m in zip(
        raw["ids"], raw["scores"], raw["documents"], raw["metadatas"]
    ):
        if _is_tracker_meta(m):
            tracker_hits.append((i, s, d, m))
        elif _is_rulebook_meta(m):
            rule_hits.append((i, s, d, m))
        else:
            (tracker_hits if cls["about_tracker"] else rule_hits).append((i, s, d, m))

    # Filter empty tracker rows
    tracker_hits = _filter_empty_tracker_rows(tracker_hits)

    # Keep top-k for each
    tracker_hits = tracker_hits[:k_tracker]
    rule_hits = rule_hits[:k_rulebook]

    # Normalize scores within each group
    def _norm(hits):
        if not hits:
            return []
        max_s = max(s for _, s, _, _ in hits) or 1.0
        return [(i, s / max_s, d, m) for (i, s, d, m) in hits]

    return {
        "tracker": _norm(tracker_hits),
        "rulebook": _norm(rule_hits),
        "class": cls,
    }


def _extract_rule_block_from_rulebook_text(text: str, rule_id_norm: str) -> str:
    """Extract specific rule block from rulebook text."""
    if not text or not rule_id_norm:
        return text  # Return full text if no rule ID

    t = text.replace("\r\n", "\n")
    rid_num = rule_id_norm.lstrip("0")

    # Multiple patterns to find the rule
    pat_candidates = [
        rf"(?i)^.*Rule#?0*{re.escape(rid_num)}[^0-9].*$",
        rf"(?i)^.*Rule[ #:-]*0*{re.escape(rid_num)}[^0-9].*$",
        rf'(?i)".*Rule#?0*{re.escape(rid_num)}[^0-9][^"]*"',
        rf"(?i)Rule#?0*{re.escape(rid_num)}[^0-9].*",
    ]

    start = -1
    for p in pat_candidates:
        m = re.search(p, t, flags=re.MULTILINE)
        if m:
            start = m.start()
            break

    if start < 0:
        return text  # Return full text if specific rule not found

    # Find the end (next rule or end of text)
    next_rule = re.search(
        r"(?i)^.*Rule[ #]*\d{1,4}.*$", t[start + 50 :], flags=re.MULTILINE
    )
    end = start + 50 + next_rule.start() if next_rule else len(t)

    block = t[start:end].strip()

    # If block is too short, expand backwards to include row header
    if len(block) < 200:
        pre = t.rfind("\nRow", 0, start)
        if pre != -1:
            block = t[pre:end].strip()

    return block if len(block) > 10 else text


def build_context_block_dual(results: Dict[str, Any], query: str) -> str:
    """Build a clean, source-separated context."""
    rid = parse_rule_id(query)
    lines: List[str] = []

    # Tracker section
    tr_hits = results.get("tracker") or []
    if tr_hits:
        lines.append("=== TRACKER ===")
        for i, s, d, m in tr_hits:
            src = (m or {}).get("source") or "tracker"
            rowindex = (m or {}).get("row_index")
            try:
                data = json.loads(d)
                pretty = json.dumps(data, ensure_ascii=False, indent=2)
            except Exception:
                pretty = d.strip()[:4000]
            lines.append(f"[score={s:.3f}] [src={src}] [row={rowindex}]")
            lines.append(pretty)

    # Rulebook section
    rb_hits = results.get("rulebook") or []
    if rb_hits:
        lines.append("=== RULEBOOK ===")
        for i, s, d, m in rb_hits:
            src = (m or {}).get("source") or (m or {}).get("filetype") or "rulebook"

            block = d
            if rid and len(d) > 100:  # Only extract if we have substantial content
                extracted = _extract_rule_block_from_rulebook_text(d, rid)
                if len(extracted) > 10:  # Only use extracted if meaningful
                    block = extracted

            lines.append(f"[score={s:.3f}] [src={src}]")
            lines.append(block.strip())

    return "\n".join(lines) if lines else "No matching context."


# ---------------------------
# Prompts and LLM call
# ---------------------------

SYSTEM_PROMPT_DUAL = """You are a SOC RAG assistant.

Use ONLY the provided CONTEXT to answer.

Rules:
- Use TRACKER section for operational facts: counts, statuses, times, owners, incidents.
- Use RULEBOOK section for procedures, criteria, triage steps, and remediation.
- If a specific Rule ID is implied, rely on RULEBOOK only for procedures/remediation.
- Never mix invented content; if something is not present, state 'Not in context'.
- Output must be concise, structured, and directly useful.

Output format:

# Title

## Key points
- 3–7 bullets

## Tracker facts
- Bullet list of concrete facts (omit if none)

## Rulebook procedures
- Bullets or ordered steps strictly from the rulebook for the relevant rule(s).

## Remediation
- Actionable remediation steps from the rulebook; if none, write 'Not in context'.
"""


def call_llm_dual_markdown(
    query: str, context_block: str, model: str = "qwen2.5:0.5b"
) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_DUAL},
        {"role": "user", "content": f"QUESTION:\n{query}\n\nCONTEXT:\n{context_block}"},
    ]

    try:
        resp = ollama.chat(
            model=model, messages=messages, options={"temperature": 0.15}
        )
        return ((resp.get("message", {}) or {}).get("content", "") or "").strip()
    except Exception as e:
        return f"Error generating response: {e}"


def answer_query_with_rag(
    query: str,
    k: int = 5,
    persist_dir: str = "vector_store_faiss",
    index_name: str = "soc_rag",
    embed_model: str = "nomic-embed-text",
    gen_model: str = "qwen2.5:0.5b",
) -> Dict[str, Any]:

    results = retrieve_dual_source(
        query=query,
        persist_dir=persist_dir,
        index_name=index_name,
        embed_model=embed_model,
        k_tracker=2,  # Limit to 2 tracker results
        k_rulebook=5,  # Allow 5 rulebook results
    )

    context_block = build_context_block_dual(results, query)
    answer_md = call_llm_dual_markdown(query, context_block, model=gen_model)

    # Save context to file
    safe_q = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:60]
    os.makedirs("artifacts/query_contexts", exist_ok=True)
    context_path = f"artifacts/query_contexts/{safe_q}.txt"

    try:
        with open(context_path, "w", encoding="utf-8") as f:
            f.write(f"Query: {query}\n")
            f.write("=" * 50 + "\n")
            f.write(context_block)
    except Exception:
        context_path = "Failed to save"

    return {
        "query": query,
        "answer": answer_md,
        "context_preview": context_block,
        "class": results.get("class"),
        "tracker_hits": len(results.get("tracker") or []),
        "rulebook_hits": len(results.get("rulebook") or []),
        "context_saved_to": context_path,
    }


def write_rule_markdown(
    query: str,
    out_dir: str = ".",
    filename: str = None,
    persist_dir: str = "vector_store_faiss",
    index_name: str = "soc_rag",
    embed_model: str = "nomic-embed-text",
    gen_model: str = "qwen2.5:0.5b",
) -> str:
    """Write rule-focused Markdown file."""
    rid = parse_rule_id(query)
    res = answer_query_with_rag(
        query=query,
        k=5,
        persist_dir=persist_dir,
        index_name=index_name,
        embed_model=embed_model,
        gen_model=gen_model,
    )

    md = res["answer"] or "# No content\n"
    if not filename:
        filename = f"rule_{rid}.md" if rid else "answer.md"

    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path
