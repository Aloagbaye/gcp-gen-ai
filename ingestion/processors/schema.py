from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class DocumentMetadata:
    doc_id: str
    gcs_uri: str
    file_type: str
    file_size: int
    title: Optional[str] = None
    page_count: Optional[int] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    text_preview: str  # First 200-300 chars
    page: Optional[int] = None
    token_count: Optional[int] = None

@dataclass
class ChunkWithEmbedding:
    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    text_preview: str  # First 200-300 chars
    embedding: List[float]
    page: Optional[int] = None
    token_count: Optional[int] = None
    
    @classmethod
    def from_chunk(cls, chunk: Chunk, embedding: List[float]) -> "ChunkWithEmbedding":
        """Create ChunkWithEmbedding from a Chunk and embedding."""
        return cls(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            text_preview=chunk.text_preview,
            embedding=embedding,
            page=chunk.page,
            token_count=chunk.token_count
        )

@dataclass
class Entity:
    name: str
    type: str  # PERSON, ORGANIZATION, PRODUCT, LOCATION, etc.
