from pydantic import BaseModel, Field
from typing import List, Optional

class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: Optional[int] = None

class Citation(BaseModel):
    chunk_id: str
    doc_id: str
    source: str
    score: float
    text_preview: str

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]

class SearchResponse(BaseModel):
    results: List[Citation]
