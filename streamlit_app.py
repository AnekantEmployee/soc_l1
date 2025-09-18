import streamlit as st
import time
import sys
import os
from io import StringIO
import contextlib

# Set Ollama timeout before any imports
os.environ.setdefault("OLLAMA_TIMEOUT", "120")

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import your RAG components (exactly matching main.py)
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker
from rag.context_retriever import retrieve_context
from rag.response_generator import (
    generate_response_with_llm,
)
from rag.embedding_indexer import (
    index_chunks_with_ollama_faiss,
    faiss_index_exists,
)

# Configure Streamlit page
st.set_page_config(
    page_title="SOC RAG Assistant",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for chatbot styling
st.markdown(
    """
<style>
.system-status {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
    background: white;
    padding: 10px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    border: 1px solid #e6e6e6;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 5px 0;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.status-ready { background-color: #28a745; }
.status-not-ready { background-color: #dc3545; }
</style>
""",
    unsafe_allow_html=True,
)

# Configuration constants
PERSIST_DIR = "vector_store_faiss"
INDEX_NAME = "soc_rag"
TRACKER_PATH = (
    "Client1 - Q2 - Daily Incident Tracker_Dashboard  - Apr to Jun 2025(July 25).csv"
)
RULEBOOK_DIR = "rulebooks/"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen2.5:0.5b"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.index_ready = False
    st.session_state.processing = False


@contextlib.contextmanager
def capture_output():
    """Context manager to capture print statements"""
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    try:
        yield captured_output
    finally:
        sys.stdout = old_stdout


def initialize_system():
    """Initialize the RAG system"""
    st.session_state.processing = True
    start_time = time.time()

    # Add system initialization message
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": "🚀 Initializing SOC RAG System...",
            "type": "system",
        }
    )

    try:
        # Check if index exists
        need_build = not faiss_index_exists(
            persist_dir=PERSIST_DIR, index_name=INDEX_NAME
        )

        if not need_build:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "✅ FAISS index already exists. System ready!",
                    "type": "system",
                }
            )
            st.session_state.index_ready = True
            st.session_state.initialized = True
            st.session_state.processing = False
            return

        # Verify files exist
        if not os.path.exists(TRACKER_PATH):
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"❌ Tracker file not found: {TRACKER_PATH}",
                    "type": "error",
                }
            )
            st.session_state.processing = False
            return

        if not os.path.exists(RULEBOOK_DIR):
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"❌ Rulebook directory not found: {RULEBOOK_DIR}",
                    "type": "error",
                }
            )
            st.session_state.processing = False
            return

        # Load documents
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "📁 Loading documents...",
                "type": "system",
            }
        )

        with capture_output():
            loader = DocumentLoader(
                tracker_path=TRACKER_PATH, rulebook_dir=RULEBOOK_DIR
            )
            tracker_df, rulebook_dfs = loader.load_all_documents()

        if tracker_df is not None:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"✅ Loaded tracker with {tracker_df.shape[0]} incidents and {len(rulebook_dfs)} rulebooks",
                    "type": "system",
                }
            )

        # Create chunks
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "📝 Creating document chunks...",
                "type": "system",
            }
        )

        with capture_output():
            chunker = DocumentChunker(tracker_df, rulebook_dfs)
            chunks_dict = chunker.create_all_chunks()

        # Export files
        os.makedirs("artifacts", exist_ok=True)
        with capture_output():
            chunks_dump_path = chunker.export_chunks_to_text(
                chunks_dict,
                out_path="artifacts/all_chunks_dump.txt",
                max_chars_per_chunk=4000,
            )
            rule_keys_path = chunker.export_rule_keys(
                out_path="artifacts/rule_keys.json"
            )

        # Create embeddings
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "🔗 Creating embeddings and FAISS index...",
                "type": "system",
            }
        )

        with capture_output():
            index_stats = index_chunks_with_ollama_faiss(
                chunks_dict["all_chunks"],
                persist_dir=PERSIST_DIR,
                index_name=INDEX_NAME,
                model=EMBED_MODEL,
                batch_size=16,
            )

        elapsed_time = time.time() - start_time
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"🎉 System initialized successfully in {elapsed_time:.1f} seconds! Ready to answer your questions.",
                "type": "success",
            }
        )

        st.session_state.index_ready = True
        st.session_state.initialized = True

    except Exception as e:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"❌ Initialization failed: {str(e)}",
                "type": "error",
            }
        )

    st.session_state.processing = False


def process_query(query):
    """Process user query and get response"""
    if not st.session_state.index_ready:
        return "❌ System not initialized. Please click 'Initialize System' first."

    start_time = time.time()

    try:
        # Context retrieval
        with capture_output():
            context_results = retrieve_context(
                query=query,
                persist_dir=PERSIST_DIR,
                index_name=INDEX_NAME,
                embed_model=EMBED_MODEL,
                k_tracker=2,
                k_rulebook=5,
            )

        # # Build context
        # context_block = build_context_block(context_results, query)

        # # Save context
        # context_file = save_context_to_file(query, context_block)

        # Generate response
        with capture_output():
            response = generate_response_with_llm(
                query=query,
                context_results=context_results,
            )

        elapsed_time = time.time() - start_time

        # Return response with metadata
        return {
            "response": response,
            "processing_time": elapsed_time,
        }

    except Exception as e:
        return f"❌ Error processing query: {str(e)}"


# Main UI
st.title("🚀 SOC RAG Assistant")
st.markdown("### 🔒 Cybersecurity Rule Analysis & Investigation Assistant")
st.divider()

# System Status Display
status_col1, status_col2 = st.columns([3, 1])

with status_col2:
    if st.session_state.initialized:
        st.success("🟢 System Ready")
    else:
        st.warning("🟡 Not Initialized")

    if st.session_state.index_ready:
        st.success("🟢 Index Ready")
    else:
        st.error("🔴 Index Not Ready")

# Quick Actions
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if st.button(
        "🚀 Initialize System",
        disabled=st.session_state.processing,
        use_container_width=True,
    ):
        initialize_system()

with col2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []

with col3:
    if st.button("📊 System Info", use_container_width=True):
        info_content = f"""**System Configuration:**

📁 **Tracker File:** `{os.path.basename(TRACKER_PATH)}`  
📚 **Rulebooks Directory:** `{RULEBOOK_DIR}`  
🔗 **Vector Store:** FAISS with {EMBED_MODEL}  
🤖 **LLM Model:** {LLM_MODEL}  
🎯 **Processing:** Two-phase (Context + Response)"""

        st.session_state.messages.append(
            {"role": "assistant", "content": info_content, "type": "info"}
        )

# Suggested Queries
st.markdown("### 💡 Quick Start Questions")
suggested_queries = [
    "Rule 2",
    "Rule 014",
    "User Assigned Privileged Role",
    "Passwordless authentication analysis",
]

query_cols = st.columns(len(suggested_queries))
for i, suggested_query in enumerate(suggested_queries):
    with query_cols[i]:
        if st.button(
            f"📋 {suggested_query}", key=f"suggested_{i}", use_container_width=True
        ):
            if not st.session_state.processing:
                st.session_state.messages.append(
                    {"role": "user", "content": suggested_query}
                )
                # Process the query
                st.session_state.processing = True
                result = process_query(suggested_query)
                st.session_state.processing = False

                if isinstance(result, dict):
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": result["response"],
                            "type": "response",
                            "metadata": {
                                "processing_time": result["processing_time"],
                                "files": [],
                            },
                        }
                    )
                else:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": result, "type": "error"}
                    )
                st.rerun()

# Chat Messages Display
st.markdown("### 💬 Chat")

# Display chat messages
for message in st.session_state.messages:
    msg_type = message.get("type", "normal")

    if message["role"] == "user":
        with st.chat_message("user"):
            st.write(message["content"])

    else:  # assistant messages
        with st.chat_message("assistant"):
            if msg_type == "system":
                st.info(message["content"])
            elif msg_type == "error":
                st.error(message["content"])
            elif msg_type == "success":
                st.success(message["content"])
            elif msg_type == "response":
                st.markdown(message["content"])
                # Show simple metadata (without tracker/rulebook counts)
                if "metadata" in message:
                    meta = message["metadata"]
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "⏱️ Processing Time", f"{meta['processing_time']:.1f}s"
                        )
                    with col2:
                        st.metric("📄 Files Created", len(meta["files"]))
            else:
                st.write(message["content"])

# Processing indicator
if st.session_state.processing:
    with st.spinner("Processing your request..."):
        st.empty()

# Chat Input
user_input = st.chat_input(
    "Ask about security rules, procedures, or incidents...",
    disabled=st.session_state.processing,
)

if user_input and not st.session_state.processing:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Process query
    st.session_state.processing = True
    result = process_query(user_input)
    st.session_state.processing = False

    # Add assistant response
    if isinstance(result, dict):
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["response"],
                "type": "response",
                "metadata": {
                    "processing_time": result["processing_time"],
                    "files": [],
                },
            }
        )
    else:
        st.session_state.messages.append(
            {"role": "assistant", "content": result, "type": "error"}
        )

    st.rerun()

# Sidebar with system information (collapsed by default)
with st.sidebar:
    st.markdown("### 🔧 System Features")
    st.markdown(
        """
    - 🔍 **Advanced Context Retrieval** Dynamic rule mapping with FAISS vector search

    - 🤖 **AI-Powered Analysis** LLM response generation with structured prompts

    - 💾 **Comprehensive Logging** Context and response files for audit trails

    - 🎯 **Smart Classification** Enhanced query understanding and rule detection

    - 📈 **Performance Optimized** Efficient embedding and relevance filtering
    """
    )

    st.markdown("### 📁 Output Files")
    st.markdown(
        """
    All generated files are saved in the `artifacts/` directory:
    - **Markdown files**: Formatted responses  
    - **JSON files**: Structured analysis data
    """
    )

    if st.session_state.initialized:
        st.success("🟢 System Operational")
    else:
        st.warning("🟡 System Needs Initialization")