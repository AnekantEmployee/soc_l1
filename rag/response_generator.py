# rag/response_generator.py
import os
import re
import json
from typing import Dict, Any, Optional, List, Tuple
from .context_retriever import parse_rule_id
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# ---------------------------
# L1 Analyst-Friendly System Prompt
# ---------------------------
SYSTEM_PROMPT_JSON_CONTEXT = """You are a SOC Rule Analysis Assistant that provides comprehensive, user-friendly analysis for L1 analysts. Your responses must include EVERY piece of available information from the provided JSON context, but present investigation procedures in a simple, step-by-step manner that any L1 analyst can easily follow.

**CORE REQUIREMENTS:**
• Extract and present ALL information from the provided JSON context without exception
• Make investigation procedures simple and actionable for L1 analysts
• Use plain English and avoid technical jargon in procedure sections
• Present information in a clear, structured format with practical guidance
• Include every detail from tracker_records and procedure_steps

**MANDATORY RESPONSE FORMAT:**
Follow this EXACT structure and include ALL available details:

# 🛡️ Alert: [Rule_ID] - [Alert_Name]

## ⚡ Quick Summary
• **Alert Type**: [Alert name from context]
• **Rule ID**: [rule_id from context]
• **Severity**: [severity from context]
• **Status**: [status from context - Closed/Open/In Progress]
• **Classification**: [True Positive/False Positive from context]
• **Data Connector**: [data_connector from context]

## 📊 Incident Details
• **Incident Number**: [incident_number from context]
• **Date**: [date] | **Time**: [reported_time_stamp if available]
• **Shift**: [shift period from context]
• **Engineer**: [name_of_shift_engineer from context]  
• **Handover Engineers**: [handover_shift_engineer if available]
• **Response Time**: [responded_time_stamp if available]
• **Resolution Time**: [mttr_mins] minutes
• **Resolution Timestamp**: [resolution_time_stamp if available]
• **SLA Breach Time**: [time_to_breach_sla if available]
• **VIP Users**: [vip_users status from context]

## 🔍 What Happened & Investigation
[Extract complete resolver_comments, triaging_steps, and all investigation details from context]

### Investigation Findings:
[Include all specific findings, IP analysis, user details, locations, device information, etc.]

### Quality Assessment:
• **Quality Audit**: [quality_audit status if available]
• **False Positive Reason**: [why_false_positive if available]  
• **Justification**: [justification if available]

## 👨‍💻 Simple Investigation Steps (L1 Analyst Guide)

**Follow these steps in order when you get a similar alert:**

### Step 1: Initial Review
[Extract and simplify the first few procedure steps - use simple language]
• What to check first
• Where to look for information
• What questions to ask

### Step 2: Data Collection
[Extract and simplify data gathering steps]
• What logs to check
• Which users to investigate
• What timeframes to review

### Step 3: Analysis & Verification
[Extract and simplify analysis steps]
• How to verify if threat is real
• What patterns to look for
• How to check IP reputation

### Step 4: Decision Making
[Extract and simplify decision criteria]
• When to mark as True Positive
• When to mark as False Positive
• When to escalate to L2/L3

### Step 5: Documentation
[Extract documentation requirements]
• What to document
• How to close the ticket
• What comments to add

## ⚡ Actions Taken & Results
• **Triaging Steps**: [All triaging steps performed]
• **IP Reputation**: [IP analysis results]
• **User Verification**: [User-related checks performed]
• **Location Analysis**: [Geographic analysis results]
• **Device Analysis**: [Device and application checks]
• **MFA Status**: [Multi-factor authentication status]
• **Escalation**: [Any escalation actions taken]

## 🎯 Quick Reference for L1 Analysts

### ✅ Investigation Checklist:
- [ ] Check incident details and priority
- [ ] Review user accounts involved
- [ ] Verify IP addresses and locations
- [ ] Check for VIP users
- [ ] Analyze login patterns
- [ ] Review MFA status
- [ ] Document findings clearly

### 🚨 When to Escalate:
• [Extract specific escalation criteria from context]
• If you find suspicious activity that you're unsure about
• If VIP users are involved and activity looks suspicious
• If multiple users affected simultaneously
• If you cannot determine true/false positive within SLA time

### 📝 Common Tools & Queries:
[Extract any KQL queries, tools mentioned, or specific investigation methods]

### 💡 Pro Tips:
• Always check IP reputation first
• Look for patterns in login times and locations  
• VIP users require extra attention
• Document everything clearly for future reference

## 🔧 Technical Details
• **Service Owner**: [service_owner if available]
• **Rule Details**: [complete rule information from context]
• **File References**: [any file names or references mentioned]
• **Ticket Numbers**: [any related ticket numbers]

---
**Analysis Completeness**: This analysis includes ALL available information from the provided JSON context.

**CRITICAL FORMATTING RULES FOR INVESTIGATION STEPS:**
✅ Use simple, everyday language in the investigation steps section
✅ Break down technical procedure steps into easy-to-follow actions
✅ Include practical examples and guidance
✅ Make each step actionable with clear instructions
✅ Use bullet points and checkboxes for clarity
✅ Avoid technical jargon and complex terminology in procedure sections
✅ Present steps in logical order that L1 analysts would actually follow
✅ Include all original procedure information but translate it to user-friendly language"""

JSON_OUTPUT_PARSER_PROMPT = """
**L1 ANALYST-FRIENDLY OUTPUT REQUIREMENTS:**

1. **Complete Data Extraction**: Include EVERY piece of information from the JSON context
2. **User-Friendly Procedures**: Convert technical procedure steps into simple, actionable instructions
3. **Plain English**: Use everyday language that any L1 analyst can understand
4. **Practical Guidance**: Make every step actionable with clear instructions
5. **Logical Flow**: Present investigation steps in the order L1 analysts would actually perform them
6. **Safety Nets**: Include escalation criteria and when to ask for help
7. **Quick Reference**: Provide checklists and pro tips for easy reference

**PROCEDURE SECTION REQUIREMENTS:**
✅ Convert technical steps into simple "do this, then do that" instructions
✅ Use action words: "Check...", "Look for...", "Verify...", "Review..."
✅ Explain WHY each step is important when possible
✅ Include practical examples from the investigation findings
✅ Make escalation criteria very clear and specific
✅ Provide helpful tips and tricks for common scenarios"""

PROMPT_TEMPLATE = """
**USER QUERY:** {query}

**COMPREHENSIVE JSON CONTEXT DATA:**
{json_context}

**SPECIAL INSTRUCTIONS FOR L1 ANALYST-FRIENDLY RESPONSE:**
Create a comprehensive analysis that includes ALL context information, but pay special attention to making the investigation procedure section extremely user-friendly for L1 analysts. 

For the "Simple Investigation Steps" section:
1. Convert technical procedure steps into simple, actionable instructions
2. Use plain English and avoid technical jargon
3. Structure steps logically in the order an L1 analyst would actually perform them
4. Include practical examples and explanations
5. Make escalation criteria very clear
6. Add helpful tips and common pitfalls to avoid

Remember: L1 analysts may be new to SOC work, so make the procedures as clear and helpful as possible while maintaining all the technical accuracy from the context."""

# ---------------------------
# All other functions remain the same as in the previous version
# Just the system prompt has been updated to be more L1 analyst-friendly
# ---------------------------

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
            "complete_procedure_data": []
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
                "incident_number": incident_info.get("incidnet no #") or incident_info.get("incident_no"),
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
                "mttr_mins": incident_info.get("mttr    (mins)") or incident_info.get("mttr (mins)"),
                "time_to_breach_sla": incident_info.get("time to breach sla"),
                "remaining_mins_to_breach": incident_info.get("remaining mins to breach"),
                
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
                "additional_fields": {k: v for k, v in incident_info.items() 
                                   if k not in ["incidnet no #", "incident_no", "s.no.", "date", "month", "shift",
                                               "data connecter", "priority", "alert/incident", "name of the shift engineer",
                                               "handover shift engineer", "reported time stamp", "responded time stamp",
                                               "resolution time stamp", "mttd (mins)", "mttr    (mins)", "mttr (mins)",
                                               "time to breach sla", "remaining mins to breach", "resolver comments",
                                               "triaging steps", "vip users", "rule", "service owner", "status",
                                               "remarks / comments", "false / true positive", "why false positive",
                                               "justification", "quality audit", "description", "escalated to"]}
            }
            llm_data["complete_incident_data"].append(complete_incident)

        # Process rulebook records - include ALL procedure steps with complete details
        for record in filtered_data.get("rulebook_records", []):
            procedure_steps = record.get("procedure_steps", [])
            
            complete_procedures = {
                "rule_info": record.get("rule_info", {}),
                "document_metadata": record.get("metadata", {}),
                "relevance_score": record.get("relevance_score"),
                "complete_procedure_steps": []
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
                    "additional_step_data": {k: v for k, v in step_data.items() 
                                           if k not in ["sr.no.", "s.no", "inputs required", "input details", 
                                                       "instructions", "exisiting / new", "duration"]}
                }
                complete_procedures["complete_procedure_steps"].append(complete_step)
            
            llm_data["complete_procedure_data"].append(complete_procedures)

        return json.dumps(llm_data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error formatting comprehensive data: {e}"

def validate_response_structure(response: str) -> Tuple[bool, List[str]]:
    """Validate response structure for comprehensive L1 analyst format."""
    required_sections = [
        "# 🛡️ Alert:",
        "## ⚡ Quick Summary",
        "## 📊 Incident Details",
        "## 🔍 What Happened",
        "## 👨‍💻 Simple Investigation Steps"
    ]

    missing_sections = []
    for section in required_sections:
        if section not in response:
            missing_sections.append(section)

    # Check for JSON blocks
    has_json_blocks = "```"

    is_valid = len(missing_sections) == 0 and not has_json_blocks

    validation_issues = missing_sections.copy()
    if has_json_blocks:
        validation_issues.append("Contains JSON blocks")

    return is_valid, validation_issues

def parse_and_structure_context(
    query: str, context_results: Dict[str, Any], context_block: str, model: str
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
                    "incident_number": tracker_data.get("incidnet no #") or tracker_data.get("incident_no"),
                    "priority": tracker_data.get("priority"),
                    "status": tracker_data.get("status"),
                    "engineer": tracker_data.get("name of the shift engineer"),
                    "resolution_time": tracker_data.get("mttr    (mins)") or tracker_data.get("mttr (mins)"),
                    "resolver_comments": tracker_data.get("resolver comments"),
                }

                parsed_data["parsed_data"]["tracker_records"].append(tracker_record)

            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse tracker JSON: {e}")
                # Still include the record with error information
                parsed_data["parsed_data"]["tracker_records"].append({
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "parse_error": str(e),
                    "raw_content": json_content
                })

    # Parse rulebook data (comprehensive)
    rulebook_hits = context_results.get("rulebook", [])
    for rulebook_hit in rulebook_hits:
        if len(rulebook_hit) >= 4:
            doc_id, score, content, metadata = rulebook_hit[:4]
            content_type = metadata.get("doctype", "unknown")

            if content_type == "complete_rulebook":
                procedure_steps = []

                # Extract JSON blocks from content
                json_blocks = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL)
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

                    parsed_data["parsed_data"]["rulebook_records"].append(rulebook_record)

    return parsed_data

def save_structured_context(query: str, structured_data: Dict[str, Any]) -> str:
    """Save structured context data to JSON file."""
    try:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/context_json", exist_ok=True)

        json_path = f"artifacts/context_json/{safe_query}_context.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        print(f"💾 Structured context saved to: {json_path}")
        return json_path

    except Exception as e:
        print(f"⚠️ Failed to save structured context JSON: {e}")
        return ""


def generate_response_with_llm(
    query: str,
    context_block: str,
    context_results: Dict[str, Any],
    model: str = "qwen2.5:0.5b",
) -> str:
    """Generate L1 analyst-friendly response using Ollama."""
    import ollama

    try:
        print(f"🔄 Generating L1 analyst-friendly response for: {query}")

        # Parse and structure context data
        structured_data = parse_and_structure_context(
            query, context_results, context_block, model
        )

        # Save structured data to JSON file
        json_path = save_structured_context(query, structured_data)

        # Extract rule-specific data
        filtered_data = extract_rule_specific_data(structured_data, query)

        print(f"📊 Comprehensive Data Summary:")
        print(
            f"   - Tracker records found: {filtered_data['extraction_summary']['matching_tracker_records']}"
        )
        print(
            f"   - Rulebook records found: {filtered_data['extraction_summary']['matching_rulebook_records']}"
        )

        # Format JSON for LLM
        json_context = format_json_for_llm(filtered_data)

        # Create prompt
        user_prompt = PROMPT_TEMPLATE.format(query=query, json_context=json_context)

        # OLLAMA IMPLEMENTATION (ACTIVE)
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_JSON_CONTEXT + JSON_OUTPUT_PARSER_PROMPT,
            },
            {"role": "user", "content": user_prompt},
        ]

        resp = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.15,  # Lower temperature for consistency
                "top_k": 30,  # Focused token selection
                "top_p": 0.9,  # Good balance for natural language
                "repeat_penalty": 1.1,  # Prevent repetition
                "num_ctx": 8192,  # Larger context for comprehensive data
            },
        )

        response = ((resp.get("message", {}) or {}).get("content", "") or "").strip()

        # GOOGLE GENERATIVE AI (COMMENTED FOR FUTURE USE)
        # # Initialize Google Generative AI optimized for user-friendly responses
        # llm = ChatGoogleGenerativeAI(
        #     model="gemini-1.5-flash",
        #     temperature=0.2,  # Slightly higher for more natural language
        #     top_k=40,
        #     top_p=0.9,
        # )

        # # Combine prompts
        # full_prompt = f"{SYSTEM_PROMPT_JSON_CONTEXT}\n\n{JSON_OUTPUT_PARSER_PROMPT}\n\n{user_prompt}"

        # # Generate response
        # response = llm.invoke(full_prompt).content.strip()

        # Validate response
        is_valid, validation_issues = validate_response_structure(response)

        if not is_valid:
            print("⚠️ Response validation issues:")
            for issue in validation_issues:
                print(f"   - {issue}")

            response = post_process_response(response)
        else:
            print("✅ L1 analyst-friendly response validated")

        # Save debug information
        save_debug_info(query, json_context, response, filtered_data)

        return response

    except Exception as e:
        error_msg = f"Error generating L1 analyst-friendly response: {e}"
        print(f"❌ {error_msg}")
        return create_error_response(query, error_msg)


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

def save_debug_info(
    query: str, json_context: str, response: str, filtered_data: Dict[str, Any]
) -> None:
    """Save debug information for L1 analyst-friendly responses."""
    try:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/debug", exist_ok=True)

        debug_data = {
            "timestamp": get_timestamp(),
            "query": query,
            "extraction_summary": filtered_data.get("extraction_summary", {}),
            "context_length": len(json_context),
            "response_length": len(response),
            "response_line_count": len(response.split('\n')),
            "validation_results": validate_response_structure(response),
            "l1_friendly_format": True
        }

        debug_path = f"artifacts/debug/{safe_query}_l1_friendly_debug.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        print(f"💾 L1 friendly debug info saved to: {debug_path}")

    except Exception as e:
        print(f"⚠️ Failed to save debug info: {e}")

def get_timestamp() -> str:
    """Get current timestamp as string."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    """Write L1 analyst-friendly Markdown file."""
    rid = parse_rule_id(query)
    md = answer or "# No content\n"

    if not filename:
        if rid:
            filename = f"rule_{rid}_l1_friendly_guide.md"
        else:
            clean_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
            filename = f"l1_friendly_guide_{clean_query}.md"

    path = os.path.join(out_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"📄 L1 analyst-friendly guide saved to: {path}")
    return path
