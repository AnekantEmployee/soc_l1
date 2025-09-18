"""

Enhanced response generator with external search capabilities and comprehensive analysis.

(Updated with structured sections: Alert Analysis, Investigation, Remediation, Historical Context, References)

"""

import os
import re
import json
import ollama
from typing import Dict, Any, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from .response_utils.config import (
    USE_GEMINI,
    OLLAMA_MODEL,
    OLLAMA_OPTIONS,
    GEMINI_MODEL,
    GEMINI_OPTIONS,
    ENABLE_EXTERNAL_SEARCH,
    TAVILY_API_KEY,
    MAX_SEARCH_RESULTS,
    SEARCH_QUERIES,
    SEARCH_TIMEOUT,
)
from .response_utils.prompts import (
    SYSTEM_PROMPT_JSON_CONTEXT,
    JSON_OUTPUT_PARSER_PROMPT,
    PROMPT_TEMPLATE,
    SEARCH_ENHANCED_SYSTEM_PROMPT,
)
from .response_utils.utils import (
    save_structured_context,
    validate_response_structure,
    post_process_response,
    create_error_response,
    parse_and_structure_context,
    get_timestamp,
)
from .response_utils.data_processor import (
    extract_rule_specific_data,
    format_json_for_llm,
    get_alert_category,
    extract_investigation_insights,
)
from .response_utils.external_search import EnhancedExternalSearchManager # Import the new class

# --- ExternalSearchManager replaced with EnhancedExternalSearchManager --- #
# The class definition below is no longer needed as we're importing it.
# Keeping it here as a comment for context.
# class ExternalSearchManager:
#     ...

def generate_response_with_llm(
    query: str,
    context_results: Dict[str, Any],
) -> str:
    """Generate comprehensive L1 analyst-friendly response with external search."""

    try:
        print(f"🔄 Generating comprehensive L1 analyst response for: {query}")
        print(f"🤖 Using model: {'Gemini' if USE_GEMINI else 'Ollama'}")

        # Parse and structure context data
        structured_data = parse_and_structure_context(query, context_results)

        # Save structured data to JSON file
        json_path = save_structured_context(query, structured_data)

        # Extract rule-specific data with enhanced analysis
        filtered_data = extract_rule_specific_data(structured_data, query)

        print(f"📊 Comprehensive Data Summary:")
        print(
            f"   - Tracker records found: {filtered_data['extraction_summary']['matching_tracker_records']}"
        )
        print(
            f"   - Rulebook records found: {filtered_data['extraction_summary']['matching_rulebook_records']}"
        )
        print(
            f"   - Historical analysis: {filtered_data['historical_analysis'].get('analysis_summary', {}).get('analysis_confidence', 'unknown')}"
        )

        # Extract alert information for search
        alert_name = _extract_alert_name_from_context(filtered_data)
        rule_id = filtered_data.get("target_rule_id", "")
        alert_category = get_alert_category(alert_name, rule_id)

        # Perform external search using the new enhanced manager
        search_manager = EnhancedExternalSearchManager()
        external_search_results = {}
        if alert_name:
            print(f"🔍 Searching external sources for: {alert_name}")
            external_search_results = search_manager.search_comprehensive_alert_information(
                alert_name, rule_id, alert_category
            )

        # Extract investigation insights
        investigation_insights = extract_investigation_insights(
            filtered_data.get("tracker_records", [])
        )

        # Format comprehensive JSON for LLM
        json_context = format_json_for_llm(filtered_data)

        # Create enhanced prompt with search results
        user_prompt = _create_enhanced_prompt(
            query,
            json_context,
            external_search_results,
            investigation_insights,
            alert_name,
        )

        # Generate response based on configuration
        if USE_GEMINI:
            response = _generate_with_gemini(user_prompt)
        else:
            response = _generate_with_ollama(user_prompt)

        # Validate and post-process response
        is_valid, validation_issues = validate_response_structure(response)
        
        # Check if the historical section needs to be removed
        num_tracker_records = filtered_data['extraction_summary']['matching_tracker_records']
        if num_tracker_records == 0:
            response = _remove_historical_section_if_empty(response)

        if not is_valid:
            print("⚠️ Response validation issues:")
            for issue in validation_issues:
                print(f"   - {issue}")
            response = post_process_response(response)
        else:
            print("✅ Comprehensive L1 analyst response validated")

        return response

    except Exception as e:
        error_msg = f"Error generating comprehensive L1 analyst response: {e}"
        print(f"❌ {error_msg}")
        return create_error_response(query, error_msg)


def _remove_historical_section_if_empty(response: str) -> str:
    """Removes the historical context section if no data is available."""
    
    # Find the start and end of the historical section
    start_pattern = r'## 📊 Historical Context & Tracker Analysis'
    end_pattern = r'## 🚨 Remediation & Escalation Procedures'

    # Check for the existence of the section
    if re.search(start_pattern, response, re.DOTALL):
        # Find the content between the two sections
        match = re.search(f'({start_pattern}.*?)(?={end_pattern})', response, re.DOTALL)
        if match:
            # Check if the content is empty or contains "no data" message
            content = match.group(1)
            if 'no historical data available' in content.lower() or 'insufficient data' in content.lower():
                # Remove the entire section
                response = re.sub(f'{start_pattern}.*?(?={end_pattern})', '', response, flags=re.DOTALL)
                print("📝 Removed empty historical context section.")

    return response


def _extract_alert_name_from_context(filtered_data: Dict[str, Any]) -> str:
    """Extract alert name from context data for search."""
    # Try to get alert name from tracker records
    tracker_records = filtered_data.get("tracker_records", [])
    for record in tracker_records:
        tracker_data = record.get("tracker_data", {})
        alert_name = tracker_data.get("alert/incident")
        if alert_name and len(str(alert_name).strip()) > 5:
            return str(alert_name).strip()

    # Try to get from extracted rule info
    for record in tracker_records:
        extracted_rule = record.get("extracted_rule_info", {})
        alert_name = extracted_rule.get("alert_name")
        if alert_name and len(str(alert_name).strip()) > 5:
            return str(alert_name).strip()

    # Try to get from rulebook records
    rulebook_records = filtered_data.get("rulebook_records", [])
    for record in rulebook_records:
        procedure_steps = record.get("procedure_steps", [])
        for step in procedure_steps:
            rule_metadata = step.get("rule_metadata", {})
            alert_name = rule_metadata.get("alert_name")
            if alert_name and len(str(alert_name).strip()) > 5:
                return str(alert_name).strip()

    return ""


def _create_enhanced_prompt(
    query: str,
    json_context: str,
    search_results: Dict[str, Any],
    investigation_insights: Dict[str, Any],
    alert_name: str,
) -> str:
    """Create enhanced prompt with external search results and insights."""

    # Format search results for prompt
    search_context = ""
    reference_links_md = ""

    if search_results and search_results.get("status") == "success":
        search_context = "\n**EXTERNAL SEARCH RESULTS:**\n"

        # Core search results
        for section, results in search_results.items():
            if section in ["alert_description", "investigation_guide", "false_positives", "threat_intel", "mitre_attack"]:
                if results:
                    search_context += f"\n**{section.replace('_', ' ').title()}:**\n"
                    for result in results:
                        search_context += f"- {result.get('title', '')}: {result.get('content', '')}\n"
        
        # SIEM search results
        if search_results.get("siem_queries"):
            search_context += "\n**SIEM Platform Queries:**\n"
            for platform_id, platform_data in search_results["siem_queries"].items():
                if platform_data["search_results"]:
                    search_context += f"- **{platform_data['platform_name']} ({platform_data['query_language']}):**\n"
                    for result in platform_data["search_results"]:
                        search_context += f"  - {result.get('title', '')}: {result.get('content', '')}\n"

        # Vendor documentation search results
        if search_results.get("vendor_documentation"):
            search_context += "\n**Vendor Documentation:**\n"
            for vendor_id, vendor_data in search_results["vendor_documentation"].items():
                if vendor_data["search_results"]:
                    search_context += f"- **{vendor_data['vendor_name']}:**\n"
                    for result in vendor_data["search_results"]:
                        search_context += f"  - {result.get('title', '')}: {result.get('content', '')}\n"

        # Format collected links for the end of the report
        if search_results.get("reference_links"):
            reference_links_md = "\nPre-collected Reference Links:\n"
            for link in search_results["reference_links"]:
                reference_links_md += f"- {link['url']} ({link['source']})\n"


    # Format investigation insights
    insights_context = ""
    if investigation_insights:
        insights_context = "\n**INVESTIGATION INSIGHTS FROM HISTORICAL DATA:**\n"
        if investigation_insights.get("common_resolution_methods"):
            insights_context += f"**Common Resolution Methods:** {', '.join(investigation_insights['common_resolution_methods'])}\n"
        if investigation_insights.get("frequent_false_positive_causes"):
            insights_context += f"**Frequent False Positive Causes:** {', '.join(investigation_insights['frequent_false_positive_causes'])}\n"
        if investigation_insights.get("escalation_patterns"):
            insights_context += f"**Escalation Patterns:** {investigation_insights['escalation_patterns']}\n"


    # --- FINAL PROMPT STRUCTURE --- #
    enhanced_prompt = f"""
**USER QUERY:** {query}

**COMPREHENSIVE JSON CONTEXT DATA:**
{json_context}

{search_context}

{insights_context}

**ALERT CATEGORIZATION:** {get_alert_category(alert_name)}

**CRITICAL INSTRUCTIONS:**

Create a comprehensive L1 analyst report following this EXACT ORDER AND STRUCTURE:

# 🛡️ Alert: [Rule_ID] - [Alert_Name]

## 📖 Detailed Alert Description & Context

**Alert Overview:**
[Comprehensive, educational description of the alert, its purpose, and business impact. Use external search results heavily here.]

**Attack Vector & Techniques:**
[Include MITRE ATT&CK mapping with IDs, common attack patterns, and threat actor tactics. Use external search.]

**Technical Details:**
[Explain the rule's detection logic, data sources, false positive causes, and true positive indicators. Use a mix of external search and rulebook context.]

## 👨‍💻 Step-by-Step Investigation Analysis

**Follow these steps in order when you get a similar alert:**

[Break down the investigation process into clear, actionable steps. Use the rulebook context and historical insights. Include time estimates for each phase (e.g., Triage: 5 mins, Data Collection: 10 mins). Focus on L1-friendly language.]

## 📊 Historical Context & Tracker Analysis

**Current Incident Details:**
[Extract and present ALL current incident details from the JSON context here, like incident number, date, engineer, etc.]

**Investigation Findings:**
[Use `resolver_comments` and `triaging_steps` from the JSON context to describe what was found.]

**Previous Incidents Summary:**
[Analyze ALL tracker records to summarize patterns and trends. If no historical data is available, state that explicitly and explain why analysis is limited.
- **Incident Trends**: [Count of similar alerts, time patterns, common targets]
- **Historical Performance**: [Average MTTR, SLA compliance, false positive rate]]

## 🚨 Remediation & Escalation Procedures

[Provide actionable steps for remediation based on classification (True/False Positive). Include an escalation matrix and emergency procedures. Use both rulebook data and external search.]

## 🔧 Technical Reference

[Provide technical details such as key SIEM queries (use examples from SIEM search if available), and relevant tools. Link to vendor documentation here.]

**SIEM Query Examples:**
[If SIEM search results were found, format a list of example queries here for different platforms.]

**Vendor Documentation:**
[If vendor search results were found, link to relevant documentation.]

---
**Analysis Completeness**: [Provide a brief statement on the completeness of the analysis, referencing the available data.]

**Relevant Links:**
[Create a clean bullet list of all collected reference URLs, including MITRE, Microsoft, and vendor links. This should be the final section.]

**CRITICAL FORMATTING RULES:**
- DO NOT include sections: "⚡ Actions Taken & Results", "🎯 Recommendations & Best Practices", "📈 Performance Metrics".
- Start with detailed Alert Description, then Investigation, then Historical Context, then Remediation, then Technical Reference, then Links.
- If Historical Context has no data, remove the entire section.
- Use simple, everyday language in investigation steps.
- Reference links MUST be at the end in a clean bullet list.
- If any data point is not provided in the JSON context, explicitly state "Not provided" or "Insufficient data" rather than omitting the field."""

    # Add pre-collected reference links to the prompt
    final_prompt = enhanced_prompt.replace(
        "[Create a clean bullet list of all collected reference URLs...]",
        reference_links_md
    )

    return final_prompt


def _generate_with_gemini(user_prompt: str) -> str:
    """Generate response using Google Gemini with enhanced system prompt."""
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, **GEMINI_OPTIONS)
    
    # Use search-enhanced system prompt
    full_prompt = (
        f"{SEARCH_ENHANCED_SYSTEM_PROMPT}\n\n"
        f"{SYSTEM_PROMPT_JSON_CONTEXT}\n\n"
        f"{JSON_OUTPUT_PARSER_PROMPT}\n\n"
        f"{user_prompt}"
    )

    response = llm.invoke(full_prompt).content.strip()
    return response


def _generate_with_ollama(user_prompt: str) -> str:
    """Generate response using Ollama with enhanced system prompt."""
    messages = [
        {
            "role": "system",
            "content": (
                f"{SEARCH_ENHANCED_SYSTEM_PROMPT}\n\n"
                f"{SYSTEM_PROMPT_JSON_CONTEXT}\n\n"
                f"{JSON_OUTPUT_PARSER_PROMPT}"
            ),
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


def save_search_results(query: str, search_results: Dict[str, Any]) -> str:
    """Save search results for debugging and caching."""
    try:
        from .config import SEARCH_CACHE_DIR
        import os
        import re

        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:50]
        os.makedirs(SEARCH_CACHE_DIR, exist_ok=True)

        cache_path = f"{SEARCH_CACHE_DIR}/{safe_query}_search_{get_timestamp().replace(':', '-')}.json"

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(search_results, f, ensure_ascii=False, indent=2)

        print(f"💾 Search results cached: {cache_path}")
        return cache_path

    except Exception as e:
        print(f"⚠️ Failed to cache search results: {e}")
        return ""


def generate_alert_summary(filtered_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate high-level alert summary for quick reference."""
    summary = {
        "alert_overview": {},
        "key_metrics": {},
        "risk_assessment": {},
        "recommended_actions": [],
    }

    # Extract key information
    tracker_records = filtered_data.get("tracker_records", [])
    historical_analysis = filtered_data.get("historical_analysis", {})
    performance_metrics = filtered_data.get("performance_metrics", {})

    if tracker_records:
        # Get most recent incident
        recent_incident = tracker_records[0].get("tracker_data", {})

        summary["alert_overview"] = {
            "alert_type": recent_incident.get("alert/incident", "Unknown"),
            "rule_id": filtered_data.get("target_rule_id", "Unknown"),
            "priority": recent_incident.get("priority", "Unknown"),
            "status": recent_incident.get("status", "Unknown"),
            "vip_users": recent_incident.get("vip users", "No"),
        }

        # Calculate key metrics
        total_incidents = len(tracker_records)
        closed_incidents = sum(
            1
            for r in tracker_records
            if r.get("tracker_data", {}).get("status", "").lower() == "closed"
        )

        summary["key_metrics"] = {
            "total_historical_incidents": total_incidents,
            "closure_rate": (
                (closed_incidents / total_incidents * 100) if total_incidents > 0 else 0
            ),
            "average_mttr": performance_metrics.get("resolution_metrics", {}).get(
                "average_mttr", "Unknown"
            ),
            "false_positive_rate": historical_analysis.get(
                "classification_patterns", {}
            ).get("false_positive_rate", "Unknown"),
        }

        # Risk assessment
        risk_level = "low"
        if recent_incident.get("priority", "").lower() in ["high", "critical"]:
            risk_level = "high"
        elif recent_incident.get("vip users", "").lower() == "yes":
            risk_level = "medium"

        summary["risk_assessment"] = {
            "risk_level": risk_level,
            "requires_immediate_attention": risk_level == "high",
            "escalation_recommended": recent_incident.get("escalated to", "") != "",
        }

    return summary