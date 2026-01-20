import os
from typing import List
from google.cloud import aiplatform
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import MatchingEngineIndexEndpoint

# Import schema - handle both relative and absolute imports
try:
    from .schema import ChunkWithEmbedding
except ImportError:
    from schema import ChunkWithEmbedding

def upsert_chunks(
    chunks: List[ChunkWithEmbedding], 
    index_endpoint: str, 
    deployed_index_id: str
):
    """
    Upsert chunk embeddings to Vertex AI Vector Search index.
    
    Args:
        chunks: List of ChunkWithEmbedding objects
        index_endpoint: Full resource name of the index endpoint
        deployed_index_id: ID of the deployed index (e.g., "rag_chunks")
    
    Format:
        Datapoint ID: "{doc_id}::{chunk_id}"
        Embedding: 768-dimensional vector
    """
    if not chunks:
        print("No chunks to upsert")
        return
    
    # Initialize endpoint
    endpoint = MatchingEngineIndexEndpoint(index_endpoint_name=index_endpoint)
    
    # Prepare datapoints
    datapoints = []
    for chunk in chunks:
        datapoint_id = f"{chunk.doc_id}::{chunk.chunk_id}"
        datapoints.append({
            "id": datapoint_id,
            "embedding": chunk.embedding
        })
    
    # Upsert in batches (recommended: 100-1000 per batch)
    batch_size = 100
    total_batches = (len(datapoints) + batch_size - 1) // batch_size
    
    for i in range(0, len(datapoints), batch_size):
        batch = datapoints[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        try:
            print(f"Upserting batch {batch_num}/{total_batches} ({len(batch)} datapoints)")
            endpoint.upsert_datapoints(
                deployed_index_id=deployed_index_id,
                datapoints=batch
            )
            print(f"Successfully upserted batch {batch_num}")
        except Exception as e:
            print(f"Error upserting batch {batch_num}: {e}")
            raise
    
    print(f"Successfully upserted {len(datapoints)} chunks to Vector Search")
