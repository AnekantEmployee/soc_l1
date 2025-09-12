# Create test_ollama_direct_fixed.py
import time
import ollama


def test_ollama_direct():
    """Test Ollama models directly with correct API usage"""

    print("🔍 Testing Ollama models...")

    try:
        # Test embedding model directly - use correct method
        print("\n🧪 Testing nomic-embed-text model...")
        start_time = time.time()

        # Use ollama.embed (not embeddings) with correct parameters
        response = ollama.embed(model="nomic-embed-text", input="test text")

        end_time = time.time()
        print(f"✅ Embedding successful! ({end_time - start_time:.2f}s)")

        # Check response structure
        if "embeddings" in response:
            embeddings = response["embeddings"]
            if embeddings and len(embeddings) > 0:
                print(f"   Embedding dimension: {len(embeddings[0])}")
            else:
                print("   ⚠️ Empty embeddings returned")
        else:
            print(f"   Response keys: {response.keys()}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_ollama_direct()
