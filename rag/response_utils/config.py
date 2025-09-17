"""
Configuration settings for RAG response generator.
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

# File paths
ARTIFACTS_DIR = "artifacts"
CONTEXT_JSON_DIR = f"{ARTIFACTS_DIR}/context_json"

# Validation settings
REQUIRED_SECTIONS = [
    "# 🛡️ Alert:",
    "## ⚡ Quick Summary",
    "## 📊 Incident Details",
    "## 🔍 What Happened",
    "## 👨‍💻 Simple Investigation Steps",
]
