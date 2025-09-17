import os
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker
from rag.context_retriever import retrieve_context
from rag.response_generator import (
    generate_response_with_llm,
    write_rule_markdown,
)
from rag.embedding_indexer import (
    index_chunks_with_ollama_faiss,
    faiss_index_exists,
)

os.environ.setdefault("OLLAMA_TIMEOUT", "120")


def quick_test_run():
    print("=" * 50)
    print("🚀 ENHANCED RAG TEST RUN - TWO PHASE PROCESSING")
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

    print("\n" + "=" * 60)
    print("🔍 Step 4A: CONTEXT RETRIEVAL PHASE")
    print("🤖 Step 4B: RESPONSE GENERATION PHASE")
    print("=" * 60)

    sample_queries = [
        "Rule 2",
        "Rule 014",
        "User Assigned Privileged Role",
        "Passwordless authentication may be happen due to compromised account or privileged account.",
    ]

    for query_idx, q in enumerate(sample_queries, 1):
        print(f"\n{'='*50}")
        print(f"[Query {query_idx}] {q}")
        print("=" * 50)

        # PHASE A: Context Retrieval
        print("🔍 Phase A: Retrieving context...")
        context_results = retrieve_context(
            query=q,
            persist_dir=persist_dir,
            index_name=index_name,
            embed_model="nomic-embed-text",
            k_tracker=2,
            k_rulebook=5,
        )

        print(f"✅ Context retrieved:")
        print(f"   📊 Tracker hits: {len(context_results.get('tracker', []))}")
        print(f"   📚 Rulebook hits: {len(context_results.get('rulebook', []))}")
        print(f"   🎯 Query classification: {context_results.get('class', {})}")

        # PHASE B: Response Generation
        print("\n🤖 Phase B: Generating response...")
        answer_md = generate_response_with_llm(
            query=q,
            context_results=context_results,
            model="qwen2.5:0.5b",
        )

        # Write markdown file
        md_path = write_rule_markdown(query=q, answer=answer_md, out_dir="artifacts")

        print(f"✅ Response generated:")
        print(f"   📄 Markdown written to: {md_path}")

        print(f"\n[Generated Answer]")
        print("-" * 40)
        print(answer_md)
        print("-" * 40)

        # Summary for this query
        print(f"\n📋 Query {query_idx} Summary:")
        print(
            f"   🔍 Context retrieval: ✅ ({len(context_results.get('tracker', []))} tracker + {len(context_results.get('rulebook', []))} rulebook hits)"
        )
        print(f"   🤖 Response generation: ✅")
        print(
            f"   💾 Files created: {os.path.basename(context_path)}, {os.path.basename(md_path)}"
        )

    return True


def main():
    ok = quick_test_run()
    if ok:
        print("\n" + "=" * 60)
        print("✅ ENHANCED TWO-PHASE SYSTEM IS WORKING!")
        print("=" * 60)
        print("📊 System Features:")
        print("   🔍 Phase A: Advanced context retrieval with dynamic rule mapping")
        print("   🤖 Phase B: LLM response generation with structured prompts")
        print("   💾 Separate file outputs for contexts and responses")
        print("   🎯 Enhanced query classification and rule detection")
        print("   📈 Improved scoring and relevance filtering")
    else:
        print("\n❌ System test failed. Check the errors above.")


if __name__ == "__main__":
    main()
