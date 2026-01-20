import base64
import json
import os
import sys
from pathlib import Path

# Add processors directory to path
# In Cloud Function deployment, processors/ is sibling to main.py
current_dir = Path(__file__).parent
processors_dir = current_dir / "processors"
sys.path.insert(0, str(processors_dir))

from processors.schema import DocumentMetadata
from processors import extract_text, chunk, embed, upsert_vector, extract_entities, upsert_graph

def generate_doc_id(gcs_uri: str) -> str:
    """Generate a unique document ID from GCS URI."""
    # Use the file path as doc_id (sanitized)
    # Format: gs://bucket/path/to/file.pdf -> path_to_file_pdf
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    if len(parts) > 1:
        doc_id = parts[1].replace("/", "_").replace(".", "_")
    else:
        doc_id = parts[0]
    
    # Remove any special characters
    doc_id = "".join(c if c.isalnum() or c == "_" else "_" for c in doc_id)
    return doc_id

def ingest_document(event, context):
    """
    Cloud Function entry point for document ingestion.
    
    Triggered by Pub/Sub message from GCS OBJECT_FINALIZE event.
    """
    try:
        # 1. Parse Pub/Sub message
        payload = base64.b64decode(event["data"]).decode("utf-8")
        msg = json.loads(payload)
        
        bucket = msg.get("bucket")
        name = msg.get("name")
        if not bucket or not name:
            print(f"Missing bucket/name in message: {msg}")
            return
        
        gcs_uri = f"gs://{bucket}/{name}"
        print(f"Ingestion triggered for: {gcs_uri}")
        
        # Generate document ID
        doc_id = generate_doc_id(gcs_uri)
        print(f"Document ID: {doc_id}")
        
        # Get environment variables
        PROJECT_ID = os.environ.get("PROJECT_ID")
        REGION = os.environ.get("REGION", "us-central1")
        EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")
        VECTOR_INDEX_ENDPOINT = os.environ.get("VECTOR_INDEX_ENDPOINT", "")
        DEPLOYED_INDEX_ID = os.environ.get("DEPLOYED_INDEX_ID", "")
        
        if not PROJECT_ID:
            raise ValueError("PROJECT_ID environment variable not set")
        
        # 2. Extract text
        print("Step 1: Extracting text...")
        extracted = extract_text.extract_text(gcs_uri)
        print(f"Extracted {len(extracted['text'])} characters")
        
        # Create document metadata
        doc_metadata = DocumentMetadata(
            doc_id=doc_id,
            gcs_uri=gcs_uri,
            file_type=extracted["metadata"]["file_type"],
            file_size=extracted["metadata"]["file_size"],
            title=extracted["metadata"].get("title"),
            page_count=extracted["metadata"].get("page_count")
        )
        
        # 3. Chunk text
        print("Step 2: Chunking text...")
        chunks = chunk.chunk_text(extracted["text"], doc_id)
        print(f"Created {len(chunks)} chunks")
        
        if not chunks:
            print("No chunks created, skipping embedding and upsert")
            return
        
        # 4. Generate embeddings
        print("Step 3: Generating embeddings...")
        chunks_with_embeddings = embed.generate_embeddings(
            chunks, 
            PROJECT_ID, 
            REGION, 
            EMBEDDING_MODEL
        )
        print(f"Generated {len(chunks_with_embeddings)} embeddings")
        
        # Verify embedding dimensions
        if chunks_with_embeddings:
            emb_dim = len(chunks_with_embeddings[0].embedding)
            print(f"Embedding dimension: {emb_dim}")
        
        # 5. Upsert to Vector Search
        if VECTOR_INDEX_ENDPOINT and DEPLOYED_INDEX_ID:
            print("Step 4: Upserting to Vector Search...")
            upsert_vector.upsert_chunks(
                chunks_with_embeddings,
                VECTOR_INDEX_ENDPOINT,
                DEPLOYED_INDEX_ID
            )
            print("Successfully upserted to Vector Search")
        else:
            print("Skipping Vector Search upsert (endpoint not configured)")
        
        # 6. Extract entities
        print("Step 5: Extracting entities...")
        entities = extract_entities.extract_entities(chunks)
        print(f"Extracted {len(entities)} unique entities")
        
        # 7. Upsert to Neo4j graph (non-blocking, won't fail ingestion)
        print("Step 6: Upserting to Neo4j graph...")
        upsert_graph.upsert_document_graph(doc_metadata, chunks, entities)
        print("Neo4j upsert completed (or skipped if not configured)")
        
        # Summary
        print(f"✅ Ingestion complete: {doc_id}")
        print(f"   - Chunks: {len(chunks)}")
        print(f"   - Entities: {len(entities)}")
        print(f"   - File type: {doc_metadata.file_type}")
        print(f"   - File size: {doc_metadata.file_size} bytes")
        
    except Exception as e:
        print(f"❌ Error processing {gcs_uri}: {e}")
        import traceback
        traceback.print_exc()
        raise
