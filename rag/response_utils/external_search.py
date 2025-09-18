"""
Enhanced external search manager with intelligent SIEM platform and vendor documentation search.
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from langchain_community.tools.tavily_search import TavilySearchResults
from .config import (
    ENABLE_EXTERNAL_SEARCH,
    TAVILY_API_KEY,
    MAX_SEARCH_RESULTS,
    SEARCH_QUERIES,
    SEARCH_TIMEOUT,
    SIEM_PLATFORMS,
    SECURITY_VENDORS,
    INTELLIGENT_SEARCH_ENABLED,
    INCLUDE_SIEM_QUERIES,
    INCLUDE_VENDOR_DOCS,
    MAX_SIEM_PLATFORMS_TO_SEARCH,
)


class EnhancedExternalSearchManager:
    """Enhanced external search manager with intelligent SIEM and vendor documentation integration."""

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

    def search_comprehensive_alert_information(
        self, alert_name: str, rule_id: str = "", alert_category: str = ""
    ) -> Dict[str, Any]:
        """Search for comprehensive alert information including SIEM-specific content."""
        if not self.search_enabled:
            return {"status": "disabled", "results": []}

        search_results = {
            "status": "success",
            "alert_description": [],
            "investigation_guide": [],
            "false_positives": [],
            "threat_intel": [],
            "mitre_attack": [],
            "siem_queries": {},  # New: SIEM-specific queries
            "vendor_documentation": {},  # New: Vendor-specific docs
            "reference_links": [],  # New: Collected reference links
        }

        try:
            # Core security searches
            search_results.update(self._perform_core_security_searches(alert_name))
            
            # SIEM platform specific searches
            if INCLUDE_SIEM_QUERIES:
                search_results["siem_queries"] = self._search_siem_platforms(alert_name, alert_category)
            
            # Vendor documentation searches
            if INCLUDE_VENDOR_DOCS:
                search_results["vendor_documentation"] = self._search_vendor_documentation(alert_name, alert_category)
            
            # Collect all reference links
            search_results["reference_links"] = self._collect_reference_links(search_results)

        except Exception as e:
            print(f"⚠️ Comprehensive search error: {e}")
            search_results["status"] = "error"
            search_results["error_message"] = str(e)

        return search_results

    def _perform_core_security_searches(self, alert_name: str) -> Dict[str, List]:
        """Perform core security searches for alert information."""
        core_results = {}
        
        core_searches = [
            ("alert_description", "alert_description"),
            ("investigation_guide", "investigation_guide"), 
            ("false_positives", "false_positives"),
            ("threat_intel", "threat_intel"),
            ("mitre_attack", "mitre_attack"),
        ]

        for search_key, query_key in core_searches:
            try:
                query = SEARCH_QUERIES[query_key].format(alert_name=alert_name)
                results = self.search_tool.run(query)
                core_results[search_key] = self._parse_search_results(results)
            except Exception as e:
                print(f"⚠️ Core search error for {search_key}: {e}")
                core_results[search_key] = []

        return core_results

    def _search_siem_platforms(self, alert_name: str, alert_category: str = "") -> Dict[str, Dict]:
        """Search for SIEM platform specific queries and documentation."""
        siem_results = {}
        
        # Prioritize SIEM platforms based on popularity and coverage
        priority_platforms = ["microsoft_sentinel", "splunk", "elastic_siem", "qradar"]
        
        for platform_id in priority_platforms[:MAX_SIEM_PLATFORMS_TO_SEARCH]:
            if platform_id not in SIEM_PLATFORMS:
                continue
                
            platform_info = SIEM_PLATFORMS[platform_id]
            siem_results[platform_id] = {
                "platform_name": platform_info["name"],
                "query_language": platform_info["query_language"],
                "base_url": platform_info["base_url"],
                "search_results": [],
                "documentation_links": [],
            }
            
            try:
                # Search for platform-specific queries
                search_terms = platform_info["search_terms"]
                for term in search_terms:
                    query = f"{term} {alert_name} detection rule investigation"
                    results = self.search_tool.run(query)
                    parsed_results = self._parse_search_results(results, max_results=2)
                    siem_results[platform_id]["search_results"].extend(parsed_results)
                
                # Add known documentation links
                siem_results[platform_id]["documentation_links"] = self._generate_siem_doc_links(
                    platform_id, alert_name, alert_category
                )
                
            except Exception as e:
                print(f"⚠️ SIEM search error for {platform_id}: {e}")
                continue

        return siem_results

    def _search_vendor_documentation(self, alert_name: str, alert_category: str = "") -> Dict[str, Dict]:
        """Search for vendor-specific documentation and resources."""
        vendor_results = {}
        
        # Prioritize vendors based on alert category
        priority_vendors = self._get_priority_vendors(alert_category)
        
        for vendor_id in priority_vendors:
            if vendor_id not in SECURITY_VENDORS:
                continue
                
            vendor_info = SECURITY_VENDORS[vendor_id]
            vendor_results[vendor_id] = {
                "vendor_name": vendor_info["name"],
                "search_results": [],
                "documentation_links": vendor_info["base_urls"],
            }
            
            try:
                # Search for vendor-specific documentation
                query = f"site:{vendor_info['base_urls'][0]} {alert_name} security alert"
                results = self.search_tool.run(query)
                vendor_results[vendor_id]["search_results"] = self._parse_search_results(results, max_results=2)
                
            except Exception as e:
                print(f"⚠️ Vendor search error for {vendor_id}: {e}")
                continue

        return vendor_results

    def _get_priority_vendors(self, alert_category: str) -> List[str]:
        """Get prioritized vendor list based on alert category."""
        category_vendor_mapping = {
            "authentication": ["microsoft", "okta", "ping_identity"],
            "endpoint": ["crowdstrike", "carbon_black", "sentinelone"],
            "network": ["palo_alto", "fortinet", "cisco"],
            "cloud": ["microsoft", "aws", "google_cloud"],
        }
        
        priority_vendors = category_vendor_mapping.get(alert_category, [])
        # Always include Microsoft for general coverage
        if "microsoft" not in priority_vendors:
            priority_vendors.insert(0, "microsoft")
            
        # Add other major vendors
        all_vendors = ["microsoft", "crowdstrike", "palo_alto", "fortinet"]
        for vendor in all_vendors:
            if vendor not in priority_vendors:
                priority_vendors.append(vendor)
                
        return priority_vendors[:3]  # Limit to top 3

    def _generate_siem_doc_links(self, platform_id: str, alert_name: str, alert_category: str) -> List[str]:
        """Generate relevant documentation links for SIEM platforms."""
        platform_info = SIEM_PLATFORMS[platform_id]
        base_url = platform_info["base_url"]
        
        # Common documentation sections
        doc_links = [f"{base_url}"]
        
        if platform_id == "microsoft_sentinel":
            doc_links.extend([
                "https://docs.microsoft.com/en-us/azure/sentinel/hunting-queries",
                "https://docs.microsoft.com/en-us/azure/sentinel/kusto-overview",
                "https://docs.microsoft.com/en-us/azure/sentinel/tutorial-investigate-cases",
                "https://github.com/Azure/Azure-Sentinel/tree/master/Hunting%20Queries",
            ])
        elif platform_id == "splunk":
            doc_links.extend([
                "https://docs.splunk.com/Documentation/Splunk/latest/SearchReference/",
                "https://docs.splunk.com/Documentation/ES/latest/",
                "https://splunkbase.splunk.com/",
            ])
        elif platform_id == "elastic_siem":
            doc_links.extend([
                "https://www.elastic.co/guide/en/security/current/rules-ui-management.html",
                "https://www.elastic.co/guide/en/security/current/detection-engine-overview.html",
            ])
        elif platform_id == "qradar":
            doc_links.extend([
                "https://www.ibm.com/docs/en/qradar-common?topic=qradar-aql-reference",
                "https://www.ibm.com/docs/en/qradar-common?topic=building-aql-queries",
            ])
            
        return doc_links

    def _collect_reference_links(self, search_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Collect all reference links from search results."""
        reference_links = []
        
        # Collect from core searches
        for section in ["alert_description", "investigation_guide", "false_positives", "threat_intel", "mitre_attack"]:
            for result in search_results.get(section, []):
                if result.get("url"):
                    reference_links.append({
                        "title": result.get("title", ""),
                        "url": result["url"],
                        "source": section.replace("_", " ").title(),
                        "relevance_score": result.get("relevance_score", 0),
                    })
        
        # Collect SIEM documentation links
        for platform_id, platform_data in search_results.get("siem_queries", {}).items():
            platform_name = platform_data.get("platform_name", platform_id)
            for url in platform_data.get("documentation_links", []):
                reference_links.append({
                    "title": f"{platform_name} Documentation",
                    "url": url,
                    "source": "SIEM Documentation",
                    "relevance_score": 0.8,
                })
        
        # Collect vendor documentation links
        for vendor_id, vendor_data in search_results.get("vendor_documentation", {}).items():
            vendor_name = vendor_data.get("vendor_name", vendor_id)
            for url in vendor_data.get("documentation_links", []):
                reference_links.append({
                    "title": f"{vendor_name} Security Documentation",
                    "url": url,
                    "source": "Vendor Documentation", 
                    "relevance_score": 0.7,
                })
        
        # Remove duplicates and sort by relevance
        unique_links = {}
        for link in reference_links:
            url = link["url"]
            if url not in unique_links or unique_links[url]["relevance_score"] < link["relevance_score"]:
                unique_links[url] = link
        
        return sorted(unique_links.values(), key=lambda x: x["relevance_score"], reverse=True)

    def _parse_search_results(self, results: List[Dict], max_results: int = None) -> List[Dict]:
        """Parse and format search results."""
        if not results:
            return []

        limit = max_results or MAX_SEARCH_RESULTS
        parsed_results = []
        
        for result in results[:limit]:
            if isinstance(result, dict):
                parsed_results.append({
                    "title": result.get("title", ""),
                    "content": result.get("content", "")[:600],  # Increased content length
                    "url": result.get("url", ""),
                    "relevance_score": result.get("score", 0),
                })

        return parsed_results

    def generate_siem_query_examples(self, alert_name: str, siem_results: Dict[str, Dict]) -> Dict[str, str]:
        """Generate example SIEM queries based on search results."""
        query_examples = {}
        
        for platform_id, platform_data in siem_results.items():
            platform_name = platform_data.get("platform_name", "")
            query_language = platform_data.get("query_language", "")
            
            # Generate basic query templates based on platform
            if platform_id == "microsoft_sentinel":
                query_examples[platform_name] = f"""
// {alert_name} Investigation Query
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID in (4624, 4625, 4648)  // Adjust based on alert type
| where Account contains "suspicious_user"
| project TimeGenerated, Computer, Account, EventID, LogonType
| order by TimeGenerated desc
                """.strip()
                
            elif platform_id == "splunk":
                query_examples[platform_name] = f"""
index=security sourcetype=WinEventLog:Security EventCode=4624 OR EventCode=4625
| search "{alert_name}"
| eval LogonResult=if(EventCode=4624,"Success","Failure")
| stats count by user, LogonResult, src_ip
| sort -count
                """.strip()
                
            elif platform_id == "elastic_siem":
                query_examples[platform_name] = f"""
event.category:authentication AND event.outcome:(success OR failure)
AND user.name:* AND source.ip:*
AND event.action:"{alert_name.lower()}"
                """.strip()
                
            elif platform_id == "qradar":
                query_examples[platform_name] = f"""
SELECT sourceip, username, eventname, starttime
FROM events
WHERE eventname ILIKE '%{alert_name}%'
AND starttime > LAST 24 HOURS
ORDER BY starttime DESC
                """.strip()

        return query_examples