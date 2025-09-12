import json
import pandas as pd
from typing import List, Dict, Any
from langchain.docstore.document import Document


class DocumentChunker:
    def __init__(self, tracker_df: pd.DataFrame, rulebook_dfs: Dict[str, pd.DataFrame]):
        """
        Initialize document chunker with loaded dataframes
        Args:
            tracker_df: Loaded tracker sheet DataFrame
            rulebook_dfs: Dictionary of loaded rulebook DataFrames
        """
        self.tracker_df = tracker_df
        self.rulebook_dfs = rulebook_dfs
        self.tracker_chunks = []
        self.rulebook_chunks = []

    def _clean_metadata(self, metadata: Dict) -> Dict:
        """Clean metadata to only include simple types"""
        clean_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean_metadata[key] = value
            elif isinstance(value, list):
                # Convert list to string or count
                if all(isinstance(item, str) for item in value):
                    clean_metadata[key] = ", ".join(value)  # Convert to string
                else:
                    clean_metadata[f"{key}_count"] = len(value)  # Store count
            else:
                # Convert other types to string
                clean_metadata[key] = str(value)
        return clean_metadata

    def chunk_tracker_sheet(self) -> List[Document]:
        """Convert tracker sheet rows to JSON-like Document chunks"""
        if self.tracker_df is None or self.tracker_df.empty:
            raise ValueError("Tracker DataFrame is empty or None")

        tracker_chunks = []
        df = self.tracker_df.copy()

        # Clean column names
        df.columns = df.columns.str.strip().str.lower()

        for idx, row in df.iterrows():
            # Convert row to dictionary, handling NaN values
            row_dict = {}
            for col, value in row.items():
                if pd.isna(value):
                    row_dict[col] = None
                elif isinstance(value, (int, float)):
                    row_dict[col] = value
                else:
                    row_dict[col] = str(value).strip()

            # Create JSON string representation
            json_content = json.dumps(row_dict, indent=2, ensure_ascii=False)

            # Create metadata with simple types only
            metadata = {
                "source": "tracker_sheet",
                "row_index": int(idx),
                "doc_type": "tracker_row",
                "total_rows": len(df),
                "columns_count": len(df.columns),
            }

            # Clean metadata
            clean_metadata = self._clean_metadata(metadata)

            # Create Document
            doc = Document(
                page_content=json_content,
                metadata=clean_metadata,
            )
            tracker_chunks.append(doc)

        self.tracker_chunks = tracker_chunks
        return tracker_chunks

    def chunk_rulebooks(self) -> List[Document]:
        """Convert each rulebook to a single Document chunk"""
        if not self.rulebook_dfs:
            raise ValueError("Rulebook DataFrames dictionary is empty")

        rulebook_chunks = []

        for filename, df in self.rulebook_dfs.items():
            if df.empty:
                continue

            # Clean column names
            df_clean = df.copy()
            df_clean.columns = df_clean.columns.str.strip().str.lower()

            # Convert entire rulebook to structured text
            content_parts = []
            content_parts.append(f"RULEBOOK: {filename}")
            content_parts.append("=" * 50)
            content_parts.append(f"Columns: {', '.join(df_clean.columns)}")
            content_parts.append(f"Total Rows: {len(df_clean)}")
            content_parts.append("")

            # Add each row as structured data
            for idx, row in df_clean.iterrows():
                row_data = {}
                for col, value in row.items():
                    if pd.isna(value):
                        row_data[col] = None
                    elif isinstance(value, (int, float)):
                        row_data[col] = value
                    else:
                        row_data[col] = str(value).strip()

                content_parts.append(f"Row {idx + 1}:")
                content_parts.append(json.dumps(row_data, indent=2, ensure_ascii=False))
                content_parts.append("")

            # Join all content
            full_content = "\n".join(content_parts)

            # Create metadata with simple types only
            metadata = {
                "source": filename,
                "doc_type": "rulebook",
                "rows": len(df_clean),
                "columns_count": len(df_clean.columns),
                "file_type": filename.split(".")[-1],
            }

            # Clean metadata
            clean_metadata = self._clean_metadata(metadata)

            # Create Document
            doc = Document(
                page_content=full_content,
                metadata=clean_metadata,
            )
            rulebook_chunks.append(doc)

        self.rulebook_chunks = rulebook_chunks
        return rulebook_chunks

    def create_all_chunks(self) -> Dict[str, List[Document]]:
        """Create all chunks for both tracker sheet and rulebooks"""
        print("📝 Creating document chunks...")

        tracker_chunks = self.chunk_tracker_sheet()
        print(f"✅ Created {len(tracker_chunks)} tracker chunks")

        rulebook_chunks = self.chunk_rulebooks()
        print(f"✅ Created {len(rulebook_chunks)} rulebook chunks")

        return {
            "tracker": tracker_chunks,
            "rulebooks": rulebook_chunks,
            "all_chunks": tracker_chunks + rulebook_chunks,
        }
