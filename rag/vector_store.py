import os
from typing import List, Dict, Any, Optional
from langchain.docstore.document import Document
from langchain_chroma import Chroma
import traceback
import chromadb
from chromadb.config import Settings
import ollama
import time


class SOCVectorStore:
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "soc_documents",
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model = os.getenv("OLLAMA_EMBEDDINGS", "nomic-embed-text")

        # Custom embedding function that uses ollama directly
        self.embeddings = CustomOllamaEmbeddings(model=self.embedding_model)
        self._initialize_vectorstore()

    def _initialize_vectorstore(self):
        os.makedirs(self.persist_directory, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

        self.vectorstore = Chroma(
            client=self.client,
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )

    def check_if_populated(self) -> bool:
        try:
            collection = self.client.get_collection(self.collection_name)
            return collection.count() > 0
        except:
            return False

    def add_chunks_once(
        self, chunks: List[Document], force_recreate: bool = False, batch_size: int = 5
    ) -> bool:
        """Add chunks to vector store in smaller batches"""
        if not chunks:
            print("⚠️ No chunks provided to add")
            return False

        # Check if already populated
        if not force_recreate and self.check_if_populated():
            print("ℹ️ Vector store already populated, skipping addition")
            return False

        # Reset if forced
        if force_recreate:
            print("🔄 Force recreating vector store...")
            self._reset_vectorstore()

        try:
            print(f"📝 Adding {len(chunks)} chunks in batches of {batch_size}...")
            total_added = 0

            # Process chunks in small batches
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(chunks) + batch_size - 1) // batch_size

                print(
                    f"  Processing batch {batch_num}/{total_batches}: {len(batch)} chunks"
                )

                try:
                    # Prepare data for this batch
                    texts = [chunk.page_content for chunk in batch]
                    metadatas = [chunk.metadata for chunk in batch]

                    # Create unique IDs
                    ids = []
                    for j, chunk in enumerate(batch):
                        doc_type = chunk.metadata.get("doc_type", "unknown")
                        source = chunk.metadata.get("source", "unknown")[
                            :20
                        ]  # Truncate long names
                        chunk_id = f"{doc_type}_{source}_{i+j}".replace(
                            " ", "_"
                        ).replace(".", "_")
                        ids.append(chunk_id)

                    # Add batch to vector store
                    self.vectorstore.add_texts(
                        texts=texts, metadatas=metadatas, ids=ids
                    )

                    total_added += len(batch)
                    print(f"  ✅ Batch {batch_num} completed ({len(batch)} chunks)")

                except Exception as batch_error:
                    print(f"  ❌ Error in batch {batch_num}: {batch_error}")
                    continue

            print(
                f"✅ Successfully added {total_added}/{len(chunks)} chunks to vector store"
            )

            # Verify addition
            final_count = self.get_document_count()
            print(f"📊 Vector store now contains {final_count} documents")

            return total_added > 0

        except Exception as e:
            print(f"❌ Error adding chunks to vector store: {e}")
            traceback.print_exc()
            return False

    def _reset_vectorstore(self):
        try:
            self.client.delete_collection(self.collection_name)
        except:
            pass
        self._initialize_vectorstore()

    def similarity_search(
        self, query: str, k: int = 5, filter_dict: Optional[Dict] = None
    ) -> List[Document]:
        if filter_dict:
            return self.vectorstore.similarity_search(
                query=query, k=k, filter=filter_dict
            )
        return self.vectorstore.similarity_search(query=query, k=k)

    def search_tracker_only(self, query: str, k: int = 5) -> List[Document]:
        return self.similarity_search(query, k, filter_dict={"doc_type": "tracker_row"})

    def search_rulebooks_only(self, query: str, k: int = 5) -> List[Document]:
        return self.similarity_search(query, k, filter_dict={"doc_type": "rulebook"})

    def get_document_count(self) -> int:
        """Get total document count in vector store"""
        try:
            if not self.check_if_populated():
                return 0
            collection = self.client.get_collection(self.collection_name)
            return collection.count()
        except Exception as e:
            print(f"Error getting document count: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get basic vector store statistics"""
        try:
            if not self.check_if_populated():
                return {"total_documents": 0, "status": "empty"}

            collection = self.client.get_collection(self.collection_name)
            total_count = collection.count()

            return {
                "total_documents": total_count,
                "embedding_model": self.embedding_model,
                "status": "populated",
            }

        except Exception as e:
            return {"error": str(e), "status": "error"}


class CustomOllamaEmbeddings:
    """Custom embedding class that uses ollama.embed directly"""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self._ensure_model_available()

    def _ensure_model_available(self):
        """Ensure the embedding model is available"""
        try:
            models_response = ollama.list()
            models = models_response.get("models", [])
            model_names = [model.get("name", "") for model in models]

            if self.model not in model_names:
                print(f"⚠️ {self.model} not found. Trying to pull...")
                ollama.pull(self.model)
                print(f"✅ {self.model} pulled successfully")
        except Exception as e:
            print(f"❌ Error ensuring model availability: {e}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents"""
        embeddings = []
        for text in texts:
            try:
                response = ollama.embed(model=self.model, input=text)
                if "embeddings" in response and response["embeddings"]:
                    embeddings.append(response["embeddings"][0])
                else:
                    print(f"Warning: Empty embedding for text: {text[:50]}...")
                    embeddings.append([0.0] * 768)  # Default 768-dim zero vector
            except Exception as e:
                print(f"Error embedding text: {e}")
                embeddings.append([0.0] * 768)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query"""
        try:
            response = ollama.embed(model=self.model, input=text)
            if "embeddings" in response and response["embeddings"]:
                return response["embeddings"][0]
            else:
                print(f"Warning: Empty embedding for query: {text[:50]}...")
                return [0.0] * 768
        except Exception as e:
            print(f"Error embedding query: {e}")
            return [0.0] * 768
