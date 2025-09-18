"""
Enhanced data processing functions for extracting and formatting rule-specific data with historical analysis.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from ..context_retriever import parse_rule_id


def extract_rule_specific_data(
    structured_data: Dict[str, Any], query: str
) -> Dict[str, Any]:
    """Extract and filter rule-specific data from structured context with enhanced analysis."""
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
        "historical_analysis": {},  # New: Historical pattern analysis
        "performance_metrics": {},  # New: Performance calculations
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

    # Perform historical analysis
    filtered_data["historical_analysis"] = analyze_historical_patterns(
        filtered_data["tracker_records"], rule_id
    )

    # Calculate performance metrics
    filtered_data["performance_metrics"] = calculate_performance_metrics(
        filtered_data["tracker_records"], rule_id
    )

    return filtered_data


def analyze_historical_patterns(
    tracker_records: List[Dict[str, Any]], rule_id: str
) -> Dict[str, Any]:
    """Analyze historical patterns from tracker records."""
    if not tracker_records:
        return {"status": "no_data", "message": "No historical data available"}

    patterns = {
        "incident_trends": {},
        "time_patterns": {},
        "user_patterns": {},
        "resolution_patterns": {},
        "classification_patterns": {},
        "recent_incidents": [],
    }

    # Collect data for analysis
    dates = []
    times = []
    engineers = []
    statuses = []
    classifications = []
    mttr_values = []
    priorities = []
    recent_incidents_data = []

    for record in tracker_records:
        tracker_data = record.get("tracker_data", {})

        # Date analysis
        date_str = tracker_data.get("date")
        if date_str:
            dates.append(date_str)

        # Time pattern analysis
        reported_time = tracker_data.get("reported time stamp")
        if reported_time:
            times.append(reported_time)

        # Engineer analysis
        engineer = tracker_data.get("name of the shift engineer")
        if engineer:
            engineers.append(engineer)

        # Status analysis
        status = tracker_data.get("status")
        if status:
            statuses.append(status)

        # Classification analysis
        classification = tracker_data.get("false / true positive")
        if classification:
            classifications.append(classification)

        # MTTR analysis
        mttr = tracker_data.get("mttr    (mins)") or tracker_data.get("mttr (mins)")
        if mttr and str(mttr).replace(".", "").isdigit():
            mttr_values.append(float(mttr))

        # Priority analysis
        priority = tracker_data.get("priority")
        if priority:
            priorities.append(priority)

        # Recent incidents (last 5)
        incident_data = {
            "incident_number": tracker_data.get("incidnet no #")
            or tracker_data.get("incident_no"),
            "date": date_str,
            "status": status,
            "classification": classification,
            "mttr": mttr,
            "engineer": engineer,
            "resolver_comments": tracker_data.get("resolver comments", "")[:200],
        }
        recent_incidents_data.append(incident_data)

    # Analyze patterns
    if dates:
        patterns["incident_trends"]["total_incidents"] = len(dates)
        patterns["incident_trends"]["date_distribution"] = dict(Counter(dates))

    if times:
        # Extract hour from timestamps for time pattern analysis
        hours = []
        for time_str in times:
            try:
                # Try different time formats
                for fmt in ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"]:
                    try:
                        dt = datetime.strptime(str(time_str).split()[0], fmt)
                        hours.append(dt.hour)
                        break
                    except ValueError:
                        continue
            except:
                continue

        if hours:
            patterns["time_patterns"]["peak_hours"] = dict(Counter(hours))
            patterns["time_patterns"]["most_common_hour"] = (
                Counter(hours).most_common(1)[0][0] if hours else None
            )

    if engineers:
        patterns["user_patterns"]["engineer_distribution"] = dict(Counter(engineers))
        patterns["user_patterns"]["most_active_engineer"] = (
            Counter(engineers).most_common(1)[0][0] if engineers else None
        )

    if statuses:
        patterns["resolution_patterns"]["status_distribution"] = dict(Counter(statuses))
        closed_count = statuses.count("Closed") + statuses.count("closed")
        patterns["resolution_patterns"]["closure_rate"] = (
            (closed_count / len(statuses)) * 100 if statuses else 0
        )

    if classifications:
        patterns["classification_patterns"]["classification_distribution"] = dict(
            Counter(classifications)
        )
        false_positive_count = sum(
            1 for c in classifications if "false" in str(c).lower()
        )
        patterns["classification_patterns"]["false_positive_rate"] = (
            (false_positive_count / len(classifications)) * 100
            if classifications
            else 0
        )

    # Sort recent incidents by date (most recent first)
    patterns["recent_incidents"] = sorted(
        recent_incidents_data, key=lambda x: x.get("date", ""), reverse=True
    )[:5]

    patterns["analysis_summary"] = {
        "total_analyzed": len(tracker_records),
        "has_sufficient_data": len(tracker_records) >= 3,
        "analysis_confidence": (
            "high"
            if len(tracker_records) >= 10
            else "medium" if len(tracker_records) >= 5 else "low"
        ),
    }

    return patterns


def calculate_performance_metrics(
    tracker_records: List[Dict[str, Any]], rule_id: str
) -> Dict[str, Any]:
    """Calculate performance metrics from tracker records."""
    if not tracker_records:
        return {"status": "no_data", "message": "No performance data available"}

    metrics = {
        "response_metrics": {},
        "resolution_metrics": {},
        "sla_metrics": {},
        "quality_metrics": {},
    }

    # Collect performance data
    mttd_values = []
    mttr_values = []
    sla_breaches = 0
    total_sla_incidents = 0
    quality_audits = []

    for record in tracker_records:
        tracker_data = record.get("tracker_data", {})

        # MTTD (Mean Time to Detect) analysis
        mttd = tracker_data.get("mttd (mins)")
        if mttd and str(mttd).replace(".", "").isdigit():
            mttd_values.append(float(mttd))

        # MTTR (Mean Time to Resolve) analysis
        mttr = tracker_data.get("mttr    (mins)") or tracker_data.get("mttr (mins)")
        if mttr and str(mttr).replace(".", "").isdigit():
            mttr_values.append(float(mttr))

        # SLA analysis
        time_to_breach = tracker_data.get("time to breach sla")
        if time_to_breach:
            total_sla_incidents += 1
            if str(time_to_breach).lower() in ["breach", "breached", "exceeded"]:
                sla_breaches += 1

        # Quality analysis
        quality_audit = tracker_data.get("quality audit")
        if quality_audit:
            quality_audits.append(quality_audit)

    # Calculate metrics
    if mttd_values:
        metrics["response_metrics"]["average_mttd"] = sum(mttd_values) / len(
            mttd_values
        )
        metrics["response_metrics"]["min_mttd"] = min(mttd_values)
        metrics["response_metrics"]["max_mttd"] = max(mttd_values)

    if mttr_values:
        metrics["resolution_metrics"]["average_mttr"] = sum(mttr_values) / len(
            mttr_values
        )
        metrics["resolution_metrics"]["min_mttr"] = min(mttr_values)
        metrics["resolution_metrics"]["max_mttr"] = max(mttr_values)
        metrics["resolution_metrics"]["mttr_trend"] = (
            "improving"
            if len(mttr_values) >= 5 and mttr_values[-3:] < mttr_values[:3]
            else "stable"
        )

    if total_sla_incidents > 0:
        metrics["sla_metrics"]["sla_compliance_rate"] = (
            (total_sla_incidents - sla_breaches) / total_sla_incidents
        ) * 100
        metrics["sla_metrics"]["breach_count"] = sla_breaches
        metrics["sla_metrics"]["total_sla_incidents"] = total_sla_incidents

    if quality_audits:
        passed_audits = sum(
            1
            for qa in quality_audits
            if "pass" in str(qa).lower() or "good" in str(qa).lower()
        )
        metrics["quality_metrics"]["quality_score"] = (
            passed_audits / len(quality_audits)
        ) * 100
        metrics["quality_metrics"]["total_audits"] = len(quality_audits)

    metrics["calculation_summary"] = {
        "incidents_analyzed": len(tracker_records),
        "has_performance_data": bool(mttd_values or mttr_values),
        "data_completeness": (
            "high"
            if len(mttr_values) >= 5
            else "medium" if len(mttr_values) >= 3 else "low"
        ),
    }

    return metrics


def format_json_for_llm(filtered_data: Dict[str, Any]) -> str:
    """Format filtered data as comprehensive JSON for LLM consumption with enhanced analysis."""
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
            "historical_analysis": filtered_data.get("historical_analysis", {}),  # New
            "performance_metrics": filtered_data.get("performance_metrics", {}),  # New
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


def get_alert_category(alert_name: str, rule_details: str = "") -> str:
    """Categorize alert based on name and rule details."""
    from .config import ALERT_CATEGORIES

    combined_text = f"{alert_name} {rule_details}".lower()

    for category, keywords in ALERT_CATEGORIES.items():
        if any(keyword in combined_text for keyword in keywords):
            return category

    return "general"


def extract_investigation_insights(
    tracker_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract investigation insights and lessons learned from tracker records."""
    insights = {
        "common_resolution_methods": [],
        "frequent_false_positive_causes": [],
        "escalation_patterns": [],
        "investigation_techniques": [],
    }

    resolution_methods = []
    false_positive_reasons = []
    escalations = []
    techniques = []

    for record in tracker_records:
        tracker_data = record.get("tracker_data", "")

        if isinstance(tracker_data, dict):
            # Resolution methods
            resolver_comments = tracker_data.get("resolver comments", "")
            if resolver_comments:
                resolution_methods.append(resolver_comments)

            # False positive causes
            fp_reason = tracker_data.get("why false positive", "")
            if fp_reason:
                false_positive_reasons.append(fp_reason)

            # Escalation patterns
            escalated_to = tracker_data.get("escalated to", "")
            if escalated_to:
                escalations.append(escalated_to)

            # Investigation techniques
            triaging_steps = tracker_data.get("triaging steps", "")
            if triaging_steps:
                techniques.append(triaging_steps)

    # Analyze patterns
    if resolution_methods:
        # Find common phrases in resolution methods
        all_words = " ".join(resolution_methods).lower().split()
        common_words = [
            word for word, count in Counter(all_words).most_common(10) if count > 1
        ]
        insights["common_resolution_methods"] = common_words[:5]

    if false_positive_reasons:
        insights["frequent_false_positive_causes"] = list(set(false_positive_reasons))[
            :5
        ]

    if escalations:
        insights["escalation_patterns"] = dict(Counter(escalations))

    if techniques:
        # Extract common investigation steps
        common_techniques = []
        for technique in techniques:
            if len(technique) > 20:  # Only meaningful techniques
                common_techniques.append(technique[:200])  # Truncate for readability
        insights["investigation_techniques"] = common_techniques[:3]

    return insights