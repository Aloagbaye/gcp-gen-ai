# Ingestion Pipeline Implementation Plan

## Overview

This plan breaks down the implementation of the document ingestion pipeline into manageable steps. The pipeline processes documents uploaded to GCS via `gsutil`, triggering a Cloud Function that extracts, chunks, embeds, and stores content in Vector Search and Neo4j.

## Architecture Flow

```
gsutil cp document.pdf gs://rag-vertex-ai-bucket/
    ↓
GCS OBJECT_FINALIZE event
    ↓
Pub/Sub Topic (rag-ingest)
    ↓
Cloud Function (rag-ingest-doc)
    ↓
┌─────────────────────────────────────────┐
│ 1. Extract Text (PDF/TXT/MD)          │
│ 2. Chunk Text (sentence-aware)         │
│ 3. Generate Embeddings (Vertex AI)     │
│ 4. Upsert to Vector Search             │
│ 5. Extract Entities (simple/LLM)       │
│ 6. Upsert to Neo4j Graph              │
└─────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Data Models & Schema (`schema.py`)

**Purpose**: Define data structures used throughout the pipeline

**Implementation**:
```python
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
```

**Testing**:
- Create test instances
- Verify serialization

**Dependencies**: None (foundation)

---

### Step 2: Text Extraction (`extract_text.py`)

**Purpose**: Extract text from PDF, TXT, and MD files

**Implementation Order**:
1. GCS client setup
2. File type detection
3. PDF extraction (using pypdf)
4. Text file extraction (TXT, MD)
5. Error handling

**Key Functions**:
```python
def extract_text(gcs_uri: str) -> dict:
    """
    Returns:
    {
        "text": "full document text",
        "metadata": {
            "file_type": "pdf",
            "page_count": 10,
            "title": "extracted title",
            "file_size": 1024000
        }
    }
    """
```

**Testing Strategy**:
- Upload test PDF to GCS
- Call function directly
- Verify text extraction
- Test error cases (corrupted files, unsupported types)

**Dependencies**: 
- `schema.py` (for DocumentMetadata)
- GCS access
- pypdf library

**Files to Create/Update**:
- `ingestion/processors/extract_text.py`

---

### Step 3: Text Chunking (`chunk.py`)

**Purpose**: Split text into overlapping chunks

**Implementation Order**:
1. Token counting (simple approximation)
2. Sentence splitting
3. Sentence-aware chunking
4. Overlap handling
5. Chunk ID generation

**Key Functions**:
```python
def chunk_text(text: str, doc_id: str, chunk_size: int = 600, overlap: int = 100) -> List[Chunk]:
    """
    Returns list of Chunk objects with:
    - chunk_id: "{doc_id}_chunk_{index}"
    - text: chunk text
    - text_preview: first 200 chars
    - chunk_index: position in document
    """
```

**Configuration**:
- Default: 600 tokens, 100 token overlap
- Can be adjusted via environment variables

**Testing Strategy**:
- Test with short text (< chunk_size)
- Test with long text (multiple chunks)
- Verify overlap works correctly
- Check chunk boundaries respect sentences

**Dependencies**:
- `schema.py` (Chunk model)

**Files to Create/Update**:
- `ingestion/processors/chunk.py`

---

### Step 4: Embedding Generation (`embed.py`)

**Purpose**: Generate vector embeddings for chunks

**Implementation Order**:
1. Vertex AI initialization
2. Batch embedding (efficient)
3. Attach embeddings to chunks
4. Error handling

**Key Functions**:
```python
def generate_embeddings(chunks: List[Chunk], project_id: str, region: str, model_name: str) -> List[ChunkWithEmbedding]:
    """
    Returns chunks with embeddings attached.
    Uses Vertex AI text-embedding-004 model.
    """
```

**Configuration**:
- Model: `text-embedding-004` (from env var)
- Batch size: 100 chunks per API call

**Testing Strategy**:
- Test with small batch (1-5 chunks)
- Test with larger batch (100+ chunks)
- Verify embedding dimensions (768)
- Check error handling (API failures)

**Dependencies**:
- `schema.py` (Chunk, ChunkWithEmbedding)
- Vertex AI access
- Environment variables

**Files to Create/Update**:
- `ingestion/processors/embed.py`

---

### Step 5: Vector Search Upsert (`upsert_vector.py`)

**Purpose**: Store chunk embeddings in Vertex AI Vector Search

**Implementation Order**:
1. Initialize Vector Search client
2. Format datapoints (id, embedding)
3. Batch upsert (100-1000 per batch)
4. Error handling and retries

**Key Functions**:
```python
def upsert_chunks(chunks: List[ChunkWithEmbedding], index_endpoint: str, deployed_index_id: str):
    """
    Upserts chunks to Vector Search.
    ID format: "{doc_id}::{chunk_id}"
    """
```

**Data Format**:
```python
datapoint = {
    "id": f"{doc_id}::{chunk_id}",  # e.g., "doc_123::chunk_0"
    "embedding": [0.1, -0.2, 0.3, ...]  # 768 dimensions
}
```

**Testing Strategy**:
- Test upsert with small batch
- Verify chunks appear in index
- Test query after upsert
- Handle duplicate IDs (update vs. error)

**Dependencies**:
- `schema.py` (ChunkWithEmbedding)
- Vector Search index endpoint
- Environment variables

**Files to Create/Update**:
- `ingestion/processors/upsert_vector.py`

---

### Step 6: Entity Extraction (Simple)

**Purpose**: Extract named entities from chunks for graph storage

**Implementation Order**:
1. Simple regex-based extraction (start)
2. Extract from all chunks
3. Normalize entity names
4. Classify entity types (optional)

**Key Functions**:
```python
def extract_entities(chunks: List[Chunk]) -> List[Entity]:
    """
    Extract entities from all chunks.
    Returns list of unique entities.
    """
```

**Simple Approach** (Phase 1):
- Regex: Capitalized words
- Basic deduplication
- Optional: Use Gemini for better extraction (Phase 2)

**Testing Strategy**:
- Test with text containing entities
- Verify deduplication works
- Check entity normalization

**Dependencies**:
- `schema.py` (Chunk, Entity)

**Files to Create/Update**:
- Can be in `main.py` initially, or separate `extract_entities.py`

---

### Step 7: Neo4j Graph Upsert (`upsert_graph.py`)

**Purpose**: Store document, chunks, and entities in Neo4j

**Implementation Order**:
1. Neo4j connection setup
2. Create/update Document node
3. Create Chunk nodes
4. Link Document → Chunks
5. Create Entity nodes
6. Link Chunks → Entities

**Key Functions**:
```python
def upsert_document_graph(
    doc_metadata: DocumentMetadata,
    chunks: List[Chunk],
    entities: List[Entity]
):
    """
    Creates/updates graph:
    - Document node
    - Chunk nodes (linked to Document)
    - Entity nodes (linked to Chunks)
    """
```

**Cypher Queries**:
```cypher
# Create Document
MERGE (d:Document {doc_id: $doc_id})
SET d.title = $title, d.gcs_uri = $gcs_uri, d.created_at = $created_at

# Create Chunk and link
MERGE (c:Chunk {chunk_id: $chunk_id})
SET c.chunk_index = $chunk_index, c.text_preview = $text_preview
MERGE (d)-[:HAS_CHUNK {order: $chunk_index}]->(c)

# Create Entity and link
MERGE (e:Entity {name: $name})
SET e.type = $type
MERGE (c)-[:MENTIONS]->(e)
```

**Testing Strategy**:
- Test with single document
- Verify nodes created correctly
- Check relationships
- Test duplicate handling (MERGE)

**Dependencies**:
- `schema.py` (DocumentMetadata, Chunk, Entity)
- Neo4j connection
- Environment variables

**Files to Create/Update**:
- `ingestion/processors/upsert_graph.py`

---

### Step 8: Main Function Integration (`main.py`)

**Purpose**: Orchestrate all processing steps

**Implementation Order**:
1. Import all processors
2. Wire up the pipeline
3. Error handling
4. Logging
5. Return status

**Key Implementation**:
```python
def ingest_document(event, context):
    # 1. Parse event
    gcs_uri = parse_event(event)
    doc_id = generate_doc_id(gcs_uri)
    
    try:
        # 2. Extract text
        extracted = extract_text.extract(gcs_uri)
        doc_metadata = DocumentMetadata(
            doc_id=doc_id,
            gcs_uri=gcs_uri,
            file_type=extracted["metadata"]["file_type"],
            ...
        )
        
        # 3. Chunk
        chunks = chunk.chunk_text(extracted["text"], doc_id)
        
        # 4. Embed
        chunks_with_embeddings = embed.generate_embeddings(
            chunks, PROJECT_ID, REGION, EMBEDDING_MODEL
        )
        
        # 5. Upsert to Vector Search
        upsert_vector.upsert_chunks(
            chunks_with_embeddings,
            VECTOR_INDEX_ENDPOINT,
            DEPLOYED_INDEX_ID
        )
        
        # 6. Extract entities
        entities = extract_entities(chunks)
        
        # 7. Upsert to Neo4j
        upsert_graph.upsert_document_graph(
            doc_metadata, chunks, entities
        )
        
        print(f"Success: {doc_id}, {len(chunks)} chunks")
        
    except Exception as e:
        print(f"Error processing {gcs_uri}: {e}")
        raise
```

**Testing Strategy**:
- End-to-end test with real document
- Test error handling at each step
- Verify data in both stores

**Dependencies**: All previous steps

**Files to Update**:
- `ingestion/function/main.py`

---

## Implementation Checklist

### Phase 1: Foundation (Steps 1-2)
- [ ] **Step 1**: Implement `schema.py` with data models
- [ ] **Step 2**: Implement `extract_text.py`
  - [ ] GCS client
  - [ ] PDF extraction
  - [ ] Text file extraction
  - [ ] Error handling
- [ ] **Test**: Upload PDF, verify text extraction

### Phase 2: Chunking & Embedding (Steps 3-4)
- [ ] **Step 3**: Implement `chunk.py`
  - [ ] Sentence splitting
  - [ ] Token-aware chunking
  - [ ] Overlap handling
- [ ] **Step 4**: Implement `embed.py`
  - [ ] Vertex AI client
  - [ ] Batch embedding
  - [ ] Error handling
- [ ] **Test**: Chunk text, generate embeddings, verify dimensions

### Phase 3: Storage (Steps 5-7)
- [ ] **Step 5**: Implement `upsert_vector.py`
  - [ ] Vector Search client
  - [ ] Batch upsert
  - [ ] Error handling
- [ ] **Step 6**: Implement entity extraction
  - [ ] Simple regex-based
  - [ ] Entity normalization
- [ ] **Step 7**: Implement `upsert_graph.py`
  - [ ] Neo4j connection
  - [ ] Document/Chunk/Entity nodes
  - [ ] Relationships
- [ ] **Test**: Upsert to both stores, verify data

### Phase 4: Integration (Step 8)
- [ ] **Step 8**: Wire up `main.py`
  - [ ] Import all processors
  - [ ] Orchestrate pipeline
  - [ ] Error handling
  - [ ] Logging
- [ ] **Test**: End-to-end with real document

### Phase 5: Testing & Validation
- [ ] **Unit Tests**: Each processor function
- [ ] **Integration Test**: Full pipeline
- [ ] **End-to-End Test**: Upload via gsutil, verify ingestion
- [ ] **Query Test**: Verify data appears in API queries

---

## Testing Workflow

### 1. Local Testing (Before Deployment)

**Test Each Component**:
```python
# Test extract_text
from processors.extract_text import extract_text
result = extract_text("gs://bucket/test.pdf")
print(result["text"][:100])

# Test chunking
from processors.chunk import chunk_text
chunks = chunk_text(result["text"], "test_doc")
print(f"Created {len(chunks)} chunks")

# Test embedding
from processors.embed import generate_embeddings
chunks_with_emb = generate_embeddings(chunks, PROJECT_ID, REGION, MODEL)
print(f"Embedding dim: {len(chunks_with_emb[0].embedding)}")
```

### 2. Cloud Function Testing

**Deploy and Test**:
```bash
# Upload test file
gsutil cp test.pdf gs://rag-vertex-ai-bucket/documents/

# Check Cloud Function logs
gcloud functions logs read rag-ingest-doc --region=us-central1 --limit=50
```

### 3. Verification

**Check Vector Search**:
```python
# Query the index
from google.cloud import aiplatform
endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=ENDPOINT)
results = endpoint.find_neighbors(...)
```

**Check Neo4j**:
```cypher
// Verify document
MATCH (d:Document {doc_id: "test_doc"})
RETURN d

// Verify chunks
MATCH (d:Document {doc_id: "test_doc"})-[:HAS_CHUNK]->(c:Chunk)
RETURN count(c)

// Verify entities
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
RETURN e.name, count(c) as mentions
ORDER BY mentions DESC
```

---

## File Structure After Implementation

```
ingestion/
├── function/
│   ├── main.py              # Orchestrates pipeline
│   └── requirements.txt     # Dependencies
└── processors/
    ├── schema.py            # Data models
    ├── extract_text.py      # Text extraction
    ├── chunk.py             # Text chunking
    ├── embed.py             # Embedding generation
    ├── upsert_vector.py     # Vector Search upsert
    └── upsert_graph.py      # Neo4j upsert
```

**Note**: Processors can be imported as modules:
```python
# In main.py
import sys
sys.path.append('/path/to/processors')
from processors import extract_text, chunk, embed, upsert_vector, upsert_graph
```

---

## Environment Variables (Already Set)

The Cloud Function already has these env vars configured:
- `PROJECT_ID`
- `REGION`
- `BUCKET_NAME`
- `VECTOR_INDEX_ENDPOINT`
- `DEPLOYED_INDEX_ID`
- `EMBEDDING_MODEL`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

---

## Recommended Implementation Order

1. **Start with `schema.py`** - Foundation for everything
2. **Then `extract_text.py`** - Get text from documents
3. **Then `chunk.py`** - Split into chunks
4. **Then `embed.py`** - Generate embeddings
5. **Then `upsert_vector.py`** - Store in Vector Search
6. **Then entity extraction** - Extract entities
7. **Then `upsert_graph.py`** - Store in Neo4j
8. **Finally `main.py`** - Wire everything together

**Why this order?**
- Each step builds on the previous
- Can test incrementally
- Dependencies flow naturally

---

## Quick Start: Minimal Working Example

For a quick test, implement in this order:

1. **schema.py** - Basic models
2. **extract_text.py** - PDF extraction only
3. **chunk.py** - Simple fixed-size chunking
4. **embed.py** - Single embedding call
5. **upsert_vector.py** - Single upsert
6. **main.py** - Wire together

Skip Neo4j initially, add it later. This gets you a working pipeline faster.

---

## Common Issues & Solutions

### Issue: Import Errors
**Solution**: Ensure processors are in Python path or use relative imports

### Issue: GCS Access Denied
**Solution**: Verify service account has `storage.objectViewer` role

### Issue: Vector Search Upsert Fails
**Solution**: 
- Check index endpoint is deployed
- Verify dimensions match (768)
- Check batch size (max 1000)

### Issue: Neo4j Connection Fails
**Solution**:
- Verify URI format (neo4j+s://...)
- Check credentials
- Test connection separately

### Issue: Timeout
**Solution**:
- Increase Cloud Function timeout (currently 120s)
- Process in smaller batches
- Consider async processing for large documents

---

## Next Steps After Implementation

1. **Add Error Handling**: Retry logic, dead-letter queue
2. **Add Monitoring**: Log metrics, track failures
3. **Optimize**: Batch processing, caching
4. **Enhance**: Better entity extraction (LLM-based)
5. **Scale**: Handle large documents, parallel processing

---

## Testing Commands

```bash
# Upload test document
gsutil cp test.pdf gs://rag-vertex-ai-bucket/documents/

# Check function logs
gcloud functions logs read rag-ingest-doc --region=us-central1 --limit=100

# Query API to verify data
curl -X POST https://rag-agent-api-cukcysp7ta-uc.a.run.app/search \
  -H "Content-Type: application/json" \
  -d '{"question": "test query", "top_k": 5}'
```

---

**Ready to start? Begin with Step 1 (`schema.py`) and work through each step sequentially!**
