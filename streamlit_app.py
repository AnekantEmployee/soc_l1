import streamlit as st
import time
import sys
import os
from io import StringIO
import contextlib

# Add the project root to Python path - UNCOMMENT THIS
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import your RAG components (should work after path fix)
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker
from rag.embedding_indexer import (
    index_chunks_with_ollama_faiss,
    index_rule_keys_with_ollama_faiss,
    faiss_index_exists,
)
from rag.context_retriever import retrieve_context, build_context_block
from rag.response_generator import (
    generate_response_with_llm,
    save_context_to_file,
    write_rule_markdown,
)

# Configure Streamlit page
st.set_page_config(page_title="🚀 SOC RAG Assistant", page_icon="🔒", layout="wide")

# Custom CSS for better styling
st.markdown(
    """
<style>
.main-header {
    font-size: 2.5rem;
    color: #1f77b4;
    text-align: center;
    padding: 1rem 0;
}
.step-header {
    background-color: #f0f2f6;
    padding: 0.5rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
}
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.info-box {
    background-color: #d1ecf1;
    border: 1px solid #bee5eb;
    color: #0c5460;
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.processing-box {
    background-color: #fff3cd;
    border: 1px solid #ffeaa7;
    color: #856404;
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.error-box {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
</style>
""",
    unsafe_allow_html=True,
)

# Title
st.markdown('<h1 class="main-header">🚀 SOC RAG Assistant</h1>', unsafe_allow_html=True)
st.markdown("### 🔒 Cybersecurity Rule Analysis & Investigation Assistant")

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.processing_logs = []
    st.session_state.index_ready = False


@contextlib.contextmanager
def capture_output():
    """Context manager to capture print statements"""
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    try:
        yield captured_output
    finally:
        sys.stdout = old_stdout


def log_step(message, type="info"):
    """Add a log message with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.processing_logs.append(
        {"time": timestamp, "message": message, "type": type}
    )


def display_logs():
    """Display processing logs in a nice format"""
    if st.session_state.processing_logs:
        st.markdown("### 📋 Processing Logs")
        for log in st.session_state.processing_logs[-20:]:  # Show last 20 logs
            if log["type"] == "success":
                st.markdown(
                    f'<div class="success-box">✅ [{log["time"]}] {log["message"]}</div>',
                    unsafe_allow_html=True,
                )
            elif log["type"] == "error":
                st.markdown(
                    f'<div class="error-box">❌ [{log["time"]}] {log["message"]}</div>',
                    unsafe_allow_html=True,
                )
            elif log["type"] == "processing":
                st.markdown(
                    f'<div class="processing-box">🔄 [{log["time"]}] {log["message"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="info-box">ℹ️ [{log["time"]}] {log["message"]}</div>',
                    unsafe_allow_html=True,
                )


def initialize_system():
    """Initialize the RAG system"""
    start_time = time.time()

    try:
        log_step("🚀 Starting SOC RAG System Initialization", "processing")

        # Step 1: Check if index exists
        if faiss_index_exists():
            log_step(
                "📊 Found existing FAISS index - skipping initialization", "success"
            )
            st.session_state.index_ready = True
            st.session_state.initialized = True
            return

        # Step 1: Load documents
        log_step("📁 Loading documents from files...", "processing")

        with capture_output() as captured:
            tracker_path = "Client1 - Q2 - Daily Incident Tracker_Dashboard  - Apr to Jun 2025(July 25).csv"
            loader = DocumentLoader(tracker_path, "rulebooks")
            tracker_df, rulebook_dfs = loader.load_all_documents()

        # Display captured output
        output_lines = captured.getvalue().strip().split("\n")
        for line in output_lines:
            if line.strip():
                log_step(line.strip(), "info")

        if tracker_df is not None:
            log_step(
                f"✅ Loaded tracker: {tracker_df.shape[0]} rows, {tracker_df.shape[1]} columns",
                "success",
            )

        log_step(f"✅ Loaded {len(rulebook_dfs)} rulebook files", "success")

        # Step 2: Create chunks
        log_step("📝 Creating document chunks...", "processing")

        with capture_output() as captured:
            chunker = DocumentChunker(tracker_df, rulebook_dfs)
            chunks = chunker.create_all_chunks()

        output_lines = captured.getvalue().strip().split("\n")
        for line in output_lines:
            if line.strip():
                log_step(line.strip(), "info")

        log_step(f"✅ Created {len(chunks['all_chunks'])} total chunks", "success")

        # Export rule keys
        with capture_output() as captured:
            rule_keys_path = chunker.export_rule_keys()

        log_step(f"🔑 Exported rule keys to {rule_keys_path}", "success")

        # Step 3: Create embeddings and index
        log_step("🔗 Creating embeddings and FAISS index...", "processing")

        with capture_output() as captured:
            index_result = index_chunks_with_ollama_faiss(chunks["all_chunks"])

        output_lines = captured.getvalue().strip().split("\n")
        for line in output_lines:
            if line.strip():
                log_step(line.strip(), "info")

        log_step(
            f"✅ Indexed {index_result['indexed']} documents in {index_result['elapsed_sec']}s",
            "success",
        )

        # Index rule keys
        with capture_output() as captured:
            key_index_result = index_rule_keys_with_ollama_faiss()

        if key_index_result["indexed"] > 0:
            log_step(f"🔑 Indexed {key_index_result['indexed']} rule keys", "success")

        elapsed_time = time.time() - start_time
        log_step(
            f"🎉 System initialization completed in {elapsed_time:.2f} seconds",
            "success",
        )

        st.session_state.index_ready = True
        st.session_state.initialized = True

    except Exception as e:
        log_step(f"❌ Initialization failed: {str(e)}", "error")
        st.error(f"Initialization failed: {str(e)}")


def process_query(query):
    """Process a user query and return response with timing"""
    if not st.session_state.index_ready:
        st.error("❌ System not initialized. Please initialize first.")
        return None, 0

    start_time = time.time()

    try:
        log_step(f"🔍 Processing query: {query}", "processing")

        # Phase A: Context Retrieval
        log_step("📊 Phase A: Retrieving context...", "processing")

        # FIX: Add all required parameters to match main script
        persist_dir = "vector_store_faiss"
        index_name = "soc_rag"

        with capture_output() as captured:
            context_results = retrieve_context(
                query=query,
                persist_dir=persist_dir,
                index_name=index_name,
                embed_model="nomic-embed-text",
                k_tracker=2,
                k_rulebook=5,
            )

        # Display context retrieval logs
        output_lines = captured.getvalue().strip().split("\n")
        for line in output_lines:
            if line.strip():
                log_step(line.strip(), "info")

        # Build context block
        context_block = build_context_block(context_results, query)

        # Save context for debugging
        context_file = save_context_to_file(query, context_block)
        log_step(f"📁 Context saved to: {context_file}", "info")

        tracker_hits = len(context_results.get("tracker", []))
        rulebook_hits = len(context_results.get("rulebook", []))

        log_step(
            f"✅ Context retrieved: {tracker_hits} tracker + {rulebook_hits} rulebook hits",
            "success",
        )

        # Phase B: Response Generation
        log_step("🤖 Phase B: Generating response...", "processing")

        with capture_output() as captured:
            # FIX: Add missing context_results and model parameters
            response = generate_response_with_llm(
                query=query,
                context_block=context_block,
                context_results=context_results,  # ← ADD THIS
                model="qwen2.5:0.5b",  # ← ADD THIS
            )

        # Save response to markdown
        markdown_file = write_rule_markdown(
            query=query, answer=response, out_dir="artifacts"
        )  # ← ADD out_dir parameter
        log_step(f"📄 Response saved to: {markdown_file}", "info")

        elapsed_time = time.time() - start_time
        log_step(
            f"✅ Query processed successfully in {elapsed_time:.2f} seconds", "success"
        )

        return {
            "response": response,
            "context": context_block,
            "context_file": context_file,
            "markdown_file": markdown_file,
            "stats": {
                "tracker_hits": tracker_hits,
                "rulebook_hits": rulebook_hits,
                "processing_time": elapsed_time,
            },
        }, elapsed_time

    except Exception as e:
        elapsed_time = time.time() - start_time
        log_step(f"❌ Query processing failed: {str(e)}", "error")
        return None, elapsed_time


# Main interface
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Query Interface")

    # Suggested questions
    st.markdown("#### 🎯 Suggested Questions:")
    suggested_queries = [
        "Rule 2",
        "Rule 014",
        "User Assigned Privileged Role",
        "Passwordless authentication may be happen due to compromised account or privileged account.",
    ]

    query_cols = st.columns(2)
    for i, suggested_query in enumerate(suggested_queries):
        col_idx = i % 2
        with query_cols[col_idx]:
            if st.button(f"📋 {suggested_query}", key=f"suggested_{i}"):
                st.session_state.selected_query = suggested_query

    # Query input
    query = st.text_input(
        "🔍 Enter your query:",
        value=st.session_state.get("selected_query", ""),
        placeholder="Ask about security rules, procedures, or incidents...",
        key="query_input",
    )

    # Processing buttons
    col_btn1, col_btn2, col_btn3 = st.columns(3)

    with col_btn1:
        if st.button("🚀 Initialize System", type="secondary"):
            st.session_state.processing_logs = []
            initialize_system()

    with col_btn2:
        process_btn = st.button(
            "🔍 Process Query", type="primary", disabled=not query.strip()
        )

    with col_btn3:
        if st.button("🗑️ Clear Logs"):
            st.session_state.processing_logs = []

with col2:
    st.markdown("### 📊 System Status")

    # System status indicators
    if st.session_state.initialized:
        st.markdown(
            '<div class="success-box">✅ System Initialized</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="info-box">⚠️ System Not Initialized</div>',
            unsafe_allow_html=True,
        )

    if st.session_state.index_ready:
        st.markdown(
            '<div class="success-box">✅ Index Ready</div>', unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="info-box">⚠️ Index Not Ready</div>', unsafe_allow_html=True
        )

    st.markdown(f"**📋 Logs:** {len(st.session_state.processing_logs)}")

# Process query if button clicked
if process_btn and query.strip():
    result, processing_time = process_query(query.strip())

    if result:
        # Display results
        st.markdown("---")
        st.markdown("## 📋 Query Results")

        # Statistics
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("⏱️ Processing Time", f"{result['stats']['processing_time']:.2f}s")
        with col_stat2:
            st.metric("📊 Tracker Hits", result["stats"]["tracker_hits"])
        with col_stat3:
            st.metric("📚 Rulebook Hits", result["stats"]["rulebook_hits"])

        # Response
        st.markdown("### 🤖 Generated Response")
        st.markdown(result["response"])

        # Context (expandable)
        with st.expander("📄 Context Used (Click to expand)"):
            st.code(
                result["context"][:2000] + "..."
                if len(result["context"]) > 2000
                else result["context"]
            )

        # Files created
        st.markdown("### 📁 Files Created")
        st.info(f"📄 Context: `{result['context_file']}`")
        st.info(f"📝 Markdown: `{result['markdown_file']}`")

# Display logs at the bottom
display_logs()

# Footer
st.markdown("---")
st.markdown("### 🔧 System Information")
col_info1, col_info2 = st.columns(2)
with col_info1:
    st.info("**Vector Store:** FAISS with Ollama embeddings")
    st.info("**Model:** nomic-embed-text")
with col_info2:
    st.info("**LLM:** qwen2.5:0.5b")
    st.info("**Framework:** Enhanced RAG with direct file reading")
