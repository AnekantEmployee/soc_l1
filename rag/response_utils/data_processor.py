"""
Data processing functions for extracting and formatting rule-specific data.
"""

import json
from typing import Dict, Any
from ..context_retriever import parse_rule_id


def extract_rule_specific_data(
    structured_data: Dict[str, Any], query: str
) -> Dict[str, Any]:
    """Extract and filter rule-specific data from structured context."""
    rule_id = parse_rule_id(query)
    query_lower = query.lower()

    # Initialize filtered data structure
    filtered_data = {
        "query": query,
        "target_rule_id": rule_id,
        "metadata": structured_data.get("metadata", {}),
        "tracker_records": [],
        "rulebook_records": [],
        "extraction_summary": {
            "total_tracker_records": 0,
            "total_rulebook_records": 0,
            "matching_tracker_records": 0,
            "matching_rulebook_records": 0,
        },
    }

    # Extract tracker records
    all_tracker_records = structured_data.get("parsed_data", {}).get(
        "tracker_records", []
    )
    filtered_data["extraction_summary"]["total_tracker_records"] = len(
        all_tracker_records
    )

    for record in all_tracker_records:
        should_include = False

        if rule_id:
            # Check extracted rule info
            extracted_rule = record.get("extracted_rule_info", {})
            if extracted_rule.get("rule_id") == rule_id:
                should_include = True

            # Check metadata
            metadata = record.get("metadata", {})
            if metadata.get("rule_id") == rule_id:
                should_include = True

            # Check tracker data
            tracker_data = record.get("tracker_data", {})
            if tracker_data.get("rule") and rule_id in str(
                tracker_data.get("rule", "")
            ):
                should_include = True

        # If no specific rule ID, check for query terms in alert name or description
        if not rule_id:
            tracker_data = record.get("tracker_data", {})
            alert_name = str(tracker_data.get("alert/incident", "")).lower()
            rule_field = str(tracker_data.get("rule", "")).lower()

            # Check if query terms match alert name or rule field
            query_terms = [term for term in query_lower.split() if len(term) > 2]
            for term in query_terms:
                if term in alert_name or term in rule_field:
                    should_include = True
                    break

        if should_include:
            filtered_data["tracker_records"].append(record)
            filtered_data["extraction_summary"]["matching_tracker_records"] += 1

    # Extract rulebook records
    all_rulebook_records = structured_data.get("parsed_data", {}).get(
        "rulebook_records", []
    )
    filtered_data["extraction_summary"]["total_rulebook_records"] = len(
        all_rulebook_records
    )

    for record in all_rulebook_records:
        should_include = False

        if rule_id:
            rule_info = record.get("rule_info", {})
            if rule_info.get("primary_rule_id") == rule_id:
                should_include = True

            metadata = record.get("metadata", {})
            if metadata.get("primary_rule_id") == rule_id:
                should_include = True

        if not rule_id:
            should_include = True

        if should_include:
            filtered_data["rulebook_records"].append(record)
            filtered_data["extraction_summary"]["matching_rulebook_records"] += 1

    return filtered_data


def format_json_for_llm(filtered_data: Dict[str, Any]) -> str:
    """Format filtered data as comprehensive JSON for LLM consumption - include ALL details."""
    try:
        # Create comprehensive structure including ALL available data
        llm_data = {
            "query_analysis": {
                "original_query": filtered_data.get("query"),
                "target_rule_id": filtered_data.get("target_rule_id"),
                "extraction_summary": filtered_data.get("extraction_summary"),
            },
            "complete_incident_data": [],
            "complete_procedure_data": [],
        }

        # Process tracker records - include EVERY field available
        for record in filtered_data.get("tracker_records", []):
            incident_info = record.get("tracker_data", {})
            extracted_rule = record.get("extracted_rule_info", {})

            # Include ALL tracker data fields
            complete_incident = {
                "document_metadata": record.get("metadata", {}),
                "relevance_score": record.get("relevance_score"),
                "extracted_rule_info": extracted_rule,
                # All incident details
                "incident_number": incident_info.get("incidnet no #")
                or incident_info.get("incident_no"),
                "serial_number": incident_info.get("s.no."),
                "date": incident_info.get("date"),
                "month": incident_info.get("month"),
                "shift": incident_info.get("shift"),
                "data_connector": incident_info.get("data connecter"),
                "priority": incident_info.get("priority"),
                "alert_type": incident_info.get("alert/incident"),
                "engineer": incident_info.get("name of the shift engineer"),
                "handover_engineers": incident_info.get("handover shift engineer"),
                # Timestamps
                "reported_timestamp": incident_info.get("reported time stamp"),
                "responded_timestamp": incident_info.get("responded time stamp"),
                "resolution_timestamp": incident_info.get("resolution time stamp"),
                # Metrics
                "mttd_mins": incident_info.get("mttd (mins)"),
                "mttr_mins": incident_info.get("mttr    (mins)")
                or incident_info.get("mttr (mins)"),
                "time_to_breach_sla": incident_info.get("time to breach sla"),
                "remaining_mins_to_breach": incident_info.get(
                    "remaining mins to breach"
                ),
                # Investigation details
                "resolver_comments": incident_info.get("resolver comments"),
                "triaging_steps": incident_info.get("triaging steps"),
                "vip_users": incident_info.get("vip users"),
                "rule_details": incident_info.get("rule"),
                "service_owner": incident_info.get("service owner"),
                "status": incident_info.get("status"),
                "remarks_comments": incident_info.get("remarks / comments"),
                # Classification
                "classification": incident_info.get("false / true positive"),
                "why_false_positive": incident_info.get("why false positive"),
                "justification": incident_info.get("justification"),
                "quality_audit": incident_info.get("quality audit"),
                "description": incident_info.get("description"),
                "escalated_to": incident_info.get("escalated to"),
                # Include any additional fields
                "additional_fields": {
                    k: v
                    for k, v in incident_info.items()
                    if k
                    not in [
                        "incidnet no #",
                        "incident_no",
                        "s.no.",
                        "date",
                        "month",
                        "shift",
                        "data connecter",
                        "priority",
                        "alert/incident",
                        "name of the shift engineer",
                        "handover shift engineer",
                        "reported time stamp",
                        "responded time stamp",
                        "resolution time stamp",
                        "mttd (mins)",
                        "mttr    (mins)",
                        "mttr (mins)",
                        "time to breach sla",
                        "remaining mins to breach",
                        "resolver comments",
                        "triaging steps",
                        "vip users",
                        "rule",
                        "service owner",
                        "status",
                        "remarks / comments",
                        "false / true positive",
                        "why false positive",
                        "justification",
                        "quality audit",
                        "description",
                        "escalated to",
                    ]
                },
            }
            llm_data["complete_incident_data"].append(complete_incident)

        # Process rulebook records - include ALL procedure steps with complete details
        for record in filtered_data.get("rulebook_records", []):
            procedure_steps = record.get("procedure_steps", [])

            complete_procedures = {
                "rule_info": record.get("rule_info", {}),
                "document_metadata": record.get("metadata", {}),
                "relevance_score": record.get("relevance_score"),
                "complete_procedure_steps": [],
            }

            # Include ALL procedure steps with ALL details
            for step in procedure_steps:
                step_data = step.get("data", {})
                rule_metadata = step.get("rule_metadata", {})

                complete_step = {
                    "row_index": step.get("row_index"),
                    "serial_number": step_data.get("sr.no.") or step_data.get("s.no"),
                    "inputs_required": step_data.get("inputs required"),
                    "input_details": step_data.get("input details"),
                    "instructions": step_data.get("instructions"),
                    "existing_new": step_data.get("exisiting / new"),
                    "duration": step_data.get("duration"),
                    "rule_metadata": rule_metadata,
                    # Include any additional step fields
                    "additional_step_data": {
                        k: v
                        for k, v in step_data.items()
                        if k
                        not in [
                            "sr.no.",
                            "s.no",
                            "inputs required",
                            "input details",
                            "instructions",
                            "exisiting / new",
                            "duration",
                        ]
                    },
                }
                complete_procedures["complete_procedure_steps"].append(complete_step)

            llm_data["complete_procedure_data"].append(complete_procedures)

        return json.dumps(llm_data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error formatting comprehensive data: {e}"
