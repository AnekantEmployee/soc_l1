import os
import ollama
import traceback
from rag.vector_store import SOCVectorStore
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker


def quick_test_run():
    """Quick test with minimal chunks"""
    print("🚀 QUICK RAG TEST RUN")
    print("=" * 50)

    # Configuration
    tracker_path = "Client1 - Q2 - Daily Incident Tracker_Dashboard  - Apr to Jun 2025(July 25).csv"
    rulebook_dir = "rulebooks/"

    # Check if files exist
    if not os.path.exists(tracker_path):
        print(f"❌ Tracker file not found: {tracker_path}")
        return False

    if not os.path.exists(rulebook_dir):
        print(f"❌ Rulebook directory not found: {rulebook_dir}")
        return False

    try:
        # Step 1: Load documents
        print("📁 Step 1: Loading documents...")
        loader = DocumentLoader(tracker_path=tracker_path, rulebook_dir=rulebook_dir)
        tracker_df, rulebook_dfs = loader.load_all_documents()

        # Step 2: Create chunks (LIMITED)
        print("📝 Step 2: Creating document chunks...")
        chunker = DocumentChunker(tracker_df, rulebook_dfs)
        chunks_dict = chunker.create_all_chunks()

        # LIMIT TO FIRST 10 CHUNKS FOR TESTING
        all_chunks = chunks_dict["all_chunks"]
        test_chunks = all_chunks[:10]  # Only use first 10 chunks

        print(
            f"Using {len(test_chunks)} chunks out of {len(all_chunks)} total for testing"
        )

        # Step 3: Initialize vector store
        print("🔗 Step 3: Setting up vector store...")
        vector_store = SOCVectorStore(
            persist_directory="./quick_test_db",
            collection_name="quick_test_collection",
        )

        # Step 4: Add chunks
        print("📚 Step 4: Adding chunks to vector store...")
        was_added = vector_store.add_chunks_once(
            chunks=test_chunks,
            force_recreate=True,  # Always recreate for testing
            batch_size=1,  # One by one
        )

        if was_added:
            print("✅ Chunks successfully added to vector store")
        else:
            print("❌ Failed to add chunks")
            return False

        # Step 5: Test search
        print("🔍 Step 5: Testing search functionality...")
        test_query = "authentication failure"
        results = vector_store.similarity_search(test_query, k=3)

        print(f"Search results for '{test_query}': {len(results)} found")
        for i, result in enumerate(results):
            source = result.metadata.get("source", "unknown")
            doc_type = result.metadata.get("doc_type", "unknown")
            content_preview = result.page_content[:100]
            print(f"  {i+1}. [{doc_type}] {source}: {content_preview}...")

        # Step 6: Test with LLM (if chat model available)
        print("🤖 Step 6: Testing LLM integration...")

        try:
            # Simple context building
            context_parts = []
            for result in results[:2]:  # Use top 2 results
                context_parts.append(result.page_content)

            context = "\n\n".join(context_parts)

            prompt = f"""Based on this SOC context, answer the question:

CONTEXT:
{context}

QUESTION: {test_query}

ANSWER:"""

            # Try to use LLM
            chat_model = os.getenv("OLLAMA_CHAT", "llama3.2:1b")  # Try a smaller model

            response = ollama.chat(
                model=chat_model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": 2048},  # Limit context
            )

            answer = response["message"]["content"][:300] + "..."
            print(f"LLM Answer: {answer}")

        except Exception as llm_error:
            print(f"LLM test skipped: {llm_error}")

        print("\n✅ QUICK TEST COMPLETED SUCCESSFULLY!")
        return True

    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("🧪 SIMPLIFIED RAG SYSTEM TEST")
    print("=" * 60)

    # Run quick test first
    success = quick_test_run()

    if success:
        print("\n" + "=" * 60)
        print("✅ SYSTEM IS WORKING!")
        print("=" * 60)
        print("\nTo run with all chunks, modify test_chunks = all_chunks")
        print("Current version uses only first 10 chunks for speed")
    else:
        print("\n❌ System test failed. Check the errors above.")


if __name__ == "__main__":
    main()
