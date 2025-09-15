import os
import json
import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Tuple
from langchain.docstore.document import Document

RULE_ID_PAT = re.compile(r"rule[#\s-]*0*(\d{1,4})", re.I)
ENHANCED_RULE_PAT = re.compile(r"(?:rule\s*#?\s*)(\d{1,4})(?:\s*[-:]\s*(.+?))?", re.I)

# Enhanced alert name patterns for better extraction
ALERT_NAME_PATTERNS = [
    r"rule\s*#?\s*\d+\s*[-:]\s*(.+?)(?:\n|$)",
    r"^(.+?)\s*-\s*rule\s*#?\s*\d+",
    r"rule\s*#?\s*\d+\s*(.+?)(?:description|instruction|$)",
]


def _extract_rule_id_from_text(s: str) -> str:
    """Enhanced rule ID extraction."""
    if not s:
        return ""

    m = ENHANCED_RULE_PAT.search(s)
    if m:
        return m.group(1).zfill(3)

    m = RULE_ID_PAT.search(s)
    if m:
        return m.group(1).zfill(3)

    return ""


def _extract_alert_name_from_row(row_dict: Dict[str, Any]) -> str:
    """Enhanced alert name extraction with multiple strategies."""
    candidates = [
        "inputs required",
        "input details",
        "details",
        "rule name",
        "alert name",
        "title",
        "rule",
        "use case",
        "alert/incident",
    ]

    # Strategy 1: Direct field mapping
    for k in list(row_dict.keys()):
        v = str(row_dict.get(k) or "").strip()
        if not v:
            continue
        if k.lower() in candidates:
            # Clean up the alert name
            clean_name = re.sub(r"rule\s*#?\s*\d+\s*[-:]?\s*", "", v, flags=re.I)
            if clean_name and clean_name != v:
                return clean_name.strip()
            return v

    # Strategy 2: Extract from rule patterns
    for k, v in row_dict.items():
        v_str = str(v or "").strip()
        if not v_str:
            continue

        # Look for rule patterns with descriptions
        for pattern in ALERT_NAME_PATTERNS:
            match = re.search(pattern, v_str, flags=re.I)
            if match:
                alert_name = match.group(1).strip()
                if len(alert_name) > 5:  # Avoid very short matches
                    return alert_name

    return ""


def _create_rule_metadata_mapping(row_dict: Dict[str, Any]) -> Dict[str, str]:
    """Create comprehensive rule metadata mapping."""
    rule_id = _extract_rule_id_from_text(str(row_dict))
    alert_name = _extract_alert_name_from_row(row_dict)

    # Extract additional metadata
    metadata = {
        "rule_id": rule_id,
        "alert_name": alert_name,
        "description": "",
        "severity": "",
        "category": "",
    }

    # Try to extract description and other fields
    for k, v in row_dict.items():
        v_str = str(v or "").lower().strip()
        k_lower = k.lower()

        if "description" in k_lower or "instruction" in k_lower:
            metadata["description"] = str(v or "").strip()
        elif "priority" in k_lower or "severity" in k_lower:
            metadata["severity"] = str(v or "").strip()
        elif "category" in k_lower or "type" in k_lower:
            metadata["category"] = str(v or "").strip()

    return metadata


class DocumentChunker:
    def __init__(self, tracker_df: pd.DataFrame, rulebook_dfs: Dict[str, pd.DataFrame]):
        self.tracker_df = tracker_df
        self.rulebook_dfs = rulebook_dfs
        self.tracker_chunks: List[Document] = []
        self.rulebook_chunks: List[Document] = []
        self.rule_key_rows: List[Tuple[str, str, str, int]] = []
        self.rule_metadata_map: Dict[str, Dict] = {}

    def _clean_metadata(self, metadata: Dict) -> Dict:
        """Enhanced metadata cleaning."""
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
        """Enhanced tracker sheet chunking with rule awareness."""
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

            # Extract rule information for enhanced indexing
            rule_metadata = _create_rule_metadata_mapping(row_dict)

            # Enhanced JSON content with rule awareness
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
                    rule_metadata["rule_id"] or rule_metadata["alert_name"]
                ),
            }

            clean_metadata = self._clean_metadata(metadata)
            doc = Document(page_content=json_content, metadata=clean_metadata)
            tracker_chunks.append(doc)

        self.tracker_chunks = tracker_chunks
        return tracker_chunks

    def chunk_rulebooks(self) -> List[Document]:
        """Enhanced rulebook chunking with better rule extraction."""
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

            # Process each row with enhanced rule extraction
            rule_procedures = []
            for idx, row in df_clean.iterrows():
                row_data = {}
                for col, value in row.items():
                    if pd.isna(value):
                        row_data[col] = None
                    elif isinstance(value, (int, float)):
                        row_data[col] = value
                    else:
                        row_data[col] = str(value).strip()

                # Extract rule metadata
                rule_metadata = _create_rule_metadata_mapping(row_data)

                # Store rule information
                rid = rule_metadata["rule_id"] or file_rule_id
                aname = rule_metadata["alert_name"]

                if rid or aname:
                    self.rule_key_rows.append((rid, aname, filename, int(idx)))

                    # Store in metadata map for quick lookup
                    if rid:
                        self.rule_metadata_map[rid] = {
                            "alert_name": aname,
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
                    if rule_id:
                        content_parts.append(f"- Rule {rule_id}: {alert_name}")

            full_content = "\n".join(content_parts)

            metadata = {
                "source": filename,
                "doctype": "rulebook",
                "rows": len(df_clean),
                "columns_count": len(df_clean.columns),
                "filetype": filename.split(".")[-1],
                "primary_rule_id": file_rule_id,
                "contains_procedures": len(rule_procedures) > 0,
                "procedure_count": len(rule_procedures),
            }

            clean_metadata = self._clean_metadata(metadata)
            doc = Document(page_content=full_content, metadata=clean_metadata)
            rulebook_chunks.append(doc)

        self.rulebook_chunks = rulebook_chunks
        return rulebook_chunks

    def create_all_chunks(self) -> Dict[str, List[Document]]:
        """Create all document chunks with enhanced processing."""
        print("📝 Creating enhanced document chunks...")

        tracker_chunks = self.chunk_tracker_sheet()
        print(f"✅ Created {len(tracker_chunks)} tracker chunks (with rule awareness)")

        rulebook_chunks = self.chunk_rulebooks()
        print(
            f"✅ Created {len(rulebook_chunks)} rulebook chunks (with enhanced rule extraction)"
        )

        print(f"📊 Extracted {len(self.rule_key_rows)} rule mappings")
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
        """Export chunks with enhanced formatting."""
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
        """Export enhanced rule keys with metadata."""
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        recs = []
        for rid, aname, filename, row_idx in self.rule_key_rows:
            rec = {
                "rule_id": rid,
                "alert_name": aname,
                "source": filename,
                "row_index": row_idx,
            }

            # Add metadata if available
            if rid and rid in self.rule_metadata_map:
                rec.update(self.rule_metadata_map[rid])

            recs.append(rec)

        # Also export the metadata map
        export_data = {
            "rule_keys": recs,
            "rule_metadata_map": self.rule_metadata_map,
            "extraction_stats": {
                "total_rules_found": len(recs),
                "unique_rules": len(self.rule_metadata_map),
                "rules_with_names": len([r for r in recs if r["alert_name"]]),
                "files_processed": len(set(r["source"] for r in recs)),
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
