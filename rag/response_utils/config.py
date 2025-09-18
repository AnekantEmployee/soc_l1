"""
Configuration settings for RAG response generator with external search capabilities.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Model Configuration
USE_GEMINI = True  # Set to True to use Gemini, False for Ollama

# Ollama Configuration
OLLAMA_MODEL = "qwen2.5:0.5b"
OLLAMA_OPTIONS = {
    "temperature": 0.15,  # Lower temperature for consistency
    "top_k": 30,  # Focused token selection
    "top_p": 0.9,  # Good balance for natural language
    "repeat_penalty": 1.1,  # Prevent repetition
    "num_ctx": 8192,  # Larger context for comprehensive data
}

# Gemini Configuration
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_OPTIONS = {
    "temperature": 0.2,  # Slightly higher for more natural language
    "top_k": 40,
    "top_p": 0.9,
}

# External Search Configuration
ENABLE_EXTERNAL_SEARCH = True  # Enable/disable external search capabilities
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")  # Tavily search API key
MAX_SEARCH_RESULTS = 3  # Maximum search results per query
SEARCH_TIMEOUT = 30  # Search timeout in seconds

# Intelligent Search Configuration
INTELLIGENT_SEARCH_ENABLED = True
INCLUDE_SIEM_QUERIES = True
INCLUDE_VENDOR_DOCS = True
MAX_SIEM_PLATFORMS_TO_SEARCH = 3  # Limit the number of SIEM platforms to search for efficiency

# Search Query Templates
SEARCH_QUERIES = {
    "alert_description": "{alert_name} security alert MITRE ATT&CK technique",
    "investigation_guide": "{alert_name} SOC analyst investigation procedure",
    "false_positives": "{alert_name} false positive causes troubleshooting",
    "vendor_docs": "{vendor} {alert_name} security documentation",
    "threat_intel": "{alert_name} threat intelligence attack pattern",
    "mitre_attack": "{alert_name} MITRE ATT&CK framework technique",
}

# SIEM Platform Search Configuration
SIEM_PLATFORMS = {
    "microsoft_sentinel": {
        "name": "Microsoft Sentinel",
        "query_language": "Kusto Query Language (KQL)",
        "base_url": "https://docs.microsoft.com/en-us/azure/sentinel/",
        "search_terms": ["KQL", "Azure Sentinel"],
    },
    "splunk": {
        "name": "Splunk",
        "query_language": "Splunk Search Processing Language (SPL)",
        "base_url": "https://docs.splunk.com/Documentation/Splunk",
        "search_terms": ["SPL", "Splunk"],
    },
    "elastic_siem": {
        "name": "Elastic SIEM",
        "query_language": "Lucene query syntax",
        "base_url": "https://www.elastic.co/guide/en/security/current/index.html",
        "search_terms": ["Elastic", "Elasticsearch"],
    },
    "qradar": {
        "name": "QRadar",
        "query_language": "AQL (Ariel Query Language)",
        "base_url": "https://www.ibm.com/docs/en/qradar",
        "search_terms": ["QRadar", "AQL"],
    },
}

# Security Vendor Search Configuration
SECURITY_VENDORS = {
    "microsoft": {
        "name": "Microsoft",
        "base_urls": ["https://docs.microsoft.com/", "https://www.microsoft.com/en-us/security"],
    },
    "crowdstrike": {
        "name": "CrowdStrike",
        "base_urls": ["https://docs.crowdstrike.com/", "https://www.crowdstrike.com/blog/"],
    },
    "palo_alto": {
        "name": "Palo Alto Networks",
        "base_urls": ["https://docs.paloaltonetworks.com/", "https://www.paloaltonetworks.com/security-research"],
    },
    "fortinet": {
        "name": "Fortinet",
        "base_urls": ["https://docs.fortinet.com/", "https://www.fortinet.com/blog/"],
    },
    "cisco": {
        "name": "Cisco",
        "base_urls": ["https://www.cisco.com/c/en/us/support/index.html", "https://blogs.cisco.com/security"],
    },
}


# File paths
ARTIFACTS_DIR = "artifacts"
CONTEXT_JSON_DIR = f"{ARTIFACTS_DIR}/context_json"
SEARCH_CACHE_DIR = f"{ARTIFACTS_DIR}/search_cache"

# Validation settings
REQUIRED_SECTIONS = [
    "# 🛡️ Alert:",
    "## 📖 Detailed Alert Description & Context",
    "## ⚡ Initial Alert Analysis",
    "## 📊 Historical Context & Tracker Analysis",
    "## 👨‍💻 Simple Investigation Steps",
    "## 🎯 Recommendations & Best Practices",
]

# Enhanced analysis settings
ENABLE_HISTORICAL_ANALYSIS = True  # Enable tracker pattern analysis
ENABLE_PERFORMANCE_METRICS = True  # Calculate performance metrics
MIN_HISTORICAL_INCIDENTS = 3  # Minimum incidents needed for trend analysis
HISTORICAL_LOOKBACK_DAYS = 90  # Days to look back for historical analysis
HIDE_EMPTY_HISTORICAL_SECTIONS = True # Hide sections if no historical data is found

# Alert categorization settings
ALERT_CATEGORIES = {
    "authentication": ["login", "authentication", "mfa", "password"],
    "network": ["network", "traffic", "connection", "ip", "dns"],
    "endpoint": ["endpoint", "malware", "process", "file", "registry"],
    "data_protection": ["data", "dlp", "exfiltration", "encryption"],
    "privilege_escalation": ["privilege", "escalation", "admin", "sudo"],
    "lateral_movement": ["lateral", "movement", "pivot", "compromise"],
}

# Performance thresholds
SLA_THRESHOLDS = {"critical": 15, "high": 30, "medium": 60, "low": 240}  # minutes

# Quality metrics
QUALITY_METRICS = {
    "min_investigation_steps": 5,
    "required_evidence_types": ["ip_analysis", "user_analysis", "timeline"],
    "escalation_triggers": ["vip_user", "data_exfiltration", "lateral_movement"],
}