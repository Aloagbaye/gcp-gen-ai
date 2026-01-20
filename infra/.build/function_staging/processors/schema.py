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
class ChunkWithEmbedding(Chunk):
    embedding: List[float]

@dataclass
class Entity:
    name: str
    type: str  # PERSON, ORGANIZATION, PRODUCT, LOCATION, etc.
