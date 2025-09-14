import os
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker
from rag.retriever_qa import answer_query_with_rag, write_rule_markdown
from rag.embedding_indexer import (
    index_chunks_with_ollama_faiss,
    faiss_index_exists,
)

os.environ.setdefault("OLLAMA_TIMEOUT", "120")


def quick_test_run():
    print("=" * 50)
    print("🚀 QUICK RAG TEST RUN")
    print("=" * 50)

    persist_dir = "vector_store_faiss"
    index_name = "soc_rag"

    tracker_path = "Client1 - Q2 - Daily Incident Tracker_Dashboard  - Apr to Jun 2025(July 25).csv"
    rulebook_dir = "rulebooks/"

    need_build = not faiss_index_exists(persist_dir=persist_dir, index_name=index_name)

    if need_build:
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

        print("💾 Step 2a: Saving chunks to file...")
        os.makedirs("artifacts", exist_ok=True)
        chunks_dump_path = chunker.export_chunks_to_text(
            chunks_dict,
            out_path="artifacts/all_chunks_dump.txt",
            max_chars_per_chunk=4000,
        )
        print(f"✅ Chunks dump written: {chunks_dump_path}")

        print("🔑 Step 2b: Export rule keys (rule id + alert name) ...")
        rule_keys_path = chunker.export_rule_keys(out_path="artifacts/rule_keys.json")
        print(f"✅ Rule keys exported: {rule_keys_path}")

        print("🔗 Step 3: Embedding and indexing (FAISS content)...")
        index_stats = index_chunks_with_ollama_faiss(
            chunks_dict["all_chunks"],
            persist_dir=persist_dir,
            index_name=index_name,
            model="nomic-embed-text",
            batch_size=16,
        )
        print(f"✅ Content index complete: {index_stats}")
    else:
        print("ℹ️ FAISS content index already exists. Skipping re-indexing.")

    print("💬 Step 4: RAG QA with qwen2.5:0.5b")
    sample_queries = [
        "Rule 2",
        "Rule 014",
        "User Assigned Privileged Role",
        "Paswordless aunthintication may be happen due to compromised account or privileged account.
"
    ]

    for q in sample_queries:
        print(f"\n[Q] {q}")
        out = answer_query_with_rag(
            query=q,
            k=5,
            persist_dir=persist_dir,
            index_name=index_name,
            embed_model="nomic-embed-text",
            gen_model="qwen2.5:0.5b",
        )

        md_path = write_rule_markdown(
            query=q,
            out_dir="artifacts",
            persist_dir=persist_dir,
            index_name=index_name,
            embed_model="nomic-embed-text",
            gen_model="qwen2.5:0.5b",
        )

        print("[Answer]")
        print(out["answer"])
        print(f"\n✅ Markdown written to: {md_path}")
        print(f"🧾 Context saved to: {out.get('context_saved_to')}")
        print("\n[Context Preview]")
        print(out["context_preview"][:1200])

    return True


def main():
    ok = quick_test_run()
    if ok:
        print("\n" + "=" * 60)
        print("✅ SYSTEM IS WORKING!")
        print("=" * 60)
    else:
        print("\n❌ System test failed. Check the errors above.")


if __name__ == "__main__":
    main()
