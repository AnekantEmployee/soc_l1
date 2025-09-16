# rag/response_generator.py

import os
import re
from typing import Dict, Any
from .context_retriever import parse_rule_id

# ---------------------------
# Enhanced Prompts and LLM call
# ---------------------------

SYSTEM_PROMPT_DUAL = """You are a SOC RAG assistant specialized in cybersecurity rule analysis.

Use ONLY the provided CONTEXT to answer questions about security rules and incidents.

CRITICAL RULES:
- When asked about a specific Rule number (e.g., "Rule 2", "Rule 014"), focus ONLY on that exact rule
- Use TRACKER section for operational facts: incident counts, statuses, times, engineers, resolution details
- Use RULEBOOK section for procedures, investigation steps, and remediation actions
- If a Rule ID is specified, prioritize information from that exact rule only
- Never mix information from different rules unless explicitly asked for comparison
- If information is not in context, state 'Not found in provided context'
- Extract rule names and descriptions from the actual data, don't assume

Output format:
# Rule [Number] - [Actual Name from Data]

## Key Information
- 3-5 key points about this specific rule from the provided context

## Tracker Facts
- Operational data from incidents (only if available in context)

## Investigation Procedures
- Step-by-step procedures from rulebook (only for the requested rule)

## Remediation Steps
- Specific remediation actions for this rule from the provided context
"""


def parse_and_structure_context(
    query: str, context_results: Dict[str, Any], context_block: str, model: str
) -> Dict[str, Any]:
    """Parse and structure context_results into comprehensive JSON format."""
    from datetime import datetime
    import json
    import re

    parsed_data = {
        "query": query,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": model,
        "metadata": {
            "total_tracker_hits": len(context_results.get("tracker", [])),
            "total_rulebook_hits": len(context_results.get("rulebook", [])),
            "rule_id": context_results.get("class", {}).get("rule_id", ""),
            "confidence": context_results.get("class", {}).get("confidence", ""),
            "is_exact_rule": context_results.get("class", {}).get(
                "is_exact_rule", False
            ),
            "about_rule": context_results.get("class", {}).get("about_rule", False),
            "context_text_length": len(context_block),
        },
        "parsed_data": {
            "tracker_records": [],
            "rulebook_records": [],
            "query_classification": context_results.get("class", {}),
        },
        "statistics": {"tracker_stats": {}, "rulebook_stats": {}, "overall_stats": {}},
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
                # Add as raw content if JSON parsing fails
                parsed_data["parsed_data"]["tracker_records"].append(
                    {
                        "document_id": doc_id,
                        "relevance_score": float(score),
                        "metadata": metadata,
                        "raw_content": json_content,
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

            # Extract procedural steps if it's a complete rulebook
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
                "raw_content": (
                    content
                    if len(content) < 5000
                    else content[:5000] + "...[TRUNCATED]"
                ),
            }

            parsed_data["parsed_data"]["rulebook_records"].append(rulebook_record)

    # Generate statistics
    parsed_data["statistics"] = {
        "tracker_stats": {
            "total_incidents": len(tracker_hits),
            "unique_rules": len(rule_ids_found),
            "rules_found": list(rule_ids_found),
            "priorities": list(set(priorities)),
            "statuses": list(set(statuses)),
            "priority_distribution": {p: priorities.count(p) for p in set(priorities)},
        },
        "rulebook_stats": {
            "total_documents": len(rulebook_hits),
            "content_types": list(set(content_types)),
            "total_procedure_steps": len(rule_procedures),
            "complete_rulebooks": len(
                [
                    r
                    for r in parsed_data["parsed_data"]["rulebook_records"]
                    if r["rule_info"]["is_complete"]
                ]
            ),
            "direct_file_reads": len(
                [
                    r
                    for r in parsed_data["parsed_data"]["rulebook_records"]
                    if r["rule_info"]["is_direct_read"]
                ]
            ),
        },
        "overall_stats": {
            "total_documents": len(tracker_hits) + len(rulebook_hits),
            "query_classification": context_results.get("class", {}),
            "processing_successful": True,
        },
    }

    return parsed_data


def save_structured_context(query: str, structured_data: Dict[str, Any]) -> str:
    """Save structured context data to JSON file."""
    import os
    import json
    import re

    try:
        # Create safe filename from query
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs("artifacts/context_json", exist_ok=True)
        json_path = f"artifacts/context_json/{safe_query}_context.json"

        # Save structured data to JSON file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        print(f"💾 Structured context saved to: {json_path}")
        print(
            f"📊 Parsed: {structured_data['metadata']['total_tracker_hits']} tracker + {structured_data['metadata']['total_rulebook_hits']} rulebook hits"
        )
        print(
            f"🔍 Found {structured_data['statistics']['tracker_stats']['total_incidents']} incidents, {structured_data['statistics']['rulebook_stats']['total_procedure_steps']} procedure steps"
        )

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
    """Generate response using LLM with enhanced prompt and context."""
    import ollama

    # ✅ Parse and save structured context data
    try:
        # Parse the context_results into structured format
        structured_data = parse_and_structure_context(
            query, context_results, context_block, model
        )

        # Save structured data to JSON file
        save_structured_context(query, structured_data)

    except Exception as json_error:
        print(f"⚠️ Failed to process structured context: {json_error}")

    # Original LLM processing
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_DUAL},
        {"role": "user", "content": f"QUESTION:\n{query}\n\nCONTEXT:\n{context_block}"},
    ]

    try:
        resp = ollama.chat(model=model, messages=messages, options={"temperature": 0.1})
        return ((resp.get("message", {}) or {}).get("content", "") or "").strip()
    except Exception as e:
        return f"Error generating response: {e}"


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
