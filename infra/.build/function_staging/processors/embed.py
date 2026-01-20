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
    texts = [chunk.text for chunk in chunks]
    
    # Generate embeddings in batches (Vertex AI handles batching internally)
    # But we'll do it in chunks of 100 to be safe
    batch_size = 100
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        try:
            embeddings = model.get_embeddings(batch_texts)
            all_embeddings.extend([list(emb.values) for emb in embeddings])
        except Exception as e:
            print(f"Error generating embeddings for batch {i}: {e}")
            raise
    
    # Create ChunkWithEmbedding objects
    chunks_with_embeddings = []
    for chunk, embedding in zip(chunks, all_embeddings):
        chunk_with_emb = ChunkWithEmbedding(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            text_preview=chunk.text_preview,
            page=chunk.page,
            token_count=chunk.token_count,
            embedding=embedding
        )
        chunks_with_embeddings.append(chunk_with_emb)
    
    return chunks_with_embeddings
