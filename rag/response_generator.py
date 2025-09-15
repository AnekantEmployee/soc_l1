# rag/response_generator.py

import os
import re
import json
import ollama
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


def generate_response_with_llm(
    query: str, context_block: str, model: str = "qwen2.5:0.5b"
) -> str:
    """Generate response using LLM with enhanced prompt and context."""
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
