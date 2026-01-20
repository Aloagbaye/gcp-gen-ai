import os
from typing import List
import vertexai
from vertexai.language_models import TextEmbeddingModel

# Import schema - handle both relative and absolute imports
try:
    from .schema import Chunk, ChunkWithEmbedding
except ImportError:
    from schema import Chunk, ChunkWithEmbedding

def generate_embeddings(
    chunks: List[Chunk], 
    project_id: str, 
    region: str, 
    model_name: str = "text-embedding-004"
) -> List[ChunkWithEmbedding]:
    """
    Generate vector embeddings for chunks using Vertex AI.
    
    Args:
        chunks: List of Chunk objects
        project_id: GCP project ID
        region: GCP region
        model_name: Embedding model name (default: text-embedding-004)
    
    Returns:
        List of ChunkWithEmbedding objects with embeddings attached
    """
    if not chunks:
        return []
    
    # Initialize Vertex AI
    vertexai.init(project=project_id, location=region)
    
    # Load embedding model
    model = TextEmbeddingModel.from_pretrained(model_name)
    
    # Prepare texts for batch embedding
    # Batch by token count (model limit: 20,000 tokens per request)
    # Use ~15,000 as safe limit to account for estimation errors
    MAX_TOKENS_PER_BATCH = 15000
    TOKEN_ESTIMATE_CHARS = 3  # More conservative: 1 token ≈ 3 characters (accounts for whitespace, punctuation)
    
    all_embeddings = []
    current_batch_texts = []
    current_batch_tokens = 0
    
    for chunk in chunks:
        # Estimate tokens for this chunk
        chunk_tokens = len(chunk.text) // TOKEN_ESTIMATE_CHARS
        
        # If adding this chunk would exceed limit, process current batch first
        if current_batch_tokens + chunk_tokens > MAX_TOKENS_PER_BATCH and current_batch_texts:
            try:
                print(f"Processing embedding batch: {len(current_batch_texts)} chunks, ~{current_batch_tokens} tokens")
                embeddings = model.get_embeddings(current_batch_texts)
                all_embeddings.extend([list(emb.values) for emb in embeddings])
            except Exception as e:
                print(f"Error generating embeddings for batch: {e}")
                raise
            
            # Reset batch
            current_batch_texts = []
            current_batch_tokens = 0
        
        # Add chunk to current batch
        current_batch_texts.append(chunk.text)
        current_batch_tokens += chunk_tokens
    
    # Process remaining batch
    if current_batch_texts:
        try:
            print(f"Processing final embedding batch: {len(current_batch_texts)} chunks, ~{current_batch_tokens} tokens")
            embeddings = model.get_embeddings(current_batch_texts)
            all_embeddings.extend([list(emb.values) for emb in embeddings])
        except Exception as e:
            print(f"Error generating embeddings for final batch: {e}")
            raise
    
    # Create ChunkWithEmbedding objects
    chunks_with_embeddings = []
    for chunk, embedding in zip(chunks, all_embeddings):
        chunk_with_emb = ChunkWithEmbedding.from_chunk(chunk, embedding)
        chunks_with_embeddings.append(chunk_with_emb)
    
    return chunks_with_embeddings
