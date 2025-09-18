"""
Enhanced response generator with external search capabilities and comprehensive analysis.
"""

import os
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


class ExternalSearchManager:
    """Manages external search operations for alert analysis."""

    def __init__(self):
        self.search_tool = None
        self.search_enabled = ENABLE_EXTERNAL_SEARCH and TAVILY_API_KEY

        if self.search_enabled:
            try:
                self.search_tool = TavilySearchResults(
                    max_results=MAX_SEARCH_RESULTS, api_key=TAVILY_API_KEY
                )
            except Exception as e:
                print(f"⚠️ Failed to initialize search tool: {e}")
                self.search_enabled = False

    def search_alert_information(
        self, alert_name: str, rule_id: str = ""
    ) -> Dict[str, Any]:
        """Search for comprehensive alert information."""
        if not self.search_enabled:
            return {"status": "disabled", "results": []}

        search_results = {
            "alert_description": [],
            "investigation_guide": [],
            "false_positives": [],
            "threat_intel": [],
            "mitre_attack": [],
        }

        try:
            # Search for alert description and MITRE ATT&CK info
            description_query = SEARCH_QUERIES["alert_description"].format(
                alert_name=alert_name
            )
            description_results = self.search_tool.run(description_query)
            search_results["alert_description"] = self._parse_search_results(
                description_results
            )

            # Search for investigation procedures
            investigation_query = SEARCH_QUERIES["investigation_guide"].format(
                alert_name=alert_name
            )
            investigation_results = self.search_tool.run(investigation_query)
            search_results["investigation_guide"] = self._parse_search_results(
                investigation_results
            )

            # Search for false positive information
            fp_query = SEARCH_QUERIES["false_positives"].format(alert_name=alert_name)
            fp_results = self.search_tool.run(fp_query)
            search_results["false_positives"] = self._parse_search_results(fp_results)

            # Search for threat intelligence
            threat_query = SEARCH_QUERIES["threat_intel"].format(alert_name=alert_name)
            threat_results = self.search_tool.run(threat_query)
            search_results["threat_intel"] = self._parse_search_results(threat_results)

            # Search for MITRE ATT&CK mapping
            mitre_query = SEARCH_QUERIES["mitre_attack"].format(alert_name=alert_name)
            mitre_results = self.search_tool.run(mitre_query)
            search_results["mitre_attack"] = self._parse_search_results(mitre_results)

        except Exception as e:
            print(f"⚠️ Search error: {e}")
            search_results["status"] = "error"
            search_results["error_message"] = str(e)

        return search_results

    def _parse_search_results(self, results: List[Dict]) -> List[Dict]:
        """Parse and format search results."""
        if not results:
            return []

        parsed_results = []
        for result in results[:MAX_SEARCH_RESULTS]:
            if isinstance(result, dict):
                parsed_results.append(
                    {
                        "title": result.get("title", ""),
                        "content": result.get("content", "")[
                            :500
                        ],  # Limit content length
                        "url": result.get("url", ""),
                        "relevance_score": result.get("score", 0),
                    }
                )

        return parsed_results


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

        # Perform external search
        search_manager = ExternalSearchManager()
        external_search_results = {}

        if alert_name:
            print(f"🔍 Searching external sources for: {alert_name}")
            external_search_results = search_manager.search_alert_information(
                alert_name, rule_id
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
    if search_results and search_results.get("alert_description"):
        search_context = "\n**EXTERNAL SEARCH RESULTS:**\n"

        if search_results.get("alert_description"):
            search_context += "\n**Alert Description & MITRE ATT&CK Information:**\n"
            for result in search_results["alert_description"]:
                search_context += (
                    f"- {result.get('title', '')}: {result.get('content', '')}\n"
                )

        if search_results.get("investigation_guide"):
            search_context += "\n**Investigation Procedures & Best Practices:**\n"
            for result in search_results["investigation_guide"]:
                search_context += (
                    f"- {result.get('title', '')}: {result.get('content', '')}\n"
                )

        if search_results.get("false_positives"):
            search_context += "\n**False Positive Causes & Troubleshooting:**\n"
            for result in search_results["false_positives"]:
                search_context += (
                    f"- {result.get('title', '')}: {result.get('content', '')}\n"
                )

        if search_results.get("threat_intel"):
            search_context += "\n**Threat Intelligence & Attack Patterns:**\n"
            for result in search_results["threat_intel"]:
                search_context += (
                    f"- {result.get('title', '')}: {result.get('content', '')}\n"
                )

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

    # Create comprehensive prompt
    enhanced_prompt = PROMPT_TEMPLATE.format(query=query, json_context=json_context)

    # Add search and insights context
    enhanced_prompt += search_context + insights_context

    enhanced_prompt += f"\n**ALERT CATEGORIZATION:** {get_alert_category(alert_name)}"

    enhanced_prompt += """

**RESPONSE STRUCTURE REQUIREMENTS:**
1. **Detailed Alert Description**: Use external search results to provide comprehensive alert context, MITRE ATT&CK mapping, and threat intelligence
2. **Initial Alert Analysis**: Present current incident details and investigation findings from JSON context
3. **Historical Context**: Analyze tracker data patterns, trends, and lessons learned
4. **Simple Investigation Steps**: Convert procedures into L1-friendly steps with time estimates
5. **Recommendations**: Provide actionable recommendations based on historical analysis and search insights

**CRITICAL INSTRUCTIONS:**
- Start with comprehensive alert description using search results
- Include ALL historical pattern analysis from tracker data
- Reference specific previous incidents and their resolutions
- Make investigation procedures simple but comprehensive
- Include external knowledge while maintaining focus on provided context data
- Ensure response follows the exact section structure specified in the system prompt"""

    return enhanced_prompt


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
