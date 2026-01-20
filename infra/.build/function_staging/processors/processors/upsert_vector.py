import os
from typing import List
from google.cloud import aiplatform
from google.cloud.aiplatform import MatchingEngineIndex
from google.cloud.aiplatform_v1 import IndexServiceClient
from google.cloud.aiplatform_v1.types import IndexDatapoint, UpsertDatapointsRequest
from google.protobuf import struct_pb2

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
        index_endpoint: Full resource name of the index endpoint (used to get index ID)
        deployed_index_id: ID of the deployed index (e.g., "rag_chunks")
    
    Format:
        Datapoint ID: "{doc_id}::{chunk_id}"
        Embedding: 768-dimensional vector
        Metadata: text_preview stored in embedding_metadata
    """
    if not chunks:
        print("No chunks to upsert")
        return
    
    # Get the index ID from the endpoint
    # The index_endpoint format is: projects/{project}/locations/{location}/indexEndpoints/{endpoint_id}
    # We need to get the index resource name from the deployed index
    from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import MatchingEngineIndexEndpoint
    
    endpoint = MatchingEngineIndexEndpoint(index_endpoint_name=index_endpoint)
    
    # Get the index resource name from the deployed index
    deployed_index = None
    for di in endpoint.deployed_indexes:
        if di.id == deployed_index_id:
            deployed_index = di
            break
    
    if not deployed_index:
        raise ValueError(f"Deployed index '{deployed_index_id}' not found on endpoint")
    
    index_resource_name = deployed_index.index
    
    # Use REST API client directly for better metadata support
    # Initialize the REST client
    client = IndexServiceClient()
    
    # Prepare datapoints with metadata
    index_datapoints = []
    for chunk in chunks:
        datapoint_id = f"{chunk.doc_id}::{chunk.chunk_id}"
        
        # Create metadata struct (limit to 2KB per datapoint)
        metadata_dict = {
            "text_preview": chunk.text_preview[:2000] if len(chunk.text_preview) > 2000 else chunk.text_preview,
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id
        }
        metadata_struct = struct_pb2.Struct()
        metadata_struct.update(metadata_dict)
        
        # Create datapoint - try with metadata field
        # According to REST API docs, field is embeddingMetadata (camelCase in JSON)
        # In Python protobuf, it should be embedding_metadata (snake_case)
        try:
            datapoint = IndexDatapoint(
                datapoint_id=datapoint_id,
                feature_vector=chunk.embedding,
                embedding_metadata=metadata_struct
            )
        except (ValueError, TypeError) as e:
            # If embedding_metadata doesn't work, try creating without it and setting via attribute
            print(f"Warning: Could not create IndexDatapoint with embedding_metadata: {e}")
            print(f"Trying alternative approach...")
            
            # Create without metadata first
            datapoint = IndexDatapoint(
                datapoint_id=datapoint_id,
                feature_vector=chunk.embedding
            )
            
            # Try to set metadata as attribute (check what attributes exist)
            if len(index_datapoints) == 0:  # Debug first chunk only
                print(f"IndexDatapoint attributes: {[a for a in dir(datapoint) if not a.startswith('_')]}")
            
            # Try different possible field names
            for attr_name in ['embedding_metadata', 'embeddingMetadata', 'metadata']:
                if hasattr(datapoint, attr_name):
                    try:
                        setattr(datapoint, attr_name, metadata_struct)
                        print(f"Successfully set metadata via {attr_name}")
                        break
                    except Exception as e2:
                        print(f"Could not set {attr_name}: {e2}")
            else:
                print(f"Warning: No metadata field found. Continuing without metadata.")
        
        index_datapoints.append(datapoint)
    
    # Upsert in batches using REST API client
    batch_size = 100
    total_batches = (len(index_datapoints) + batch_size - 1) // batch_size
    
    for i in range(0, len(index_datapoints), batch_size):
        batch = index_datapoints[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        try:
            print(f"Upserting batch {batch_num}/{total_batches} ({len(batch)} datapoints)")
            
            # Use REST API client directly
            request = UpsertDatapointsRequest(
                index=index_resource_name,
                datapoints=batch
            )
            client.upsert_datapoints(request=request)
            
            print(f"Successfully upserted batch {batch_num}")
        except Exception as e:
            print(f"Error upserting batch {batch_num}: {e}")
            # Fallback: try using MatchingEngineIndex if REST client fails
            try:
                vector_index = MatchingEngineIndex(index_name=index_resource_name)
                vector_index.upsert_datapoints(datapoints=batch)
                print(f"Successfully upserted batch {batch_num} (fallback method)")
            except Exception as e2:
                print(f"Both methods failed. Error: {e2}")
                raise
    
    print(f"Successfully upserted {len(index_datapoints)} chunks to Vector Search")
