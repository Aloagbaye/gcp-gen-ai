import re
from typing import List

# Import schema - handle both relative and absolute imports
try:
    from .schema import Chunk
except ImportError:
    from schema import Chunk

def count_tokens_approx(text: str) -> int:
    """
    Approximate token count.
    Rule of thumb: 1 token ≈ 0.75 words ≈ 4 characters
    """
    # Simple approximation: characters / 4
    return len(text) // 4

def split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    # Pattern: sentence ending followed by whitespace
    pattern = r'(?<=[.!?])\s+'
    sentences = re.split(pattern, text)
    # Filter out empty sentences
    return [s.strip() for s in sentences if s.strip()]

def chunk_text(
    text: str, 
    doc_id: str, 
    chunk_size: int = 600, 
    overlap: int = 100
) -> List[Chunk]:
    """
    Split text into overlapping chunks using sentence-aware chunking.
    
    Args:
        text: Full document text
        doc_id: Document identifier
        chunk_size: Target chunk size in tokens
        overlap: Overlap size in tokens
    
    Returns:
        List of Chunk objects with:
        - chunk_id: "{doc_id}_chunk_{index}"
        - text: chunk text
        - text_preview: first 200 chars
        - chunk_index: position in document
    """
    sentences = split_sentences(text)
    
    if not sentences:
        # Fallback: return single chunk with entire text
        return [Chunk(
            chunk_id=f"{doc_id}_chunk_0",
            doc_id=doc_id,
            chunk_index=0,
            text=text,
            text_preview=text[:200],
            token_count=count_tokens_approx(text)
        )]
    
    chunks = []
    current_chunk = []
    current_size = 0
    chunk_index = 0
    
    for sentence in sentences:
        sentence_tokens = count_tokens_approx(sentence)
        
        # If adding this sentence would exceed chunk size and we have content
        if current_size + sentence_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunk_text_content = " ".join(current_chunk)
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_chunk_{chunk_index}",
                doc_id=doc_id,
                chunk_index=chunk_index,
                text=chunk_text_content,
                text_preview=chunk_text_content[:200],
                token_count=current_size
            ))
            
            # Start new chunk with overlap
            # Calculate how many sentences to keep for overlap
            overlap_tokens = overlap
            overlap_sentences = []
            overlap_size = 0
            
            # Add sentences backwards until we reach overlap size
            for s in reversed(current_chunk):
                s_tokens = count_tokens_approx(s)
                if overlap_size + s_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_size += s_tokens
                else:
                    break
            
            # Start new chunk with overlap + current sentence
            current_chunk = overlap_sentences + [sentence]
            current_size = overlap_size + sentence_tokens
            chunk_index += 1
        else:
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_size += sentence_tokens
    
    # Add final chunk
    if current_chunk:
        chunk_text_content = " ".join(current_chunk)
        chunks.append(Chunk(
            chunk_id=f"{doc_id}_chunk_{chunk_index}",
            doc_id=doc_id,
            chunk_index=chunk_index,
            text=chunk_text_content,
            text_preview=chunk_text_content[:200],
            token_count=current_size
        ))
    
    return chunks
