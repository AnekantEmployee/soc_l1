import os
import json
import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Tuple
from langchain.docstore.document import Document

# Enhanced rule patterns with stricter matching
RULE_ID_PAT = re.compile(r"rule\s*#?\s*0*(\d{1,4})(?:\s*[-:]|$)", re.I)
ENHANCED_RULE_PAT = re.compile(
    r"(?:rule\s*#?\s*)0*(\d{1,4})(?:\s*[-:]\s*(.+?))?(?:\n|$)", re.I
)

# Improved alert name patterns - prioritize rule titles over procedure steps
RULE_TITLE_PATTERNS = [
    r"rule\s*#?\s*\d+\s*[-:]\s*(.+?)(?:\n|description|instruction|$)",
    r"^(.+?)\s*rule\s*#?\s*\d+",
    r"rule\s*#?\s*\d+[:\s-]+([^,\n]+?)(?:description|may|which|$)",
]


# Procedure step keywords to exclude from alert names
PROCEDURE_KEYWORDS = {
    "follow up",
    "track for",
    "check",
    "verify",
    "escalate",
    "inform",
    "raise",
    "document",
    "upload",
    "make a word",
    "write",
    "gather",
    "collect",
    "run",
    "observe",
    "validate",
    "contact",
    "notify",
    "reset",
    "disable",
    "block",
    "false positive",
    "true positive",
    "benign positive",
}


def _extract_rule_id_from_text(s: str) -> str:
    """Enhanced rule ID extraction with exact boundary matching."""
    if not s:
        return ""

    # First try exact rule pattern with word boundaries
    m = re.search(r"\brule\s*#?\s*0*(\d{1,4})\b", s, re.I)
    if m:
        return m.group(1).zfill(3)

    # Fallback to original patterns
    m = ENHANCED_RULE_PAT.search(s)
    if m:
        return m.group(1).zfill(3)

    m = RULE_ID_PAT.search(s)
    if m:
        return m.group(1).zfill(3)

    return ""


def _is_procedure_step(text: str) -> bool:
    """Check if text appears to be a procedure step rather than a rule name."""
    if not text:
        return True

    text_lower = text.lower().strip()

    # Check for procedure keywords
    if any(keyword in text_lower for keyword in PROCEDURE_KEYWORDS):
        return True

    # Check for question-like patterns
    if text_lower.endswith("?") or text_lower.startswith(
        ("how", "what", "when", "where", "why")
    ):
        return True

    # Check for imperative verbs (common in procedure steps)
    imperative_starters = ["check", "verify", "ensure", "confirm", "review", "analyze"]
    if any(text_lower.startswith(verb) for verb in imperative_starters):
        return True

    return False


def _extract_alert_name_from_row(row_dict: Dict[str, Any]) -> str:
    """Enhanced alert name extraction prioritizing actual rule titles."""

    # Strategy 1: Look for rule titles in specific fields
    title_fields = ["inputs required", "rule name", "alert name", "title", "rule"]

    for field_name in title_fields:
        for k, v in row_dict.items():
            if k.lower().strip() == field_name:
                v_str = str(v or "").strip()
                if not v_str:
                    continue

                # Extract rule title from "Rule#XXX - Title" pattern
                rule_title_match = re.search(
                    r"rule\s*#?\s*\d+\s*[-:]?\s*(.+?)(?:$|\n)", v_str, re.I
                )
                if rule_title_match:
                    candidate = rule_title_match.group(1).strip()
                    if (
                        candidate
                        and not _is_procedure_step(candidate)
                        and len(candidate) > 5
                    ):
                        return candidate

                # If field contains rule info but no clear title, use as-is if not procedural
                if "rule" in v_str.lower() and not _is_procedure_step(v_str):
                    return v_str

    # Strategy 2: Look for clean rule descriptions in any field
    for k, v in row_dict.items():
        v_str = str(v or "").strip()
        if len(v_str) < 10 or len(v_str) > 200:  # Skip very short/long text
            continue

        # Look for rule patterns
        for pattern in RULE_TITLE_PATTERNS:
            match = re.search(pattern, v_str, flags=re.I)
            if match:
                candidate = match.group(1).strip()
                if (
                    candidate
                    and not _is_procedure_step(candidate)
                    and len(candidate) > 8
                ):
                    return candidate

    return ""


def _create_rule_metadata_mapping(row_dict: Dict[str, Any]) -> Dict[str, str]:
    """Create comprehensive rule metadata mapping with better filtering."""
    rule_id = _extract_rule_id_from_text(str(row_dict))
    alert_name = _extract_alert_name_from_row(row_dict)

    # Enhanced metadata with quality filtering
    metadata = {
        "rule_id": rule_id,
        "alert_name": alert_name,
        "description": "",
        "severity": "",
        "category": "",
    }

    # Extract additional metadata
    for k, v in row_dict.items():
        v_str = str(v or "").strip()
        k_lower = k.lower()

        if ("description" in k_lower or "instruction" in k_lower) and len(v_str) > 10:
            if not _is_procedure_step(v_str):
                metadata["description"] = v_str[:200]  # Limit length
        elif "priority" in k_lower or "severity" in k_lower:
            metadata["severity"] = v_str
        elif "category" in k_lower or "type" in k_lower:
            metadata["category"] = v_str

    return metadata


class DocumentChunker:
    def __init__(self, tracker_df: pd.DataFrame, rulebook_dfs: Dict[str, pd.DataFrame]):
        self.tracker_df = tracker_df
        self.rulebook_dfs = rulebook_dfs
        self.tracker_chunks: List[Document] = []
        self.rulebook_chunks: List[Document] = []
        self.rule_key_rows: List[Dict[str, Any]] = (
            []
        )  # Changed to dict for deduplication
        self.rule_metadata_map: Dict[str, Dict] = {}

    def _clean_metadata(self, metadata: Dict) -> Dict:
        """Enhanced metadata cleaning with validation."""
        clean_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean_metadata[key] = value
            elif isinstance(value, list):
                if all(isinstance(item, str) for item in value):
                    clean_metadata[key] = ", ".join(value)
                else:
                    clean_metadata[f"{key}_count"] = len(value)
            else:
                clean_metadata[key] = str(value)
        return clean_metadata

    def chunk_tracker_sheet(self) -> List[Document]:
        """Enhanced tracker sheet chunking with better rule extraction."""
        if self.tracker_df is None or self.tracker_df.empty:
            raise ValueError("Tracker DataFrame is empty or None")

        tracker_chunks = []
        df = self.tracker_df.copy()
        df.columns = df.columns.str.strip().str.lower()

        for idx, row in df.iterrows():
            row_dict = {}
            non_null_count = 0

            for col, value in row.items():
                if pd.isna(value):
                    row_dict[col] = None
                elif isinstance(value, (int, float)):
                    row_dict[col] = value
                    non_null_count += 1
                else:
                    clean_val = str(value).strip()
                    row_dict[col] = clean_val
                    if clean_val:
                        non_null_count += 1

            # Skip rows with mostly empty data
            if non_null_count < 5:
                continue

            # Extract rule information with enhanced filtering
            rule_metadata = _create_rule_metadata_mapping(row_dict)

            # Only add to rule keys if we have good quality data
            if rule_metadata["rule_id"] and not _is_procedure_step(
                rule_metadata["alert_name"]
            ):
                rule_key = {
                    "rule_id": rule_metadata["rule_id"],
                    "alert_name": rule_metadata["alert_name"],
                    "source": "tracker_sheet",
                    "row_index": int(idx),
                    "description": rule_metadata["description"],
                    "type": "tracker_data",
                }
                self.rule_key_rows.append(rule_key)

            # Enhanced JSON content
            enhanced_content = {
                "tracker_data": row_dict,
                "extracted_rule_info": rule_metadata,
            }

            json_content = json.dumps(enhanced_content, indent=2, ensure_ascii=False)

            metadata = {
                "source": "tracker_sheet",
                "row_index": int(idx),
                "doctype": "tracker_row",
                "total_rows": len(df),
                "columns_count": len(df.columns),
                "rule_id": rule_metadata["rule_id"],
                "alert_name": rule_metadata["alert_name"],
                "has_rule_info": bool(
                    rule_metadata["rule_id"]
                    and rule_metadata["alert_name"]
                    and not _is_procedure_step(rule_metadata["alert_name"])
                ),
            }

            clean_metadata = self._clean_metadata(metadata)
            doc = Document(page_content=json_content, metadata=clean_metadata)
            tracker_chunks.append(doc)

        self.tracker_chunks = tracker_chunks
        return tracker_chunks

    def chunk_rulebooks(self) -> List[Document]:
        """Enhanced rulebook chunking with complete procedure preservation."""
        if not self.rulebook_dfs:
            raise ValueError("Rulebook DataFrames dictionary is empty")

        rulebook_chunks = []

        for filename, df in self.rulebook_dfs.items():
            if df.empty:
                continue

            df_clean = df.copy()
            df_clean.columns = df_clean.columns.str.strip().str.lower()

            # Extract rule information from filename
            file_rule_id = _extract_rule_id_from_text(filename)

            # Build enhanced content
            content_parts = []
            content_parts.append(f"RULEBOOK: {filename}")
            content_parts.append("=" * 50)

            if file_rule_id:
                content_parts.append(f"PRIMARY RULE: {file_rule_id}")

            content_parts.append(f"Columns: {', '.join(df_clean.columns)}")
            content_parts.append(f"Total Rows: {len(df_clean)}")
            content_parts.append("")

            # Process rows and extract rule information with deduplication
            rule_procedures = []
            seen_rule_entries = set()  # For deduplication

            for idx, row in df_clean.iterrows():
                row_data = {}
                for col, value in row.items():
                    if pd.isna(value):
                        row_data[col] = None
                    elif isinstance(value, (int, float)):
                        row_data[col] = value
                    else:
                        row_data[col] = str(value).strip()

                # Extract rule metadata with enhanced filtering
                rule_metadata = _create_rule_metadata_mapping(row_data)

                # Create unique key for deduplication
                rule_key_signature = (
                    f"{rule_metadata['rule_id']}_{rule_metadata['alert_name']}"
                )

                # Only add high-quality, non-duplicate rule entries
                if (
                    rule_metadata["rule_id"]
                    and rule_metadata["alert_name"]
                    and not _is_procedure_step(rule_metadata["alert_name"])
                    and rule_key_signature not in seen_rule_entries
                ):

                    rule_key = {
                        "rule_id": rule_metadata["rule_id"],
                        "alert_name": rule_metadata["alert_name"],
                        "source": filename,
                        "row_index": int(idx),
                        "description": rule_metadata["description"],
                        "type": "rulebook_procedure",
                    }
                    self.rule_key_rows.append(rule_key)
                    seen_rule_entries.add(rule_key_signature)

                # Store in metadata map
                rid = rule_metadata["rule_id"] or file_rule_id
                if (
                    rid
                    and rule_metadata["alert_name"]
                    and not _is_procedure_step(rule_metadata["alert_name"])
                ):
                    self.rule_metadata_map[rid] = {
                        "alert_name": rule_metadata["alert_name"],
                        "description": rule_metadata["description"],
                        "source_file": filename,
                        "row_index": idx,
                    }

                # Enhanced row representation
                row_repr = {
                    "row_index": idx + 1,
                    "data": row_data,
                    "rule_metadata": rule_metadata,
                }

                if rule_metadata["rule_id"] or rule_metadata["alert_name"]:
                    rule_procedures.append(row_repr)

                content_parts.append(f"Row {idx + 1}:")
                content_parts.append(json.dumps(row_repr, indent=2, ensure_ascii=False))
                content_parts.append("")

            # Add summary of rule procedures
            if rule_procedures:
                content_parts.append("=" * 30)
                content_parts.append("RULE PROCEDURES SUMMARY:")
                for proc in rule_procedures:
                    rule_id = proc["rule_metadata"]["rule_id"]
                    alert_name = proc["rule_metadata"]["alert_name"]
                    if rule_id and not _is_procedure_step(alert_name):
                        content_parts.append(f"- Rule {rule_id}: {alert_name}")

            full_content = "\n".join(content_parts)

            # *** KEY ADDITION: Enhanced metadata for complete rulebooks ***
            metadata = {
                "source": filename,
                "doctype": (
                    "complete_rulebook"
                    if file_rule_id and len(df_clean) <= 25
                    else "rulebook"
                ),
                "rows": len(df_clean),
                "columns_count": len(df_clean.columns),
                "filetype": filename.split(".")[-1],
                "primary_rule_id": file_rule_id,
                "contains_procedures": len(rule_procedures) > 0,
                "procedure_count": len(rule_procedures),
                "is_complete": (
                    True if file_rule_id and len(df_clean) <= 25 else False
                ),  # NEW: Complete flag
                "total_content_length": len(full_content),  # NEW: Content length
            }

            clean_metadata = self._clean_metadata(metadata)
            doc = Document(page_content=full_content, metadata=clean_metadata)
            rulebook_chunks.append(doc)

            # *** KEY ADDITION: Create additional focused chunks for specific rules ***
            if file_rule_id and len(rule_procedures) > 0:
                # Create a focused chunk with just the rule procedures for better retrieval
                focused_content_parts = []
                focused_content_parts.append(f"FOCUSED RULE PROCEDURES: {filename}")
                focused_content_parts.append("=" * 60)
                focused_content_parts.append(f"RULE ID: {file_rule_id}")

                # Add alert names from procedures
                alert_names = [
                    proc["rule_metadata"]["alert_name"]
                    for proc in rule_procedures
                    if proc["rule_metadata"]["alert_name"]
                    and not _is_procedure_step(proc["rule_metadata"]["alert_name"])
                ]
                if alert_names:
                    focused_content_parts.append(
                        f"ALERT NAMES: {', '.join(set(alert_names))}"
                    )

                focused_content_parts.append("")

                # Add all procedure rows with full details
                for proc in rule_procedures:
                    focused_content_parts.append(f"Step {proc['row_index']}:")
                    focused_content_parts.append(
                        json.dumps(proc, indent=2, ensure_ascii=False)
                    )
                    focused_content_parts.append("")

                focused_content = "\n".join(focused_content_parts)

                focused_metadata = {
                    "source": filename,
                    "doctype": "focused_rule_procedures",  # NEW: Focused type
                    "rows": len(rule_procedures),
                    "columns_count": len(df_clean.columns),
                    "filetype": filename.split(".")[-1],
                    "primary_rule_id": file_rule_id,
                    "contains_procedures": True,
                    "procedure_count": len(rule_procedures),
                    "is_complete": True,
                    "is_focused": True,  # NEW: Focused flag
                    "total_content_length": len(focused_content),
                }

                focused_clean_metadata = self._clean_metadata(focused_metadata)
                focused_doc = Document(
                    page_content=focused_content, metadata=focused_clean_metadata
                )
                rulebook_chunks.append(focused_doc)

        self.rulebook_chunks = rulebook_chunks
        return rulebook_chunks

    def create_all_chunks(self) -> Dict[str, List[Document]]:
        """Create all document chunks with enhanced processing and deduplication."""
        print("📝 Creating enhanced document chunks with improved rule extraction...")

        tracker_chunks = self.chunk_tracker_sheet()
        print(
            f"✅ Created {len(tracker_chunks)} tracker chunks (with enhanced rule awareness)"
        )

        rulebook_chunks = self.chunk_rulebooks()
        print(
            f"✅ Created {len(rulebook_chunks)} rulebook chunks (with better rule extraction)"
        )

        # Deduplicate rule keys
        unique_rule_keys = []
        seen_keys = set()

        for rule_key in self.rule_key_rows:
            key_signature = (
                f"{rule_key['rule_id']}_{rule_key['alert_name']}_{rule_key['source']}"
            )
            if key_signature not in seen_keys:
                unique_rule_keys.append(rule_key)
                seen_keys.add(key_signature)

        self.rule_key_rows = unique_rule_keys

        print(
            f"📊 Extracted {len(self.rule_key_rows)} unique rule mappings (deduplicated)"
        )
        print(f"🗂️ Built metadata for {len(self.rule_metadata_map)} unique rules")

        return {
            "tracker": tracker_chunks,
            "rulebooks": rulebook_chunks,
            "all_chunks": tracker_chunks + rulebook_chunks,
        }

    def export_chunks_to_text(
        self,
        chunks: Dict[str, Any],
        out_path: str = "artifacts/all_chunks_dump.txt",
        max_chars_per_chunk: int = 0,
    ) -> str:
        """Export chunks with enhanced formatting and quality indicators."""
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        now = datetime.utcnow().isoformat() + "Z"

        def _doc_to_entry(doc, idx):
            meta = getattr(doc, "metadata", {}) or {}
            content = getattr(doc, "page_content", "") or ""

            if max_chars_per_chunk and len(content) > max_chars_per_chunk:
                content = content[:max_chars_per_chunk] + "\n...[TRUNCATED]"

            return (
                "----- CHUNK START -----\n"
                f"index: {idx}\n"
                f"doctype: {meta.get('doctype','')}\n"
                f"source: {meta.get('source','')}\n"
                f"rule_id: {meta.get('rule_id','')}\n"
                f"alert_name: {meta.get('alert_name','')}\n"
                f"has_rule_info: {meta.get('has_rule_info','')}\n"
                f"metadata: {json.dumps(meta, ensure_ascii=False)}\n"
                "----- CONTENT -----\n"
                f"{content}\n"
                "----- CHUNK END -----\n"
            )

        tracker = chunks.get("tracker") or []
        rulebook = chunks.get("rulebooks") or []
        allc = chunks.get("all_chunks") or []

        lines = []
        lines.append(f"=== ENHANCED CHUNKS DUMP ===\nwritten_utc: {now}\n")
        lines.append(
            f"counts: tracker={len(tracker)}, rulebook={len(rulebook)}, all={len(allc)}\n"
        )
        lines.append(f"rule_mappings: {len(self.rule_key_rows)}\n")
        lines.append(f"unique_rules: {len(self.rule_metadata_map)}\n")

        if allc:
            for i, d in enumerate(allc, 1):
                lines.append(_doc_to_entry(d, i))
        else:
            idx = 1
            for d in tracker:
                lines.append(_doc_to_entry(d, idx))
                idx += 1
            for d in rulebook:
                lines.append(_doc_to_entry(d, idx))
                idx += 1

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return out_path

    def export_rule_keys(self, out_path: str = "artifacts/rule_keys.json") -> str:
        """Export enhanced rule keys with better quality and deduplication."""
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        # Export data with quality metrics
        export_data = {
            "rule_keys": self.rule_key_rows,
            "rule_metadata_map": self.rule_metadata_map,
            "extraction_stats": {
                "total_rules_found": len(self.rule_key_rows),
                "unique_rules": len(self.rule_metadata_map),
                "rules_with_names": len(
                    [
                        r
                        for r in self.rule_key_rows
                        if r["alert_name"] and not _is_procedure_step(r["alert_name"])
                    ]
                ),
                "files_processed": len(set(r["source"] for r in self.rule_key_rows)),
                "quality_score": len(
                    [
                        r
                        for r in self.rule_key_rows
                        if r["alert_name"] and not _is_procedure_step(r["alert_name"])
                    ]
                )
                / max(len(self.rule_key_rows), 1),
            },
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return out_path

    def export_rule_metadata_map(
        self, out_path: str = "artifacts/rule_metadata_map.json"
    ) -> str:
        """Export the rule metadata mapping for quick lookup."""
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.rule_metadata_map, f, ensure_ascii=False, indent=2)

        return out_path
