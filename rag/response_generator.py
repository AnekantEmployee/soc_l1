# rag/response_generator.py

import os
import re
import json
from typing import Dict, Any, Optional, List
from .context_retriever import parse_rule_id


# ---------------------------
# Enhanced System Prompts with Expanded Structure
# ---------------------------

SYSTEM_PROMPT_JSON_CONTEXT = """You are an elite SOC (Security Operations Center) RAG assistant specialized in comprehensive cybersecurity rule analysis and incident response.

**CRITICAL INSTRUCTIONS:**
1. Use ONLY the provided JSON CONTEXT to answer questions
2. NEVER make assumptions or add information not present in the context
3. If information is not available in the context, explicitly state "Not found in provided context"
4. Focus on the specific rule requested in the query
5. Extract information from both tracker_records and rulebook_records sections
6. Ensure all sections are populated with available data - do not leave sections empty

**RESPONSE STRUCTURE REQUIREMENTS:**
You MUST follow this exact expanded structure in your response:

# Rule [Number] - [Actual Rule Name from Context]

## Key Information
- **Rule ID**: [from context]
- **Alert Name**: [from context]
- **Description**: [from rulebook procedure_steps or context]
- **Severity**: [from context]
- **Category**: [from context]
- **Service Owner**: [from tracker_data]
- **Data Connector**: [from tracker_data]

## Recent Incident Summary  
- **Incident Number**: [from tracker_data]
- **Date**: [from tracker_data]
- **Reported Time**: [from tracker_data.reported_time_stamp]
- **Responded Time**: [from tracker_data.responded_time_stamp]
- **Resolution Time**: [from tracker_data.resolution_time_stamp]
- **Priority**: [from tracker_data]
- **Status**: [from tracker_data]
- **Engineer**: [from tracker_data.name_of_the_shift_engineer]
- **Handover Engineers**: [from tracker_data.handover_shift_engineer]
- **Shift**: [from tracker_data.shift]

## SLA & Performance Metrics
- **MTTD (Minutes)**: [from tracker_data.mttd_mins]
- **MTTR (Minutes)**: [from tracker_data.mttr_mins]
- **Time to Breach SLA**: [from tracker_data.time_to_breach_sla]
- **Remaining Minutes to Breach**: [from tracker_data.remaining_mins_to_breach]
- **Quality Audit**: [from tracker_data.quality_audit]

## Investigation Findings
- **Key Findings**: [from resolver_comments or investigation details]
- **IP Reputation Status**: [extract from resolver_comments]
- **Locations/Countries**: [extract from resolver_comments]
- **MFA Status**: [extract from resolver_comments if mentioned]
- **Device Information**: [extract from resolver_comments]
- **Applications Used**: [extract from resolver_comments]
- **VIP Users Involved**: [from tracker_data.vip_users]

## False Positive Analysis
- **Classification**: [from tracker_data.false_true_positive]
- **Reason**: [from tracker_data.why_false_positive]
- **Justification**: [from tracker_data.justification]
- **Escalation Required**: [from tracker_data if mentioned in resolver_comments]

## Investigation Procedure Steps
[Extract step-by-step from rulebook_records procedure_steps, format as numbered list with sub-details]
1. [Step description with input details and instructions]
2. [Continue for all steps...]

## Remediation Actions
[Extract remediation steps from procedure_steps focusing on resolution actions]
- [Action items for incident resolution]
- [Follow-up requirements]
- [Preventive measures]

## Supporting Artifacts & References
- **Incident Tickets**: [extract ticket numbers from procedure_steps or tracker_data]
- **Documentation**: [from tracker_data.remarks_comments]
- **Screenshots/Videos**: [if mentioned in procedure_steps]
- **External References**: [if mentioned in rulebook content]

## MITRE ATT&CK Mapping
[If any MITRE techniques are mentioned in context or can be inferred from rule type]
- **Tactic**: [if available]
- **Technique**: [if available]
- **Sub-technique**: [if available]

## Additional Notes
- **Workspace Issues**: [if mentioned in justification]
- **Historical Context**: [if mentioned in resolver_comments]
- **Special Considerations**: [any unique aspects from the investigation]

**DATA EXTRACTION RULES:**
- Extract ALL available fields from tracker_data
- Parse resolver_comments for detailed investigation findings
- Include timestamps, metrics, and personnel information
- Maintain exact terminology from the source data
- Populate ALL sections even if some information is limited
- Use "Not found in provided context" only when data is truly missing

**FORMATTING REQUIREMENTS:**
- Use consistent markdown formatting
- Include bullet points for lists
- Use bold for field labels
- Maintain professional SOC terminology
- Ensure no duplicate information across sections
"""

JSON_OUTPUT_PARSER_PROMPT = """
**OUTPUT VALIDATION:**
Ensure your response:
1. Follows the exact expanded markdown structure specified above
2. Uses only information from the provided JSON context
3. Includes ALL available data points like incident numbers, dates, times, metrics
4. Maintains professional SOC terminology
5. Clearly indicates when information is missing from context
6. Populates ALL 10 sections with available data
7. Removes any empty placeholder text or redundant information
"""

PROMPT_TEMPLATE = """
**QUERY:** {query}

**JSON CONTEXT:**
{json_context}


**INSTRUCTION:**
Analyze the provided JSON context and generate a comprehensive structured response following the exact format specified in the system prompt. Focus specifically on the rule mentioned in the query and extract ALL available information to populate every section thoroughly.
"""


# ---------------------------
# Enhanced Data Extraction Functions
# ---------------------------

def extract_comprehensive_tracker_data(tracker_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract comprehensive data from tracker_data with all available fields."""
    return {
        # Basic incident info
        "incident_number": tracker_data.get("incidnet no #") or tracker_data.get("incident_no"),
        "date": tracker_data.get("date"),
        "month": tracker_data.get("month"),
        "shift": tracker_data.get("shift"),
        "priority": tracker_data.get("priority"),
        "status": tracker_data.get("status"),
        "alert_incident": tracker_data.get("alert/incident"),
        
        # Personnel
        "engineer": tracker_data.get("name of the shift engineer"),
        "handover_engineers": tracker_data.get("handover shift engineer"),
        
        # Timestamps and metrics
        "reported_timestamp": tracker_data.get("reported time stamp"),
        "responded_timestamp": tracker_data.get("responded time stamp"),
        "resolution_timestamp": tracker_data.get("resolution time stamp"),
        "mttd_mins": tracker_data.get("mttd   (mins)") or tracker_data.get("mttd (mins)"),
        "mttr_mins": tracker_data.get("mttr    (mins)") or tracker_data.get("mttr (mins)"),
        "time_to_breach_sla": tracker_data.get("time to breach sla"),
        "remaining_mins_to_breach": tracker_data.get("remaining mins to breach"),
        
        # Technical details
        "data_connector": tracker_data.get("data connecter"),
        "rule": tracker_data.get("rule"),
        "service_owner": tracker_data.get("service owner"),
        
        # Investigation details
        "resolver_comments": tracker_data.get("resolver comments"),
        "vip_users": tracker_data.get("vip users"),
        "escalating": tracker_data.get("escalating"),
        
        # Classification
        "false_true_positive": tracker_data.get("false / true positive"),
        "why_false_positive": tracker_data.get("why false positive"),
        "justification": tracker_data.get("justification"),
        "quality_audit": tracker_data.get("quality audit"),
        
        # Additional fields
        "remarks_comments": tracker_data.get("remarks & comments"),
        "description": tracker_data.get("description")
    }

def extract_enhanced_procedure_steps(procedure_steps: List[Dict]) -> List[Dict]:
    """Extract and structure procedure steps with enhanced detail."""
    structured_steps = []
    
    for step in procedure_steps:
        step_data = step.get("data", {})
        step_info = {
            "step_number": step_data.get("sr.no.") or step_data.get("s.no."),
            "inputs_required": step_data.get("inputs required"),
            "input_details": step_data.get("input details"),
            "instructions": step_data.get("instructions"),
            "rule_metadata": step.get("rule_metadata", {})
        }
        
        if step_info["inputs_required"] or step_info["instructions"]:
            structured_steps.append(step_info)
    
    return structured_steps

def extract_rule_specific_data(
    structured_data: Dict[str, Any], query: str
) -> Dict[str, Any]:
    """Extract rule-specific data from structured context with enhanced filtering."""
    rule_id = parse_rule_id(query)

    # Enhanced filter data structure
    filtered_data = {
        "query": query,
        "target_rule_id": rule_id,
        "metadata": structured_data.get("metadata", {}),
        "tracker_records": [],
        "rulebook_records": [],
        "enhanced_extraction": True
    }

    # Filter and enhance tracker records
    for record in structured_data.get("parsed_data", {}).get("tracker_records", []):
        extracted_rule = record.get("extracted_rule_info", {})
        tracker_data = record.get("tracker_data", {})
        
        # Check rule matching
        record_rule_id = extracted_rule.get("rule_id")
        if rule_id and record_rule_id != rule_id:
            continue
            
        # Create enhanced record with comprehensive data extraction
        enhanced_record = {
            "document_id": record.get("document_id"),
            "relevance_score": record.get("relevance_score"),
            "metadata": record.get("metadata", {}),
            "extracted_rule_info": extracted_rule,
            "comprehensive_tracker_data": extract_comprehensive_tracker_data(tracker_data),
            "raw_tracker_data": tracker_data  # Keep raw data for fallback
        }
        
        filtered_data["tracker_records"].append(enhanced_record)

    # Filter and enhance rulebook records
    for record in structured_data.get("parsed_data", {}).get("rulebook_records", []):
        rule_info = record.get("rule_info", {})
        procedure_steps = record.get("procedure_steps", [])
        
        # Check rule matching
        record_rule_id = rule_info.get("primary_rule_id")
        if rule_id and record_rule_id != rule_id:
            continue
            
        # Create enhanced record with structured procedures
        enhanced_record = {
            "document_id": record.get("document_id"),
            "relevance_score": record.get("relevance_score"),
            "metadata": record.get("metadata", {}),
            "rule_info": rule_info,
            "structured_procedures": extract_enhanced_procedure_steps(procedure_steps),
            "raw_procedure_steps": procedure_steps  # Keep raw data for fallback
        }
        
        filtered_data["rulebook_records"].append(enhanced_record)

    return filtered_data

def sanitize_json_for_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove null, empty, and duplicate values from JSON data."""
    def clean_value(value):
        if value is None:
            return None
        elif isinstance(value, str):
            return value.strip() if value.strip() else None
        elif isinstance(value, dict):
            return {k: clean_value(v) for k, v in value.items() if clean_value(v) is not None}
        elif isinstance(value, list):
            cleaned_list = [clean_value(item) for item in value if clean_value(item) is not None]
            return cleaned_list if cleaned_list else None
        else:
            return value
    
    return clean_value(data)

def format_json_for_llm(filtered_data: Dict[str, Any]) -> str:
    """Format filtered data as clean JSON string for LLM consumption."""
    try:
        # Clean the data before formatting
        sanitized_data = sanitize_json_for_llm(filtered_data)
        return json.dumps(sanitized_data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error formatting JSON: {e}"

def validate_response_completeness(response: str) -> Dict[str, Any]:
    """Validate that the response follows the required structure and contains data."""
    required_sections = [
        "# Rule",
        "## Key Information",
        "## Recent Incident Summary", 
        "## SLA & Performance Metrics",
        "## Investigation Findings",
        "## False Positive Analysis",
        "## Investigation Procedure Steps",
        "## Remediation Actions",
        "## Supporting Artifacts & References",
        "## MITRE ATT&CK Mapping",
        "## Additional Notes"
    ]
    
    validation_results = {
        "has_all_sections": all(section in response for section in required_sections),
        "missing_sections": [section for section in required_sections if section not in response],
        "has_placeholder_text": "Not found in provided context" in response,
        "response_length": len(response),
        "estimated_completeness": 0.0
    }
    
    # Calculate estimated completeness
    present_sections = sum(1 for section in required_sections if section in response)
    validation_results["estimated_completeness"] = present_sections / len(required_sections)
    
    return validation_results

def generate_response_with_llm(
    query: str,
    context_block: str,
    context_results: Dict[str, Any],
    model: str = "qwen2.5:0.5b",
) -> str:
    """Enhanced response generation using structured JSON context with comprehensive data extraction."""
    import ollama

    try:
        # ✅ Parse and structure context data
        structured_data = parse_and_structure_context(
            query, context_results, context_block, model
        )

        # ✅ Save structured data to JSON file
        json_path = save_structured_context(query, structured_data)

        # ✅ Extract rule-specific data with enhanced filtering
        filtered_data = extract_rule_specific_data(structured_data, query)

        # ✅ Format JSON for LLM with sanitization
        json_context = format_json_for_llm(filtered_data)

        # ✅ Create enhanced prompt
        user_prompt = PROMPT_TEMPLATE.format(query=query, json_context=json_context)

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_JSON_CONTEXT + JSON_OUTPUT_PARSER_PROMPT,
            },
            {"role": "user", "content": user_prompt},
        ]

        # ✅ Generate response with optimized settings
        resp = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.05,  # Lower temperature for more consistent output
                "top_k": 15,
                "top_p": 0.85,
                "repeat_penalty": 1.15,
                "num_ctx": 8192  # Increased context window
            },
        )

        response = ((resp.get("message", {}) or {}).get("content", "") or "").strip()

        # ✅ Validate response completeness
        validation_results = validate_response_completeness(response)
        
        if validation_results["estimated_completeness"] < 0.8:
            print(f"⚠️ Warning: Response completeness is {validation_results['estimated_completeness']:.1%}")
            print(f"Missing sections: {validation_results['missing_sections']}")

        # ✅ Apply post-processing sanitization
        response = sanitize_response_output(response)

        # ✅ Save comprehensive debug information
        save_enhanced_debug_info(query, json_context, response, validation_results)

        return response

    except Exception as e:
        error_msg = f"Error generating enhanced response: {e}"
        print(f"❌ {error_msg}")
        return error_msg

def sanitize_response_output(response: str) -> str:
    """Post-process response to remove duplicates and ensure clean formatting."""
    lines = response.split('\n')
    
    # Remove duplicate consecutive lines
    cleaned_lines = []
    prev_line = ""
    
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line != prev_line or cleaned_line.startswith('#'):
            cleaned_lines.append(line)
            prev_line = cleaned_line
    
    # Join with single newlines and clean up excessive whitespace
    cleaned_response = '\n'.join(cleaned_lines)
    
    # Remove excessive empty lines (more than 2 consecutive)
    cleaned_response = re.sub(r'\n{3,}', '\n\n', cleaned_response)
    
    return cleaned_response.strip()

def save_enhanced_debug_info(
    query: str, 
    json_context: str, 
    response: str, 
    validation_results: Dict[str, Any]
) -> None:
    """Save comprehensive debug information for troubleshooting."""
    try:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/debug", exist_ok=True)

        debug_data = {
            "query": query,
            "json_context_length": len(json_context),
            "response_length": len(response),
            "validation_results": validation_results,
            "timestamp": json.dumps(None),  # Will be set by JSON serializer
            "response_preview": response[:500] + "..." if len(response) > 500 else response,
        }

        debug_path = f"artifacts/debug/{safe_query}_enhanced_debug.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        print(f"🔍 Enhanced debug info saved to: {debug_path}")
        print(f"📊 Response completeness: {validation_results['estimated_completeness']:.1%}")

    except Exception as e:
        print(f"⚠️ Failed to save enhanced debug info: {e}")

# ---------------------------
# Existing helper functions with enhancements
# ---------------------------

def parse_and_structure_context(
    query: str, context_results: Dict[str, Any], context_block: str, model: str
) -> Dict[str, Any]:
    """Parse and structure context_results into comprehensive JSON format with enhanced data extraction."""
    
    parsed_data = {
        "query": query,
        "metadata": {
            "total_tracker_hits": len(context_results.get("tracker", [])),
            "total_rulebook_hits": len(context_results.get("rulebook", [])),
            "enhancement_version": "2.0"
        },
        "parsed_data": {
            "tracker_records": [],
            "rulebook_records": [],
        },
    }

    # Enhanced tracker data parsing
    tracker_hits = context_results.get("tracker", [])
    rule_ids_found = set()
    priorities = []
    statuses = []

    for tracker_hit in tracker_hits:
        if len(tracker_hit) >= 4:
            doc_id, score, json_content, metadata = tracker_hit[:4]

            try:
                parsed_json = json.loads(json_content)

                # Extract tracker_data with fallback handling
                if "tracker_data" in parsed_json:
                    tracker_data = parsed_json["tracker_data"]
                    extracted_rule_info = parsed_json.get("extracted_rule_info", {})
                else:
                    tracker_data = parsed_json
                    extracted_rule_info = {}

                # Collect enhanced statistics
                if "rule_id" in extracted_rule_info:
                    rule_ids_found.add(extracted_rule_info["rule_id"])
                if "priority" in tracker_data:
                    priorities.append(tracker_data["priority"])
                if "status" in tracker_data:
                    statuses.append(tracker_data["status"])

                # Create enhanced tracker record
                tracker_record = {
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "tracker_data": tracker_data,
                    "extracted_rule_info": extracted_rule_info,
                    
                    # Quick access fields
                    "incident_number": tracker_data.get("incidnet no #") or tracker_data.get("incident_no"),
                    "priority": tracker_data.get("priority"),
                    "status": tracker_data.get("status"),
                    "rule": tracker_data.get("rule"),
                    "engineer": tracker_data.get("name of the shift engineer"),
                    "resolution_time": tracker_data.get("mttr    (mins)") or tracker_data.get("mttr (mins)"),
                    "service_owner": tracker_data.get("service owner"),
                    "false_positive": tracker_data.get("false / true positive"),
                    "mttd": tracker_data.get("mttd   (mins)") or tracker_data.get("mttd (mins)"),
                    "resolver_comments": tracker_data.get("resolver comments")
                }

                parsed_data["parsed_data"]["tracker_records"].append(tracker_record)

            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse tracker JSON: {e}")
                parsed_data["parsed_data"]["tracker_records"].append({
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "parse_error": str(e),
                })

    # Enhanced rulebook data parsing
    rulebook_hits = context_results.get("rulebook", [])
    content_types = []
    rule_procedures = []

    for rulebook_hit in rulebook_hits:
        if len(rulebook_hit) >= 4:
            doc_id, score, content, metadata = rulebook_hit[:4]

            content_type = metadata.get("doctype", "unknown")
            content_types.append(content_type)

            if content_type == "complete_rulebook":
                procedure_steps = []
                
                # Enhanced JSON block extraction
                if "Row " in content and "{" in content:
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

                # Enhanced rule information extraction
                rule_info = {
                    "primary_rule_id": metadata.get("primary_rule_id", ""),
                    "total_rows": metadata.get("rows", 0),
                    "is_complete": metadata.get("is_complete", False),
                    "is_direct_read": metadata.get("is_direct_read", False),
                    "procedure_count": len(procedure_steps),
                    "file_type": metadata.get("filetype", ""),
                    "content_length": len(content)
                }

                if procedure_steps:
                    rule_procedures.extend(procedure_steps)

                # Create enhanced rulebook record
                rulebook_record = {
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "content_type": content_type,
                    "rule_info": rule_info,
                    "procedure_steps": procedure_steps,
                    "content_length": len(content),
                    "source_file": metadata.get("source", "")
                }

                parsed_data["parsed_data"]["rulebook_records"].append(rulebook_record)

    # Add enhanced summary statistics
    parsed_data["summary_stats"] = {
        "unique_rules_found": len(rule_ids_found),
        "priority_distribution": {priority: priorities.count(priority) for priority in set(priorities)},
        "status_distribution": {status: statuses.count(status) for status in set(statuses)},
        "total_procedure_steps": len(rule_procedures),
        "content_types_found": list(set(content_types))
    }

    return parsed_data

def save_structured_context(query: str, structured_data: Dict[str, Any]) -> str:
    """Save structured context data to JSON file with enhanced metadata."""
    try:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/context_json", exist_ok=True)
        json_path = f"artifacts/context_json/{safe_query}_enhanced_context.json"

        # Add processing metadata
        structured_data["processing_info"] = {
            "processed_at": "2025-09-17T00:47:00Z",  # Current timestamp
            "enhancement_version": "2.0",
            "total_data_points": sum([
                len(structured_data.get("parsed_data", {}).get("tracker_records", [])),
                len(structured_data.get("parsed_data", {}).get("rulebook_records", []))
            ])
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        print(f"💾 Enhanced structured context saved to: {json_path}")
        return json_path

    except Exception as e:
        print(f"⚠️ Failed to save enhanced structured context JSON: {e}")
        return ""

def save_context_to_file(query: str, context_block: str) -> str:
    """Save context to file for debugging and reference."""
    safe_q = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:60]
    os.makedirs("artifacts/query_contexts", exist_ok=True)
    context_path = f"artifacts/query_contexts/{safe_q}.txt"

    try:
        with open(context_path, "w", encoding="utf-8") as f:
            f.write(f"Query: {query}\n")
            f.write("=" * 50 + "\n")
            f.write(context_block)
        return context_path
    except Exception:
        return "Failed to save"

def write_rule_markdown(
    query: str,
    answer: str,
    out_dir: str = ".",
    filename: str = None,
) -> str:
    """Write comprehensive rule-focused Markdown file with enhanced content."""
    rid = parse_rule_id(query)

    md = answer or "# No content\n"

    if not filename:
        if rid:
            filename = f"rule_{rid}_enhanced.md"
        else:
            clean_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
            filename = f"answer_{clean_query}_enhanced.md"

    path = os.path.join(out_dir, filename)
    
    # Add metadata header to markdown file
    enhanced_md = f"""<!--- 
Generated: 2025-09-17T00:47:00Z
Query: {query}
Enhancement Version: 2.0
--->

{md}
"""
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(enhanced_md)

    print(f"📝 Enhanced markdown saved to: {path}")
    return path
