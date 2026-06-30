import os
import time

# ponytail: mock Pinecone ingester, upgrade to real Pinecone API credentials & active embedding client (e.g. OpenAI / Vertex AI)
class DocumentVectorIngester:
    def __init__(self, index_name="saarthi-kb"):
        self.index_name = index_name
        self.docs_catalog = [
            {
                "title": "RBI Fair Practices Code (FPC) Guidelines 2024",
                "content": "Lenders must disclose all loan terms, interest rates p.a., processing fees, and foreclosure charges transparently. Cross-selling products without explicit opt-in consent is strictly prohibited.",
                "category": "Compliance"
            },
            {
                "title": "SBI Digital Banking Migration Manual",
                "content": "To reduce branch counter friction, customers executing manual counter transactions should be guided toward digital equivalents (e.g., self-service deposits, digital sweep, and YONO Pay transfers).",
                "category": "Operations"
            },
            {
                "title": "SBI Pre-Approved Debt Consolidation Personal Loan Guidelines",
                "content": "Customers paying high interest rates on credit cards (>36% p.a.) with an active savings account in good standing qualify for debt consolidation personal loans at 10.50% p.a. fixed interest.",
                "category": "Products"
            }
        ]

    def connect_vector_db(self):
        print(f"Connecting to Pinecone Vector DB...")
        time.sleep(1.0) # Mock network handshake
        print(f"Index status: Active ({self.index_name})")
        return True

    def ingest_documents(self):
        print(f"\nStarting ingestion pipeline for {len(self.docs_catalog)} document sections...")
        self.connect_vector_db()
        
        for i, doc in enumerate(self.docs_catalog):
            print(f" -> Processing: '{doc['title']}'")
            # Simulating generating embeddings (mock vector representation)
            time.sleep(0.5)
            vector_dims = [round(0.12 * (i + 1), 4) for _ in range(1536)] # mock 1536-dim vector
            
            payload = {
                "id": f"doc-chunk-{i}",
                "values": vector_dims[:10], # showing truncated vector dimensions for logging
                "metadata": {
                    "title": doc["title"],
                    "category": doc["category"],
                    "snippet": doc["content"][:80] + "..."
                }
            }
            print(f"    Upserted chunk to namespace 'sbi-policy': {json_repr(payload)}")
            
        print("\nAll documents vectorized and indexed successfully inside Pinecone!")

def json_repr(d):
    import json
    return json.dumps(d, indent=2)

if __name__ == "__main__":
    ingester = DocumentVectorIngester()
    ingester.ingest_documents()
