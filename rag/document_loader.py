import os
import logging
import pandas as pd
from typing import Dict, List, Tuple
import chardet


class DocumentLoader:
    def __init__(self, tracker_path: str, rulebook_dir: str):
        """
        Enhanced document loader for tracker sheet and rulebooks with better error handling.

        Args:
            tracker_path: Path to the tracker sheet (xlsx/csv)
            rulebook_dir: Directory containing all rulebook files (xlsx/csv)
        """
        self.tracker_path = tracker_path
        self.rulebook_dir = rulebook_dir
        self.tracker_sheet = None
        self.rulebooks = {}
        self.loading_stats = {}
        self.logger = logging.getLogger(__name__)

    def _detect_file_encoding(self, file_path: str) -> str:
        """Detect file encoding using chardet."""
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read(10000)  # Read first 10KB for detection
            result = chardet.detect(raw_data)
            encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0)

            if confidence > 0.7:
                return encoding
            else:
                return "utf-8"  # Fallback to utf-8

        except Exception as e:
            self.logger.warning(f"Encoding detection failed for {file_path}: {e}")
            return "utf-8"

    def _read_csv_with_fallback_encoding(self, file_path: str) -> pd.DataFrame:
        """Enhanced CSV reading with automatic encoding detection."""
        # First try automatic detection
        detected_encoding = self._detect_file_encoding(file_path)

        encodings = [
            detected_encoding,
            "utf-8",
            "cp1252",
            "iso-8859-1",
            "latin1",
            "utf-16",
        ]
        # Remove duplicates while preserving order
        encodings = list(dict.fromkeys(encodings))

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)

                # Validate that we got reasonable data
                if not df.empty and not df.columns.empty:
                    self.logger.info(
                        f"Successfully read {file_path} with encoding: {encoding}"
                    )
                    return df

            except UnicodeDecodeError as e:
                self.logger.debug(f"Encoding {encoding} failed for {file_path}: {e}")
                continue
            except Exception as e:
                self.logger.debug(f"Error reading {file_path} with {encoding}: {e}")
                continue

        # Last resort: read with errors ignored
        try:
            df = pd.read_csv(file_path, encoding="utf-8", errors="ignore")
            self.logger.warning(f"Read {file_path} with errors ignored")
            return df
        except Exception as e:
            raise Exception(
                f"Could not read CSV file {file_path} with any encoding. Last error: {e}"
            )

    def _validate_dataframe(self, df: pd.DataFrame, file_path: str) -> Tuple[bool, str]:
        """Validate loaded dataframe quality."""
        if df is None:
            return False, "DataFrame is None"

        if df.empty:
            return False, "DataFrame is empty"

        if len(df.columns) == 0:
            return False, "No columns found"

        # Check for reasonable column names
        suspicious_columns = sum(
            1 for col in df.columns if str(col).startswith("Unnamed")
        )
        if suspicious_columns > len(df.columns) * 0.8:
            return (
                False,
                f"Too many unnamed columns ({suspicious_columns}/{len(df.columns)})",
            )

        # Check data quality
        total_cells = len(df) * len(df.columns)
        null_cells = df.isnull().sum().sum()
        null_ratio = null_cells / total_cells if total_cells > 0 else 1

        if null_ratio > 0.95:
            return False, f"Too many null values ({null_ratio:.2%})"

        return True, "Valid"

    def load_tracker_sheet(self) -> pd.DataFrame:
        """Enhanced tracker sheet loading with validation."""
        try:
            if not os.path.exists(self.tracker_path):
                raise FileNotFoundError(f"Tracker file not found: {self.tracker_path}")

            if self.tracker_path.endswith(".csv"):
                self.tracker_sheet = self._read_csv_with_fallback_encoding(
                    self.tracker_path
                )
            elif self.tracker_path.endswith((".xlsx", ".xls")):
                try:
                    self.tracker_sheet = pd.read_excel(self.tracker_path)
                except Exception as e:
                    # Try with different engines
                    for engine in ["openpyxl", "xlrd"]:
                        try:
                            self.tracker_sheet = pd.read_excel(
                                self.tracker_path, engine=engine
                            )
                            break
                        except:
                            continue
                    else:
                        raise e
            else:
                raise ValueError(
                    f"Unsupported tracker file format: {self.tracker_path}. "
                    "Supported formats: .csv, .xlsx, .xls"
                )

            # Validate the loaded data
            is_valid, msg = self._validate_dataframe(
                self.tracker_sheet, self.tracker_path
            )
            if not is_valid:
                raise ValueError(f"Invalid tracker data: {msg}")

            # Clean column names
            self.tracker_sheet.columns = [
                str(col).strip() for col in self.tracker_sheet.columns
            ]

            print(
                f"✅ Loaded tracker sheet: {self.tracker_sheet.shape[0]} rows, "
                f"{self.tracker_sheet.shape[1]} columns"
            )

            # Log sample of column names for debugging
            sample_cols = list(self.tracker_sheet.columns)[:5]
            print(f"📋 Sample columns: {sample_cols}")

            return self.tracker_sheet

        except Exception as e:
            raise Exception(
                f"Error loading tracker sheet from {self.tracker_path}: {e}"
            )

    def load_rulebooks(self) -> Dict[str, pd.DataFrame]:
        """Enhanced rulebook loading with better file filtering and validation."""
        try:
            if not os.path.exists(self.rulebook_dir):
                raise FileNotFoundError(
                    f"Rulebook directory not found: {self.rulebook_dir}"
                )

            # Enhanced file filtering
            all_files = os.listdir(self.rulebook_dir)
            supported_extensions = {".csv", ".xlsx", ".xls"}

            files = []
            for f in all_files:
                file_path = os.path.join(self.rulebook_dir, f)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(f.lower())
                    if ext in supported_extensions:
                        # Skip temporary/backup files
                        if not f.startswith(("~$", ".~", "temp", "backup")):
                            files.append(f)

            print(f"📁 Found {len(files)} rulebook files in {self.rulebook_dir}")

            if not files:
                print("⚠️ No valid rulebook files found")
                return {}

            successful_loads = 0

            for file in files:
                file_path = os.path.join(self.rulebook_dir, file)

                try:
                    # Load based on file type
                    if file.lower().endswith(".csv"):
                        df = self._read_csv_with_fallback_encoding(file_path)
                    else:  # Excel files
                        try:
                            df = pd.read_excel(file_path)
                        except Exception as e:
                            # Try different engines for Excel
                            for engine in ["openpyxl", "xlrd"]:
                                try:
                                    df = pd.read_excel(file_path, engine=engine)
                                    break
                                except:
                                    continue
                            else:
                                raise e

                    # Validate the loaded data
                    is_valid, msg = self._validate_dataframe(df, file_path)
                    if not is_valid:
                        self.loading_stats[file] = {
                            "status": "invalid",
                            "error": f"Validation failed: {msg}",
                            "rows": 0,
                            "columns": 0,
                        }
                        print(f"⚠️ Skipping {file}: {msg}")
                        continue

                    # Clean column names
                    df.columns = [str(col).strip() for col in df.columns]

                    self.rulebooks[file] = df
                    successful_loads += 1

                    self.loading_stats[file] = {
                        "rows": df.shape[0],
                        "columns": df.shape[1],
                        "status": "success",
                        "encoding": getattr(df, "_encoding", "auto-detected"),
                        "has_rule_content": self._check_rule_content(df),
                    }

                    print(
                        f"✅ Loaded {file}: {df.shape[0]} rows, {df.shape[1]} columns"
                    )

                except Exception as e:
                    self.loading_stats[file] = {
                        "status": "failed",
                        "error": str(e),
                        "rows": 0,
                        "columns": 0,
                    }
                    print(f"❌ Error loading {file}: {e}")

            print(
                f"✅ Successfully loaded {successful_loads}/{len(files)} rulebook files"
            )

            # Print summary statistics
            if successful_loads > 0:
                total_rows = sum(df.shape[0] for df in self.rulebooks.values())
                rule_files = sum(
                    1
                    for stats in self.loading_stats.values()
                    if stats.get("has_rule_content", False)
                )
                print(
                    f"📊 Total rulebook data: {total_rows} rows across {rule_files} rule-containing files"
                )

            return self.rulebooks

        except Exception as e:
            raise Exception(f"Error loading rulebooks from {self.rulebook_dir}: {e}")

    def _check_rule_content(self, df: pd.DataFrame) -> bool:
        """Check if dataframe contains rule-related content."""
        if df.empty:
            return False    

        # Check column names
        rule_indicators = [
            "rule",
            "alert", 
            "incident",
            "procedure",
            "step", 
            "instruction",
        ]

        for col in df.columns:
            col_lower = str(col).lower()
            if any(indicator in col_lower for indicator in rule_indicators):
                return True

        # Check a sample of data content
        sample_size = min(10, len(df))
        
        for _, row in df.head(sample_size).iterrows():
            row_text = " ".join([str(val).lower() for val in row.values])
            if "rule" in row_text and any(c.isdigit() for c in row_text):
                return True

        return False


    def load_all_documents(self) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """Enhanced document loading with comprehensive error handling."""
        print("📊 Starting enhanced document loading process...")

        try:
            tracker_df = self.load_tracker_sheet()
        except Exception as e:
            print(f"❌ Failed to load tracker sheet: {e}")
            raise

        try:
            rulebook_dfs = self.load_rulebooks()
        except Exception as e:
            print(f"❌ Failed to load rulebooks: {e}")
            # Don't raise here, allow processing with just tracker data
            rulebook_dfs = {}

        # Generate loading report
        self._generate_loading_report()

        return tracker_df, rulebook_dfs

    def _generate_loading_report(self):
        """Generate comprehensive loading report."""
        print("\n" + "=" * 50)
        print("📋 DOCUMENT LOADING REPORT")
        print("=" * 50)

        # Tracker report
        if self.tracker_sheet is not None:
            print(
                f"✅ Tracker Sheet: {self.tracker_sheet.shape[0]} rows, {self.tracker_sheet.shape[1]} cols"
            )
            rule_mentions = 0
            if "rule" in str(self.tracker_sheet.columns).lower():
                rule_col = [
                    col
                    for col in self.tracker_sheet.columns
                    if "rule" in str(col).lower()
                ]
                if rule_col:
                    rule_mentions = self.tracker_sheet[rule_col[0]].notna().sum()
                    print(f"   📊 Found {rule_mentions} entries with rule information")
        else:
            print("❌ Tracker Sheet: Failed to load")

        # Rulebook report
        print(f"\n📚 Rulebooks: {len(self.rulebooks)} files loaded")

        status_counts = {}
        for stats in self.loading_stats.values():
            status = stats.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in status_counts.items():
            emoji = "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
            print(f"   {emoji} {status.title()}: {count} files")

        # Rule content summary
        rule_files = [
            f
            for f, stats in self.loading_stats.items()
            if stats.get("has_rule_content", False)
        ]

        if rule_files:
            print(f"\n🔧 Files with rule content: {len(rule_files)}")
            for file in rule_files[:5]:  # Show first 5
                stats = self.loading_stats[file]
                print(f"   📄 {file}: {stats.get('rows', 0)} rows")
            if len(rule_files) > 5:
                print(f"   ... and {len(rule_files) - 5} more")

        print("=" * 50)

    def get_loading_stats(self) -> Dict:
        """Get comprehensive loading statistics."""
        return {
            "tracker_loaded": self.tracker_sheet is not None,
            "tracker_shape": (
                self.tracker_sheet.shape if self.tracker_sheet is not None else None
            ),
            "rulebooks_loaded": len(self.rulebooks),
            "file_stats": self.loading_stats,
            "successful_files": [
                f for f, s in self.loading_stats.items() if s.get("status") == "success"
            ],
            "failed_files": [
                f for f, s in self.loading_stats.items() if s.get("status") == "failed"
            ],
            "rule_content_files": [
                f
                for f, s in self.loading_stats.items()
                if s.get("has_rule_content", False)
            ],
        }
