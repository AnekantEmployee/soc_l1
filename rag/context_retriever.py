# rag/context_retriever.py

import os
import re
import json
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from .embedding_indexer import OllamaEmbedder, FaissIndexer

# ---------------------------
# Dynamic Query understanding helpers
# ---------------------------

RULE_PAT = re.compile(r"(?:\brule\b\s*#?\s*)(\d{1,4})\b", flags=re.I)
EXACT_RULE_PAT = re.compile(r"^\s*rule\s*#?\s*(\d{1,4})\s*$", flags=re.I)
JUST_NUMBER_PAT = re.compile(r"^\s*(\d{1,4})\s*$")


class DynamicRuleMapper:
    """Dynamic rule mapper that learns from the actual data instead of hardcoding."""

    def __init__(self):
        self.rule_to_alert_map: Dict[str, List[str]] = {}
        self.alert_to_rule_map: Dict[str, str] = {}
        self.rule_patterns: Dict[str, List[str]] = {}
        self.loaded = False

    def load_from_artifacts(self, rule_keys_path: str = "artifacts/rule_keys.json"):
        """Load rule mappings from the actual processed data."""
        if not os.path.exists(rule_keys_path):
            return

        try:
            with open(rule_keys_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both old and new format
            if isinstance(data, dict) and "rule_keys" in data:
                rule_keys = data["rule_keys"]
                metadata_map = data.get("rule_metadata_map", {})
            else:
                rule_keys = data
                metadata_map = {}

            # Build dynamic mappings from actual data
            for item in rule_keys:
                rule_id = item.get("rule_id", "").strip()
                alert_name = item.get("alert_name", "").strip()

                if rule_id:
                    rule_id = rule_id.zfill(3)  # Normalize to 3 digits

                    if alert_name:
                        # Rule to alert mapping
                        if rule_id not in self.rule_to_alert_map:
                            self.rule_to_alert_map[rule_id] = []
                        if alert_name not in self.rule_to_alert_map[rule_id]:
                            self.rule_to_alert_map[rule_id].append(alert_name)

                        # Alert to rule mapping (use lowercase for matching)
                        alert_key = alert_name.lower().strip()
                        if alert_key not in self.alert_to_rule_map:
                            self.alert_to_rule_map[alert_key] = rule_id

                    # Build search patterns for this rule
                    patterns = [
                        f"rule {rule_id}",
                        f"rule#{rule_id}",
                        f"rule {int(rule_id)}",
                        f"rule#{int(rule_id)}",
                    ]

                    if alert_name:
                        patterns.extend(
                            [
                                alert_name.lower(),
                                f"{alert_name.lower()} rule",
                                f"rule {rule_id} {alert_name.lower()}",
                            ]
                        )

                    self.rule_patterns[rule_id] = patterns

            self.loaded = True
            print(
                f"🔧 Loaded dynamic mappings: {len(self.rule_to_alert_map)} rules, "
                f"{len(self.alert_to_rule_map)} alert patterns"
            )

        except Exception as e:
            print(f"⚠️ Could not load rule mappings: {e}")

    def find_rule_from_query(self, query: str) -> Optional[str]:
        """Find rule ID from query using dynamic mappings."""
        if not self.loaded:
            return None

        query_lower = query.lower().strip()

        # Direct alert name matching
        for alert_phrase, rule_id in self.alert_to_rule_map.items():
            if alert_phrase in query_lower:
                return rule_id

        # Partial alert name matching
        for alert_phrase, rule_id in self.alert_to_rule_map.items():
            alert_words = alert_phrase.split()
            if len(alert_words) > 1:
                # Check if most words match
                matches = sum(1 for word in alert_words if word in query_lower)
                if matches >= len(alert_words) * 0.6:  # 60% word match threshold
                    return rule_id

        return None

    def get_rule_patterns(self, rule_id: str) -> List[str]:
        """Get search patterns for a specific rule."""
        return self.rule_patterns.get(rule_id, [])

    def get_alert_names(self, rule_id: str) -> List[str]:
        """Get alert names for a specific rule."""
        return self.rule_to_alert_map.get(rule_id, [])


# Global dynamic mapper instance
_rule_mapper = DynamicRuleMapper()


def parse_rule_id(q: str) -> str:
    """Enhanced rule ID extraction with dynamic mapping fallback."""
    if not q:
        return ""

    # First try exact rule pattern (highest priority)
    m = EXACT_RULE_PAT.match(q)
    if m:
        return m.group(1).zfill(3)

    # Then try general rule pattern
    m = RULE_PAT.search(q)
    if m:
        return m.group(1).zfill(3)

    # Try just number pattern
    m2 = JUST_NUMBER_PAT.match(q)
    if m2:
        return m2.group(1).zfill(3)

    # Try dynamic alert name mapping (loads automatically if not loaded)
    if not _rule_mapper.loaded:
        _rule_mapper.load_from_artifacts()

    dynamic_rule = _rule_mapper.find_rule_from_query(q)
    if dynamic_rule:
        return dynamic_rule

    return ""


def classify_query(q: str) -> Dict[str, Any]:
    """Enhanced query classification with dynamic rule detection."""
    s = (q or "").lower()
    rule_id = parse_rule_id(q)

    # High confidence rule query
    is_exact_rule = bool(EXACT_RULE_PAT.match(q)) or bool(JUST_NUMBER_PAT.match(q))

    # General rule indicators (keep these as they're universal)
    basic_rule_indicators = ["rule", "remediation", "procedure", "steps"]
    is_basic_rule = any(indicator in s for indicator in basic_rule_indicators)

    # Dynamic rule detection
    is_dynamic_rule = bool(rule_id) and _rule_mapper.loaded

    is_rule = is_basic_rule or is_dynamic_rule

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
            "incident",
            "ticket",
            "daily",
            "weekly",
            "summary",
            "dashboard",
        ]
    )

    return {
        "about_rule": is_rule,
        "about_tracker": tracker_signals or not is_rule,
        "is_exact_rule": is_exact_rule,
        "rule_id": rule_id,
        "confidence": "high" if is_exact_rule else "medium" if rule_id else "low",
        "is_dynamic_match": is_dynamic_rule,
    }


def expand_tracker_queries(q: str) -> List[str]:
    """Tracker-focused query expansion."""
    base = (q or "").strip()
    variants = [
        base,
        f"{base} tracker",
        f"{base} incident",
        f"{base} status priority owner",
    ]
    return [v for v in dict.fromkeys(v.strip() for v in variants if v.strip())]


def expand_rulebook_queries(q: str, rule_id: str = "") -> List[str]:
    """Dynamic rulebook query expansion based on actual rule data."""
    base = (q or "").strip()
    variants = [base]

    if rule_id:
        # Standard rule patterns
        rule_num = int(rule_id)
        variants.extend(
            [
                f"Rule {rule_id}",
                f"Rule#{rule_id}",
                f"Rule {rule_num}",
                f"Rule#{rule_num}",
                f"Rule {rule_id} procedure",
                f"Rule {rule_id} remediation",
                f"Rule {rule_id} investigation steps",
            ]
        )

        # Add dynamic patterns if available
        if _rule_mapper.loaded:
            dynamic_patterns = _rule_mapper.get_rule_patterns(rule_id)
            variants.extend(dynamic_patterns)

            # Add alert names for this rule
            alert_names = _rule_mapper.get_alert_names(rule_id)
            for alert_name in alert_names:
                variants.extend(
                    [alert_name, f"{alert_name} procedure", f"{alert_name} remediation"]
                )

    variants.extend([f"{base} rulebook", f"{base} procedure steps remediation"])

    return [v for v in dict.fromkeys(v.strip() for v in variants if v.strip())]


def _retrieve_with_dynamic_matching(
    queries: List[str],
    indexer: FaissIndexer,
    embedder: OllamaEmbedder,
    k_per_query: int,
    rule_id: str = "",
) -> Dict[str, Any]:
    """Enhanced retrieval with dynamic rule matching."""
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

            # Dynamic score boosting based on rule matching
            boost_factor = 1.0
            if rule_id and d:
                d_lower = d.lower()

                # Exact rule pattern matching
                exact_patterns = [
                    f"rule#{rule_id}",
                    f"rule {rule_id}",
                    f"rule {int(rule_id)}",
                ]

                if any(pattern in d_lower for pattern in exact_patterns):
                    boost_factor = 2.5  # High boost for exact matches

                # Dynamic pattern matching
                elif _rule_mapper.loaded:
                    dynamic_patterns = _rule_mapper.get_rule_patterns(rule_id)
                    for pattern in dynamic_patterns:
                        if pattern.lower() in d_lower:
                            boost_factor = max(boost_factor, 2.0)
                            break

                # Partial rule matching
                elif "rule" in d_lower:
                    # Check if it's a different rule number
                    other_rule_match = re.search(r"rule\s*#?\s*(\d+)", d_lower)
                    if other_rule_match:
                        other_rule_num = other_rule_match.group(1).zfill(3)
                        if other_rule_num != rule_id:
                            boost_factor = 0.5  # Reduce score for different rules
                    else:
                        boost_factor = 1.2  # Small boost for rule-related content

            seen.add(i)
            ids.append(i)
            scores.append(float(s) * boost_factor)
            docs.append(d)
            metas.append(m)

    # Sort by boosted score desc
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


def _filter_by_rule_relevance(hits: List[Tuple], rule_id: str) -> List[Tuple]:
    """Dynamic rule relevance filtering."""
    if not rule_id:
        return hits

    exact_matches = []
    related_matches = []
    other_matches = []

    # Build dynamic rule patterns
    rule_patterns = [
        f"rule#{rule_id}",
        f"rule {rule_id}",
        f"rule {int(rule_id)}",
        f"rule#{int(rule_id)}",
    ]

    # Add dynamic patterns if available
    if _rule_mapper.loaded:
        dynamic_patterns = [p.lower() for p in _rule_mapper.get_rule_patterns(rule_id)]
        rule_patterns.extend(dynamic_patterns)

    for hit in hits:
        i, s, d, m = hit
        d_lower = d.lower()

        # Check for exact rule match
        if any(pattern in d_lower for pattern in rule_patterns):
            exact_matches.append(hit)
        # Check for different rule numbers
        elif re.search(r"rule\s*#?\s*\d+", d_lower):
            # This contains a different rule number
            other_rule_match = re.search(r"rule\s*#?\s*(\d+)", d_lower)
            if other_rule_match:
                other_rule_num = other_rule_match.group(1).zfill(3)
                if other_rule_num != rule_id:
                    # Different rule, lower priority
                    related_matches.append(hit)
                else:
                    exact_matches.append(hit)
            else:
                related_matches.append(hit)
        else:
            other_matches.append(hit)

    # Return exact matches first, then related, then others (limited)
    return exact_matches + related_matches[:2] + other_matches[:1]


def _filter_empty_tracker_rows(hits: List[Tuple]) -> List[Tuple]:
    """Filter out tracker rows that are mostly null/empty."""
    filtered = []
    for i, s, d, m in hits:
        try:
            if _is_tracker_meta(m):
                data = json.loads(d)
                # Handle both old and new tracker format
                if isinstance(data, dict) and "tracker_data" in data:
                    tracker_data = data["tracker_data"]
                else:
                    tracker_data = data

                non_null_count = sum(
                    1
                    for v in tracker_data.values()
                    if v is not None and str(v).strip() != ""
                )
                if non_null_count >= 5:
                    filtered.append((i, s, d, m))
            else:
                filtered.append((i, s, d, m))
        except Exception:
            filtered.append((i, s, d, m))
    return filtered


def retrieve_context(
    query: str,
    persist_dir: str = "vector_store_faiss",
    index_name: str = "soc_rag",
    embed_model: str = "nomic-embed-text",
    k_tracker: int = 2,
    k_rulebook: int = 5,
) -> Dict[str, Any]:
    """Enhanced dual source retrieval with dynamic rule matching - Context Only."""
    # Ensure rule mapper is loaded
    if not _rule_mapper.loaded:
        _rule_mapper.load_from_artifacts()

    embedder = OllamaEmbedder(model=embed_model)
    indexer = FaissIndexer(persist_dir=persist_dir, index_name=index_name)

    cls = classify_query(query)
    rule_id = cls.get("rule_id", "")

    # Use dynamic query expansion
    tracker_qs = expand_tracker_queries(query) if cls["about_tracker"] else [query]
    rule_qs = expand_rulebook_queries(query, rule_id) if cls["about_rule"] else [query]

    # Enhanced retrieval with dynamic matching
    raw = _retrieve_with_dynamic_matching(
        tracker_qs + rule_qs,
        indexer,
        embedder,
        k_per_query=max(k_tracker, k_rulebook),
        rule_id=rule_id,
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

    # Apply dynamic rule-specific filtering
    if rule_id:
        rule_hits = _filter_by_rule_relevance(rule_hits, rule_id)
        # For exact rule queries, also filter tracker by rule
        if cls.get("is_exact_rule"):
            rule_patterns = [rule_id, f"rule#{rule_id}", f"rule {rule_id}"]
            if _rule_mapper.loaded:
                rule_patterns.extend(_rule_mapper.get_rule_patterns(rule_id))

            tracker_hits = [
                hit
                for hit in tracker_hits
                if any(pattern.lower() in hit[2].lower() for pattern in rule_patterns)
            ]

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
    """Enhanced rule block extraction with dynamic pattern matching."""
    if not text or not rule_id_norm:
        return text

    t = text.replace("\r\n", "\n")
    rid_num = rule_id_norm.lstrip("0")

    # Build comprehensive patterns
    pat_candidates = [
        rf"(?i)^.*Rule#?0*{re.escape(rid_num)}[^0-9].*$",
        rf"(?i)^.*Rule[ #:-]*0*{re.escape(rid_num)}[^0-9].*$",
        rf'(?i)".*Rule#?0*{re.escape(rid_num)}[^0-9][^"]*"',
        rf"(?i)Rule#?0*{re.escape(rid_num)}[^0-9].*",
        rf"(?i)Rule[ #:-]*0*{re.escape(rid_num)}[^0-9].*",
    ]

    # Add dynamic patterns if available
    if _rule_mapper.loaded:
        alert_names = _rule_mapper.get_alert_names(rule_id_norm)
        for alert_name in alert_names:
            escaped_alert = re.escape(alert_name)
            pat_candidates.extend(
                [
                    rf"(?i)^.*{escaped_alert}.*$",
                    rf"(?i){escaped_alert}.*Rule.*{re.escape(rid_num)}",
                    rf"(?i)Rule.*{re.escape(rid_num)}.*{escaped_alert}",
                ]
            )

    start = -1
    for p in pat_candidates:
        try:
            m = re.search(p, t, flags=re.MULTILINE)
            if m:
                start = m.start()
                break
        except re.error:
            continue  # Skip invalid regex patterns

    if start < 0:
        return text

    # Find the end (next rule or end of text)
    next_rule = re.search(
        r"(?i)^.*Rule[ #]*\d{1,4}.*$", t[start + 50 :], flags=re.MULTILINE
    )
    end = start + 50 + next_rule.start() if next_rule else len(t)

    block = t[start:end].strip()

    # If block is too short, expand backwards
    if len(block) < 200:
        pre = t.rfind("\nRow", 0, start)
        if pre != -1:
            block = t[pre:end].strip()

    return block if len(block) > 10 else text


def build_context_block(results: Dict[str, Any], query: str) -> str:
    """Enhanced context building with dynamic rule information."""
    rid = parse_rule_id(query)
    cls = results.get("class", {})
    lines: List[str] = []

    # Add dynamic query context
    if rid:
        lines.append(f"=== QUERY CONTEXT ===")
        lines.append(f"Searching for: Rule {rid}")

        # Add dynamic rule information if available
        if _rule_mapper.loaded:
            alert_names = _rule_mapper.get_alert_names(rid)
            if alert_names:
                lines.append(f"Alert Names: {', '.join(alert_names)}")

        lines.append("")

    # Tracker section
    tr_hits = results.get("tracker") or []
    if tr_hits:
        lines.append("=== TRACKER DATA ===")
        for i, (idx, s, d, m) in enumerate(tr_hits):
            src = (m or {}).get("source") or "tracker"
            rowindex = (m or {}).get("row_index")

            try:
                data = json.loads(d)
                # Handle both old and new tracker format
                if isinstance(data, dict) and "tracker_data" in data:
                    tracker_data = data["tracker_data"]
                    rule_info = data.get("extracted_rule_info", {})
                else:
                    tracker_data = data
                    rule_info = {}

                # Filter to show only relevant fields for rules
                if rid:
                    relevant_data = {}
                    for k, v in tracker_data.items():
                        if v is not None and (
                            "rule" in k.lower()
                            or "incident" in k.lower()
                            or "priority" in k.lower()
                            or "status" in k.lower()
                            or "comments" in k.lower()
                            or "alert" in k.lower()
                        ):
                            relevant_data[k] = v

                    if relevant_data:
                        display_data = relevant_data
                    else:
                        # If no relevant fields, show all
                        display_data = tracker_data
                else:
                    display_data = tracker_data

                # Add rule info if available
                if rule_info:
                    display_data["_extracted_rule_info"] = rule_info

                pretty = json.dumps(display_data, ensure_ascii=False, indent=2)

            except Exception:
                pretty = d.strip()[:4000]

            lines.append(f"[score={s:.3f}] [src={src}] [row={rowindex}]")
            lines.append(pretty)
            lines.append("")

    # Rulebook section
    rb_hits = results.get("rulebook") or []
    if rb_hits:
        lines.append("=== RULEBOOK PROCEDURES ===")
        for i, (idx, s, d, m) in enumerate(rb_hits):
            src = (m or {}).get("source") or (m or {}).get("filetype") or "rulebook"
            block = d

            if rid and len(d) > 100:
                extracted = _extract_rule_block_from_rulebook_text(d, rid)
                if len(extracted) > 10:
                    block = extracted

            lines.append(f"[score={s:.3f}] [src={src}]")
            lines.append(block.strip())
            lines.append("")

    return "\n".join(lines) if lines else "No matching context found."


# Utility functions for external access
def force_reload_rule_mappings():
    """Force reload of rule mappings - useful for testing."""
    global _rule_mapper
    _rule_mapper = DynamicRuleMapper()
    _rule_mapper.load_from_artifacts()
    return _rule_mapper.loaded


def get_dynamic_rule_stats() -> Dict[str, Any]:
    """Get statistics about loaded dynamic rule mappings."""
    if not _rule_mapper.loaded:
        _rule_mapper.load_from_artifacts()

    return {
        "loaded": _rule_mapper.loaded,
        "total_rules": len(_rule_mapper.rule_to_alert_map),
        "total_alert_patterns": len(_rule_mapper.alert_to_rule_map),
        "rules_with_alerts": len(
            [r for r in _rule_mapper.rule_to_alert_map.values() if r]
        ),
        "sample_rules": list(_rule_mapper.rule_to_alert_map.keys())[:5],
        "sample_alerts": list(_rule_mapper.alert_to_rule_map.keys())[:5],
    }
