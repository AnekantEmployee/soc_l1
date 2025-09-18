"""
Utility functions for response generation and data processing.
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
from .config import ARTIFACTS_DIR, CONTEXT_JSON_DIR, REQUIRED_SECTIONS
from ..context_retriever import parse_rule_id


def get_timestamp() -> str:
    """Get current timestamp as string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_structured_context(query: str, structured_data: Dict[str, Any]) -> str:
    """Save structured context data to JSON file."""
    try:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs(CONTEXT_JSON_DIR, exist_ok=True)

        json_path = f"{CONTEXT_JSON_DIR}/{safe_query}_context.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        print(f"💾 Structured context saved to: {json_path}")
        return json_path

    except Exception as e:
        print(f"⚠️ Failed to save structured context JSON: {e}")
        return ""


def validate_response_structure(response: str) -> Tuple[bool, List[str]]:
    """Validate response structure for comprehensive L1 analyst format."""
    missing_sections = []
    for section in REQUIRED_SECTIONS:
        if section not in response:
            missing_sections.append(section)

    # Check for JSON blocks
    has_json_blocks = "```" in response

    is_valid = len(missing_sections) == 0 and not has_json_blocks

    validation_issues = missing_sections.copy()
    if has_json_blocks:
        validation_issues.append("Contains JSON blocks")

    return is_valid, validation_issues


def post_process_response(response: str) -> str:
    """Post-process response to ensure L1 analyst-friendly format compliance."""

    # Remove JSON blocks
    if "```json" in response:
        lines = response.split("\n")
        cleaned_lines = []
        in_json_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_json_block = not in_json_block
                continue
            if not in_json_block:
                cleaned_lines.append(line)

        response = "\n".join(cleaned_lines)

    # Ensure proper header format
    if not response.startswith("# 🛡️ Alert:"):
        rule_match = re.search(r"rule[s]?\s*(\d+)", response, re.IGNORECASE)
        rule_id = rule_match.group(1) if rule_match else "Unknown"
        response = f"# 🛡️ Alert: {rule_id}\n\n" + response

    return response.strip()



def create_error_response(query: str, error_msg: str) -> str:
    """Create a simple error response for L1 analysts."""
    rule_id = parse_rule_id(query) or "Unknown"

    return f"""# 🛡️ Alert: {rule_id} - Analysis Error

## ❌ Issue
-  **Problem**: Unable to process comprehensive rule analysis
-  **Error**: {error_msg}
-  **Time**: {get_timestamp()}

## 🔧 Next Steps
-  Verify the rule ID exists in the system
-  Check context data availability  
-  Contact SOC team lead for manual analysis
-  Escalate if system issues persist"""


def parse_and_structure_context(
    query: str, context_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Parse and structure context_results into comprehensive format."""

    parsed_data = {
        "query": query,
        "metadata": {
            "total_tracker_hits": len(context_results.get("tracker", [])),
            "total_rulebook_hits": len(context_results.get("rulebook", [])),
            "processing_timestamp": get_timestamp(),
        },
        "parsed_data": {
            "tracker_records": [],
            "rulebook_records": [],
        },
    }

    # Parse tracker data (comprehensive)
    tracker_hits = context_results.get("tracker", [])
    for tracker_hit in tracker_hits:
        if len(tracker_hit) >= 4:
            doc_id, score, json_content, metadata = tracker_hit[:4]

            try:
                parsed_json = json.loads(json_content)
                tracker_data = parsed_json.get("tracker_data", parsed_json)
                extracted_rule_info = parsed_json.get("extracted_rule_info", {})

                # Create comprehensive record with ALL fields
                tracker_record = {
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "tracker_data": tracker_data,  # Keep complete original data
                    "extracted_rule_info": extracted_rule_info,
                    # Also extract key fields for easy access
                    "incident_number": tracker_data.get("incidnet no #")
                    or tracker_data.get("incident_no"),
                    "priority": tracker_data.get("priority"),
                    "status": tracker_data.get("status"),
                    "engineer": tracker_data.get("name of the shift engineer"),
                    "resolution_time": tracker_data.get("mttr    (mins)")
                    or tracker_data.get("mttr (mins)"),
                    "resolver_comments": tracker_data.get("resolver comments"),
                }

                parsed_data["parsed_data"]["tracker_records"].append(tracker_record)

            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse tracker JSON: {e}")
                # Still include the record with error information
                parsed_data["parsed_data"]["tracker_records"].append(
                    {
                        "document_id": doc_id,
                        "relevance_score": float(score),
                        "metadata": metadata,
                        "parse_error": str(e),
                        "raw_content": json_content,
                    }
                )

    # Parse rulebook data (comprehensive)
    rulebook_hits = context_results.get("rulebook", [])
    for rulebook_hit in rulebook_hits:
        if len(rulebook_hit) >= 4:
            doc_id, score, content, metadata = rulebook_hit[:4]
            content_type = metadata.get("doctype", "unknown")

            if content_type == "complete_rulebook":
                procedure_steps = []

                # Extract JSON blocks from content
                json_blocks = re.findall(
                    r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL
                )
                for json_block in json_blocks:
                    try:
                        parsed_step = json.loads(json_block)
                        if "row_index" in parsed_step and "data" in parsed_step:
                            procedure_steps.append(parsed_step)
                    except json.JSONDecodeError:
                        continue

                if procedure_steps:  # Only include if we have steps
                    rule_info = {
                        "primary_rule_id": metadata.get("primary_rule_id", ""),
                        "is_direct_read": metadata.get("is_direct_read", False),
                        "total_rows": metadata.get("rows", 0),
                        "is_complete": metadata.get("is_complete", False),
                        "source": metadata.get("source", ""),
                    }

                    rulebook_record = {
                        "document_id": doc_id,
                        "relevance_score": float(score),
                        "metadata": metadata,  # Keep complete metadata
                        "rule_info": rule_info,
                        "procedure_steps": procedure_steps,  # Keep complete procedure steps
                        "content_length": len(content),
                    }

                    parsed_data["parsed_data"]["rulebook_records"].append(
                        rulebook_record
                    )

    return parsed_data
