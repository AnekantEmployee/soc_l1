# main.py
import os
import traceback
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker
from rag.retriever_qa import answer_query_with_rag
from rag.embedding_indexer import index_chunks_with_ollama_faiss, faiss_index_exists

os.environ.setdefault("OLLAMA_TIMEOUT", "120")


def quick_test_run():
    print("=" * 50)
    print("🚀 QUICK RAG TEST RUN")
    print("=" * 50)

    persist_dir = "vector_store_faiss"
    index_name = "soc_rag"
    need_build = not faiss_index_exists(persist_dir=persist_dir, index_name=index_name)
    tracker_path = "Client1 - Q2 - Daily Incident Tracker_Dashboard  - Apr to Jun 2025(July 25).csv"
    rulebook_dir = "rulebooks/"

    if need_build:
        # Only do Steps 1–3 when index missing
        if not os.path.exists(tracker_path):
            print(f"❌ Tracker file not found: {tracker_path}")
            return False
        if not os.path.exists(rulebook_dir):
            print(f"❌ Rulebook directory not found: {rulebook_dir}")
            return False

        print("📁 Step 1: Loading documents...")
        loader = DocumentLoader(tracker_path=tracker_path, rulebook_dir=rulebook_dir)
        tracker_df, rulebook_dfs = loader.load_all_documents()

        print("📝 Step 2: Creating document chunks...")
        chunker = DocumentChunker(tracker_df, rulebook_dfs)
        chunks_dict = chunker.create_all_chunks()
        all_chunks = chunks_dict["all_chunks"]

        print("🔗 Step 3: Embedding and indexing (FAISS)...")
        index_stats = index_chunks_with_ollama_faiss(
            all_chunks,
            persist_dir=persist_dir,
            index_name=index_name,
            model="nomic-embed-text",
            batch_size=16,
        )
        print(f"✅ Index complete: {index_stats}")
    else:
        print("🔗 Step 3: Embedding and indexing (FAISS)...")
        print("ℹ️ FAISS index already exists. Skipping re-indexing.")

    # Step 4
    print("💬 Step 4: RAG QA with qwen2.5:0.5b")
    sample_queries = ["Rule 2"]  # narrow to the exact rule
    for q in sample_queries:
        print(f"\n[Q] {q}")
        out = answer_query_with_rag(
            query=q,
            k=5,
            persist_dir="vector_store_faiss",
            index_name="soc_rag",
            embed_model="nomic-embed-text",
            gen_model="qwen2.5:0.5b",
        )
        # Also write to md
        from rag.retriever_qa import write_rule_markdown

        md_path = write_rule_markdown(
            query=q,
            out_dir=".",
            persist_dir="vector_store_faiss",
            index_name="soc_rag",
            embed_model="nomic-embed-text",
            gen_model="qwen2.5:0.5b",
        )
        print("[Answer]")
        print(out["answer"])
        print(f"\n✅ Markdown written to: {md_path}")
        print("\n[Context Preview]")
        print(out["context_preview"][:1200])

    return True


def main():
    success = quick_test_run()
    if success:
        print("\n" + "=" * 60)
        print("✅ SYSTEM IS WORKING!")
        print("=" * 60)
    else:
        print("\n❌ System test failed. Check the errors above.")


if __name__ == "__main__":
    main()
