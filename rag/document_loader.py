import os
import logging
import pandas as pd
from typing import Dict


class DocumentLoader:
    def __init__(self, tracker_path: str, rulebook_dir: str):
        """
        Initialize document loader for tracker sheet and rulebooks
        Args:
            tracker_path: Path to the tracker sheet (xlsx/csv)
            rulebook_dir: Directory containing all rulebook files (xlsx/csv)
        """
        self.tracker_path = tracker_path
        self.rulebook_dir = rulebook_dir
        self.tracker_sheet = None
        self.rulebooks = {}
        self.loading_stats = {}

        # Setup minimal logging
        self.logger = logging.getLogger(__name__)

    def _read_csv_with_fallback_encoding(self, file_path: str) -> pd.DataFrame:
        """Read CSV with multiple encoding attempts"""
        encodings = ["utf-8", "cp1252", "iso-8859-1", "latin1", "utf-16"]

        for encoding in encodings:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

        # Final attempt with error handling
        try:
            return pd.read_csv(file_path, encoding="utf-8", errors="ignore")
        except Exception as e:
            raise Exception(
                f"Could not read CSV file {file_path} with any encoding: {e}"
            )

    def load_tracker_sheet(self) -> pd.DataFrame:
        """Load the tracker sheet from CSV or XLSX format"""
        try:
            if self.tracker_path.endswith(".csv"):
                self.tracker_sheet = self._read_csv_with_fallback_encoding(
                    self.tracker_path
                )
            elif self.tracker_path.endswith(".xlsx"):
                self.tracker_sheet = pd.read_excel(self.tracker_path)
            else:
                raise ValueError("Unsupported tracker file format. Use .csv or .xlsx")

            print(
                f"✅ Loaded tracker sheet: {self.tracker_sheet.shape[0]} rows, {self.tracker_sheet.shape[1]} columns"
            )
            return self.tracker_sheet

        except Exception as e:
            raise Exception(f"Error loading tracker sheet: {e}")

    def load_rulebooks(self) -> Dict[str, pd.DataFrame]:
        """Load all rulebook files"""
        try:
            if not os.path.exists(self.rulebook_dir):
                raise FileNotFoundError(
                    f"Rulebook directory not found: {self.rulebook_dir}"
                )

            files = [
                f
                for f in os.listdir(self.rulebook_dir)
                if f.endswith((".csv", ".xlsx"))
            ]
            print(f"📁 Found {len(files)} rulebook files")

            for file in files:
                file_path = os.path.join(self.rulebook_dir, file)
                try:
                    if file.endswith(".csv"):
                        df = self._read_csv_with_fallback_encoding(file_path)
                    else:  # .xlsx
                        df = pd.read_excel(file_path)

                    self.rulebooks[file] = df
                    self.loading_stats[file] = {
                        "rows": df.shape[0],
                        "columns": df.shape[1],
                        "status": "success",
                    }

                except Exception as e:
                    self.loading_stats[file] = {"status": "failed", "error": str(e)}
                    print(f"⚠️ Error loading {file}: {e}")

            successful_loads = sum(
                1 for stat in self.loading_stats.values() if stat["status"] == "success"
            )
            print(
                f"✅ Successfully loaded {successful_loads}/{len(files)} rulebook files"
            )

            return self.rulebooks

        except Exception as e:
            raise Exception(f"Error loading rulebooks: {e}")

    def load_all_documents(self) -> tuple:
        """Load both tracker sheet and all rulebooks"""
        print("📊 Starting document loading process...")

        # Load tracker sheet
        tracker_df = self.load_tracker_sheet()

        # Load rulebooks
        rulebook_dfs = self.load_rulebooks()

        return tracker_df, rulebook_dfs
