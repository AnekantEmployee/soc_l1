import ollama
import time
from langchain.docstore.document import Document


class SimpleOllamaEmbeddings:
    """Minimal embedding class for testing"""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        print(f"🔧 Initializing embedding model: {self.model}")

    def embed_query(self, text: str) -> list:
        """Embed a single query with timing"""
        print(f"   Embedding query: '{text[:50]}...'")
        start_time = time.time()

        try:
            response = ollama.embed(model=self.model, input=text)
            end_time = time.time()

            if "embeddings" in response and response["embeddings"]:
                print(f"   ✅ Query embedded in {end_time - start_time:.2f}s")
                return response["embeddings"][0]
            else:
                print(f"   ❌ Empty embedding response")
                return [0.0] * 768

        except Exception as e:
            end_time = time.time()
            print(f"   ❌ Embedding failed in {end_time - start_time:.2f}s: {e}")
            return [0.0] * 768

    def embed_documents(self, texts: list) -> list:
        """Embed multiple documents with progress tracking"""
        print(f"   Embedding {len(texts)} documents...")
        embeddings = []

        for i, text in enumerate(texts):
            print(f"     Document {i+1}/{len(texts)}: '{text[:30]}...'")
            embedding = self.embed_query(text)
            embeddings.append(embedding)

            # Small delay to prevent overwhelming
            time.sleep(0.1)

        print(f"   ✅ Completed embedding {len(texts)} documents")
        return embeddings


def test_minimal_embedding():
    """Test minimal embedding functionality"""
    print("🧪 MINIMAL EMBEDDING TEST")
    print("=" * 50)

    try:
        # Test 1: Create embedding instance
        print("Step 1: Creating embedding instance...")
        embedder = SimpleOllamaEmbeddings()

        # Test 2: Single embedding
        print("\nStep 2: Testing single embedding...")
        single_result = embedder.embed_query("This is a test document")
        print(f"Single embedding dimension: {len(single_result)}")

        # Test 3: Batch embedding (small)
        print("\nStep 3: Testing small batch embedding...")
        test_docs = [
            "Document 1: This is about cybersecurity incidents",
            "Document 2: This covers authentication failures",
            "Document 3: This discusses vulnerability management",
        ]

        batch_results = embedder.embed_documents(test_docs)
        print(f"Batch embedding results: {len(batch_results)} embeddings")

        # Test 4: Simulate vector store addition
        print("\nStep 4: Simulating vector store addition...")
        docs = [
            Document(
                page_content=text, metadata={"source": f"test_{i}", "doc_type": "test"}
            )
            for i, text in enumerate(test_docs)
        ]

        print("Creating document embeddings...")
        start_time = time.time()

        for i, doc in enumerate(docs):
            print(f"  Processing document {i+1}/{len(docs)}...")
            embedding = embedder.embed_query(doc.page_content)
            print(f"    Embedding dimension: {len(embedding)}")

        end_time = time.time()
        print(f"✅ Processed {len(docs)} documents in {end_time - start_time:.2f}s")

        return True

    except Exception as e:
        print(f"❌ Minimal test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_ollama_models():
    """Test which Ollama models are actually working"""
    print("\n🔍 TESTING OLLAMA MODELS")
    print("=" * 50)

    try:
        models_response = ollama.list()
        models = models_response.get("models", [])

        print(f"Found {len(models)} models:")
        for model in models:
            name = model.get("name", "unknown")
            size = model.get("size", "unknown")
            print(f"  - {name} ({size})")

        # Test embedding model specifically
        embed_model = "nomic-embed-text"
        print(f"\nTesting {embed_model}...")

        # Multiple quick tests
        test_inputs = ["test", "hello world", "cybersecurity incident"]

        for i, test_input in enumerate(test_inputs):
            start_time = time.time()
            response = ollama.embed(model=embed_model, input=test_input)
            end_time = time.time()

            if "embeddings" in response:
                print(
                    f"  Test {i+1}: ✅ ({end_time - start_time:.2f}s) - {len(response['embeddings'][0])} dims"
                )
            else:
                print(f"  Test {i+1}: ❌ Invalid response format")

        return True

    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 MINIMAL EMBEDDING SYSTEM TEST")
    print("=" * 60)

    # Test 1: Ollama models
    if not test_ollama_models():
        print("❌ Ollama model test failed")
        exit(1)

    # Test 2: Minimal embedding
    if not test_minimal_embedding():
        print("❌ Minimal embedding test failed")
        exit(1)

    print("\n" + "=" * 60)
    print("✅ ALL MINIMAL TESTS PASSED!")
    print("=" * 60)
    print("\nIf this works but main.py hangs, the issue is likely:")
    print("- ChromaDB initialization")
    print("- Large batch processing")
    print("- Memory/resource constraints")
