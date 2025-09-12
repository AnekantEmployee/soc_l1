# Create test_ollama_direct_fixed.py
import time
import ollama


def test_ollama_direct():
    """Test Ollama models directly with correct API usage"""

    print("🔍 Testing Ollama models...")

    try:
        # List models - use correct structure
        models_response = ollama.list()
        models = models_response.get("models", [])

        print(f"Available models: {len(models)} found")
        for model in models:
            model_name = model.get("name", "unknown")
            print(f"   - {model_name}")

        # Check if nomic-embed-text is available
        model_names = [model.get("name", "") for model in models]

        if "nomic-embed-text" not in model_names:
            print("⚠️ nomic-embed-text not found. Trying to pull...")
            try:
                ollama.pull("nomic-embed-text")
                print("✅ nomic-embed-text pulled successfully")
            except Exception as pull_error:
                print(f"❌ Failed to pull nomic-embed-text: {pull_error}")
                return False

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
