import json
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_ollama import OllamaEmbeddings
from qdrant_client.models import PayloadSchemaType

COLLECTION_NAME = "contract_clauses"

# ---------- Qdrant ----------
client = QdrantClient(url="http://localhost:6333")

# client.delete_collection(COLLECTION_NAME)
# print("Deleted existing collection")


try:
    client.get_collection(COLLECTION_NAME)
    print(f"Collection '{COLLECTION_NAME}' already exists.")
except Exception:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )
    client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="contract_type",
    field_schema=PayloadSchemaType.KEYWORD
    )
    print(f"Created collection '{COLLECTION_NAME}'.")

# ---------- Embeddings ----------
embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

vectorstore = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings
)

# ---------- Load clause.json ----------
with open("clause.json", "r") as f:
    data = json.load(f)

documents = []
for contract in data:
    contract_type = contract["contract_type"]
    for clause in contract["clauses"]:
        doc = Document(
            page_content=clause["clause_text"],
            metadata={
                "contract_type": contract_type,
                "clause_title": clause["clause_title"],
                "jurisdiction": clause["metadata"]["jurisdiction"]
            }
        )
        documents.append(doc)



# ---------- Ingest ----------
if __name__ == "__main__":
    vectorstore.add_documents(documents)
    print(f"Ingested {len(documents)} clauses into Qdrant.")

