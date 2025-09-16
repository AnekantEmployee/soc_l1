# rag/response_generator.py

import os
import re
import json
from typing import Dict, Any, Optional
from .context_retriever import parse_rule_id

# ---------------------------
# Enhanced System Prompts
# ---------------------------

SYSTEM_PROMPT_JSON_CONTEXT = """You are a SOC (Security Operations Center) RAG assistant specialized in cybersecurity rule analysis and incident response.

**CRITICAL INSTRUCTIONS:**
1. Use ONLY the provided JSON CONTEXT to answer questions
2. NEVER make assumptions or add information not present in the context
3. If information is not available in the context, explicitly state "Not found in provided context"
4. Focus on the specific rule requested in the query
5. Extract information from both tracker_records and rulebook_records sections

**RESPONSE STRUCTURE REQUIREMENTS:**
You MUST follow this exact structure in your response:

# Rule [Number] - [Actual Rule Name from Context]

## Key Information
- [3-5 key points about this specific rule from the context]
- [Include rule description, severity, category if available]

## Recent Incident Summary
- **Incident Number**: [from tracker_data]
- **Date**: [from tracker_data] 
- **Priority**: [from tracker_data]
- **Status**: [from tracker_data]
- **Engineer**: [from tracker_data]
- **Resolution Time**: [from tracker_data] minutes
- **Classification**: [from tracker_data]

## Investigation Findings
- [Key findings from resolver_comments or investigation details]
- [IP reputation status, locations, MFA status, etc.]

## Investigation Procedure Steps
[Extract from rulebook_records procedure_steps, format as numbered list]

## Remediation Actions
[Extract remediation steps from procedure_steps or tracker findings]

**DATA EXTRACTION RULES:**
- Extract rule_id, alert_name from extracted_rule_info
- Get incident details from tracker_data section
- Use resolver_comments for investigation findings
- Extract procedure steps from rulebook_records
- Maintain exact terminology from the source data
- If multiple incidents exist, focus on the most recent one

**FORBIDDEN:**
- Do not invent or assume any information
- Do not mix information from different rules
- Do not add procedural steps not in the context
- Do not speculate on missing information"""

JSON_OUTPUT_PARSER_PROMPT = """
**OUTPUT VALIDATION:**
Ensure your response:
1. Follows the exact markdown structure specified above
2. Uses only information from the provided JSON context
3. Includes specific data points like incident numbers, dates, times
4. Maintains professional SOC terminology
5. Clearly indicates when information is missing from context
"""

PROMPT_TEMPLATE = """
**QUERY:** {query}

**JSON CONTEXT:**
```json
{json_context}
```

**INSTRUCTION:**
Analyze the provided JSON context and generate a structured response following the exact format specified in the system prompt. Focus specifically on the rule mentioned in the query.
"""

# ---------------------------
# Enhanced Response Generation
# ---------------------------


def extract_rule_specific_data(
    structured_data: Dict[str, Any], query: str
) -> Dict[str, Any]:
    """Extract rule-specific data from structured context."""
    rule_id = parse_rule_id(query)

    # Filter data for specific rule if rule_id is found
    filtered_data = {
        "query": query,
        "target_rule_id": rule_id,
        "metadata": structured_data.get("metadata", {}),
        "tracker_records": [],
        "rulebook_records": [],
    }

    # Filter tracker records
    for record in structured_data.get("parsed_data", {}).get("tracker_records", []):
        if rule_id:
            # Check if this record matches the target rule
            extracted_rule = record.get("extracted_rule_info", {})
            if extracted_rule.get("rule_id") == rule_id:
                filtered_data["tracker_records"].append(record)
        else:
            # Include all if no specific rule requested
            filtered_data["tracker_records"].append(record)

    # Filter rulebook records
    for record in structured_data.get("parsed_data", {}).get("rulebook_records", []):
        if rule_id:
            # Check if this record matches the target rule
            rule_info = record.get("rule_info", {})
            if rule_info.get("primary_rule_id") == rule_id:
                filtered_data["rulebook_records"].append(record)
        else:
            # Include all if no specific rule requested
            filtered_data["rulebook_records"].append(record)

    return filtered_data


def format_json_for_llm(filtered_data: Dict[str, Any]) -> str:
    """Format filtered data as clean JSON string for LLM consumption."""
    try:
        return json.dumps(filtered_data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error formatting JSON: {e}"


def validate_response_structure(response: str) -> bool:
    """Validate that the response follows the required structure."""
    required_sections = [
        "# Rule",
        "## Key Information",
        "## Recent Incident Summary",
        "## Investigation Findings",
        "## Investigation Procedure Steps",
        "## Remediation Actions",
    ]

    return all(section in response for section in required_sections)


def generate_response_with_llm(
    query: str,
    context_block: str,
    context_results: Dict[str, Any],
    model: str = "qwen2.5:0.5b",
) -> str:
    """Enhanced response generation using structured JSON context."""
    import ollama

    try:
        # ✅ Parse and structure context data
        structured_data = parse_and_structure_context(
            query, context_results, context_block, model
        )

        # ✅ Save structured data to JSON file
        json_path = save_structured_context(query, structured_data)

        # ✅ Extract rule-specific data
        filtered_data = extract_rule_specific_data(structured_data, query)

        # ✅ Format JSON for LLM
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

        # ✅ Generate response with enhanced settings
        resp = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.1,
                "top_k": 10,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        )

        response = ((resp.get("message", {}) or {}).get("content", "") or "").strip()

        # ✅ Validate response structure
        if not validate_response_structure(response):
            print("⚠️ Warning: Response may not follow required structure")

        # ✅ Save debug information
        save_debug_info(query, json_context, response)

        return response

    except Exception as e:
        error_msg = f"Error generating response: {e}"
        print(f"❌ {error_msg}")
        return error_msg


def save_debug_info(query: str, json_context: str, response: str) -> None:
    """Save debug information for troubleshooting."""
    try:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/debug", exist_ok=True)

        debug_data = {
            "query": query,
            "json_context_length": len(json_context),
            "response_length": len(response),
            "has_required_structure": validate_response_structure(response),
            "response": response,
        }

        debug_path = f"artifacts/debug/{safe_query}_debug.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"⚠️ Failed to save debug info: {e}")


# ---------------------------
# Existing helper functions remain the same
# ---------------------------


def parse_and_structure_context(
    query: str, context_results: Dict[str, Any], context_block: str, model: str
) -> Dict[str, Any]:
    """Parse and structure context_results into comprehensive JSON format."""
    # [Keep existing implementation]
    parsed_data = {
        "query": query,
        "metadata": {
            "total_tracker_hits": len(context_results.get("tracker", [])),
            "total_rulebook_hits": len(context_results.get("rulebook", [])),
        },
        "parsed_data": {
            "tracker_records": [],
            "rulebook_records": [],
        },
    }

    # Parse tracker data
    tracker_hits = context_results.get("tracker", [])
    rule_ids_found = set()
    priorities = []
    statuses = []

    for tracker_hit in tracker_hits:
        if len(tracker_hit) >= 4:
            doc_id, score, json_content, metadata = tracker_hit[:4]

            try:
                # Parse the JSON content
                parsed_json = json.loads(json_content)

                # Extract tracker_data if it's nested
                if "tracker_data" in parsed_json:
                    tracker_data = parsed_json["tracker_data"]
                    extracted_rule_info = parsed_json.get("extracted_rule_info", {})
                else:
                    tracker_data = parsed_json
                    extracted_rule_info = {}

                # Collect statistics
                if "rule_id" in extracted_rule_info:
                    rule_ids_found.add(extracted_rule_info["rule_id"])
                if "priority" in tracker_data:
                    priorities.append(tracker_data["priority"])
                if "status" in tracker_data:
                    statuses.append(tracker_data["status"])

                # Create structured record
                tracker_record = {
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "tracker_data": tracker_data,
                    "extracted_rule_info": extracted_rule_info,
                    "incident_number": tracker_data.get("incidnet no #")
                    or tracker_data.get("incident_no"),
                    "priority": tracker_data.get("priority"),
                    "status": tracker_data.get("status"),
                    "rule": tracker_data.get("rule"),
                    "engineer": tracker_data.get("name of the shift engineer"),
                    "resolution_time": tracker_data.get("mttr    (mins)")
                    or tracker_data.get("mttr (mins)"),
                }

                parsed_data["parsed_data"]["tracker_records"].append(tracker_record)

            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse tracker JSON: {e}")
                parsed_data["parsed_data"]["tracker_records"].append(
                    {
                        "document_id": doc_id,
                        "relevance_score": float(score),
                        "metadata": metadata,
                        "parse_error": str(e),
                    }
                )

    # Parse rulebook data
    rulebook_hits = context_results.get("rulebook", [])
    content_types = []
    rule_procedures = []

    for rulebook_hit in rulebook_hits:
        if len(rulebook_hit) >= 4:
            doc_id, score, content, metadata = rulebook_hit[:4]

            # Determine content type
            content_type = metadata.get("doctype", "unknown")
            content_types.append(content_type)

            if content_type == "complete_rulebook":
                procedure_steps = []
                if "Row " in content and "{" in content:
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

                # Extract rule information
                rule_info = {
                    "primary_rule_id": metadata.get("primary_rule_id", ""),
                    "total_rows": metadata.get("rows", 0),
                    "is_complete": metadata.get("is_complete", False),
                    "is_direct_read": metadata.get("is_direct_read", False),
                }

                if procedure_steps:
                    rule_procedures.extend(procedure_steps)

                # Create structured record
                rulebook_record = {
                    "document_id": doc_id,
                    "relevance_score": float(score),
                    "metadata": metadata,
                    "content_type": content_type,
                    "rule_info": rule_info,
                    "procedure_steps": procedure_steps,
                    "content_length": len(content),
                }

                parsed_data["parsed_data"]["rulebook_records"].append(rulebook_record)

    return parsed_data


def save_structured_context(query: str, structured_data: Dict[str, Any]) -> str:
    """Save structured context data to JSON file."""
    try:
        # Create safe filename from query
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/context_json", exist_ok=True)
        json_path = f"artifacts/context_json/{safe_query}_context.json"

        # Save structured data to JSON file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        print(f"💾 Structured context saved to: {json_path}")
        return json_path

    except Exception as e:
        print(f"⚠️ Failed to save structured context JSON: {e}")
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
    """Write rule-focused Markdown file with dynamic rule detection."""
    rid = parse_rule_id(query)

    md = answer or "# No content\n"

    if not filename:
        if rid:
            filename = f"rule_{rid}.md"
        else:
            # Clean query for filename
            clean_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
            filename = f"answer_{clean_query}.md"

    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)

    return path
