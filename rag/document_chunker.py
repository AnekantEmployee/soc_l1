import os
import json
import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Tuple
from langchain.docstore.document import Document

RULE_ID_PAT = re.compile(r"rule[#\s-]*0*(\d{1,4})", re.I)


def _extract_rule_id_from_text(s: str) -> str:
    if not s:
        return ""
    m = RULE_ID_PAT.search(s)
    if m:
        return m.group(1).zfill(3)
    return ""


def _extract_alert_name_from_row(row_dict: Dict[str, Any]) -> str:
    """Extract alert name from row data."""
    candidates = [
        "inputs required",
        "input details",
        "details",
        "rule name",
        "alert name",
        "title",
        "rule",
        "use case",
    ]

    for k in list(row_dict.keys()):
        v = str(row_dict.get(k) or "").strip()
        if not v:
            continue
        if k.lower() in candidates:
            return v
        # Extract text after rule marker as name
        rid = _extract_rule_id_from_text(v)
        if rid:
            after = re.split(
                r"rule[#\s-]*0*\d{1,4}\s*[-:]\s*", v, flags=re.I, maxsplit=1
            )
            if len(after) == 2 and after[14].strip():
                return after[14].strip()
    return ""


class DocumentChunker:
    def __init__(self, tracker_df: pd.DataFrame, rulebook_dfs: Dict[str, pd.DataFrame]):
        self.tracker_df = tracker_df
        self.rulebook_dfs = rulebook_dfs
        self.tracker_chunks: List[Document] = []
        self.rulebook_chunks: List[Document] = []
        self.rule_key_rows: List[Tuple[str, str, str, int]] = []

    def _clean_metadata(self, metadata: Dict) -> Dict:
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
                    row_dict[col] = str(value).strip()
                    if str(value).strip():
                        non_null_count += 1

            # Skip rows with mostly empty data
            if non_null_count < 5:
                continue

            json_content = json.dumps(row_dict, indent=2, ensure_ascii=False)
            metadata = {
                "source": "tracker_sheet",
                "row_index": int(idx),
                "doctype": "tracker_row",
                "total_rows": len(df),
                "columns_count": len(df.columns),
            }
            clean_metadata = self._clean_metadata(metadata)
            doc = Document(page_content=json_content, metadata=clean_metadata)
            tracker_chunks.append(doc)

        self.tracker_chunks = tracker_chunks
        return tracker_chunks

    def chunk_rulebooks(self) -> List[Document]:
        if not self.rulebook_dfs:
            raise ValueError("Rulebook DataFrames dictionary is empty")

        rulebook_chunks = []
        for filename, df in self.rulebook_dfs.items():
            if df.empty:
                continue

            df_clean = df.copy()
            df_clean.columns = df_clean.columns.str.strip().str.lower()

            # Build content
            content_parts = []
            content_parts.append(f"RULEBOOK: {filename}")
            content_parts.append("=" * 50)
            content_parts.append(f"Columns: {', '.join(df_clean.columns)}")
            content_parts.append(f"Total Rows: {len(df_clean)}")
            content_parts.append("")

            for idx, row in df_clean.iterrows():
                row_data = {}
                for col, value in row.items():
                    if pd.isna(value):
                        row_data[col] = None
                    elif isinstance(value, (int, float)):
                        row_data[col] = value
                    else:
                        row_data[col] = str(value).strip()

                # Extract keys for indexing
                joined = " | ".join(
                    [str(v) for v in row_data.values() if v is not None]
                )
                rid = _extract_rule_id_from_text(joined)
                aname = _extract_alert_name_from_row(row_data)

                if rid or aname:
                    self.rule_key_rows.append((rid, aname, filename, int(idx)))

                content_parts.append(f"Row {idx + 1}:")
                content_parts.append(json.dumps(row_data, indent=2, ensure_ascii=False))
                content_parts.append("")

            full_content = "\n".join(content_parts)
            metadata = {
                "source": filename,
                "doctype": "rulebook",
                "rows": len(df_clean),
                "columns_count": len(df_clean.columns),
                "filetype": filename.split(".")[-1],
            }
            clean_metadata = self._clean_metadata(metadata)
            doc = Document(page_content=full_content, metadata=clean_metadata)
            rulebook_chunks.append(doc)

        self.rulebook_chunks = rulebook_chunks
        return rulebook_chunks

    def create_all_chunks(self) -> Dict[str, List[Document]]:
        print("📝 Creating document chunks...")
        tracker_chunks = self.chunk_tracker_sheet()
        print(f"✅ Created {len(tracker_chunks)} tracker chunks (filtered empty rows)")

        rulebook_chunks = self.chunk_rulebooks()
        print(f"✅ Created {len(rulebook_chunks)} rulebook chunks")

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
                f"filetype: {meta.get('filetype','')}\n"
                f"row_index: {meta.get('row_index','')}\n"
                f"metadata: {json.dumps(meta, ensure_ascii=False)}\n"
                "----- CONTENT -----\n"
                f"{content}\n"
                "----- CHUNK END -----\n"
            )

        tracker = chunks.get("tracker") or []
        rulebook = chunks.get("rulebooks") or []
        allc = chunks.get("all_chunks") or []

        lines = []
        lines.append(f"=== CHUNKS DUMP ===\nwritten_utc: {now}\n")
        lines.append(
            f"counts: tracker={len(tracker)}, rulebook={len(rulebook)}, all={len(allc)}\n"
        )

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
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        recs = []
        for rid, aname, filename, row_idx in self.rule_key_rows:
            recs.append(
                {
                    "rule_id": rid,
                    "alert_name": aname,
                    "source": filename,
                    "row_index": row_idx,
                }
            )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(recs, f, ensure_ascii=False, indent=2)
        return out_path
