import os
import traceback
from rag.document_loader import DocumentLoader
from rag.document_chunker import DocumentChunker


def quick_test_run():
    """Quick test with minimal chunks"""
    print("=" * 50)
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
        return True

    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        traceback.print_exc()
        return False


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
