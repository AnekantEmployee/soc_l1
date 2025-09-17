"""
Refactored response generator with model selection capability.
"""

import ollama
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from .response_utils.config import (
    USE_GEMINI,
    OLLAMA_MODEL,
    OLLAMA_OPTIONS,
    GEMINI_MODEL,
    GEMINI_OPTIONS,
)
from .response_utils.prompts import (
    SYSTEM_PROMPT_JSON_CONTEXT,
    JSON_OUTPUT_PARSER_PROMPT,
    PROMPT_TEMPLATE,
)
from .response_utils.utils import (
    save_structured_context,
    validate_response_structure,
    post_process_response,
    create_error_response,
    parse_and_structure_context,
)
from .response_utils.data_processor import (
    extract_rule_specific_data,
    format_json_for_llm,
)


def generate_response_with_llm(
    query: str,
    context_results: Dict[str, Any],
) -> str:
    """Generate L1 analyst-friendly response using selected model."""

    try:
        print(f"🔄 Generating L1 analyst-friendly response for: {query}")
        print(f"🤖 Using model: {'Gemini' if USE_GEMINI else 'Ollama'}")

        # Parse and structure context data
        structured_data = parse_and_structure_context(query, context_results)

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

        # Generate response based on configuration
        if USE_GEMINI:
            response = _generate_with_gemini(user_prompt)
        else:
            response = _generate_with_ollama(user_prompt)

        # Validate response
        is_valid, validation_issues = validate_response_structure(response)

        if not is_valid:
            print("⚠️ Response validation issues:")
            for issue in validation_issues:
                print(f"   - {issue}")
            response = post_process_response(response)
        else:
            print("✅ L1 analyst-friendly response validated")

        return response

    except Exception as e:
        error_msg = f"Error generating L1 analyst-friendly response: {e}"
        print(f"❌ {error_msg}")
        return create_error_response(query, error_msg)


def _generate_with_gemini(user_prompt: str) -> str:
    """Generate response using Google Gemini."""
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, **GEMINI_OPTIONS)

    full_prompt = (
        f"{SYSTEM_PROMPT_JSON_CONTEXT}\n\n{JSON_OUTPUT_PARSER_PROMPT}\n\n{user_prompt}"
    )
    response = llm.invoke(full_prompt).content.strip()
    return response


def _generate_with_ollama(user_prompt: str) -> str:
    """Generate response using Ollama."""
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT_JSON_CONTEXT + JSON_OUTPUT_PARSER_PROMPT,
        },
        {"role": "user", "content": user_prompt},
    ]

    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        options=OLLAMA_OPTIONS,
    )

    response = ((resp.get("message", {}) or {}).get("content", "") or "").strip()
    return response
