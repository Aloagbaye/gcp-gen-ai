# Hybrid RAG System Tutorial: Building Production-Ready Retrieval-Augmented Generation on GCP

## Table of Contents

1. [Introduction & Architecture Overview](#introduction--architecture-overview)
2. [Understanding RAG Fundamentals](#understanding-rag-fundamentals)
3. [Why Hybrid RAG? Vector Search + Graph Knowledge](#why-hybrid-rag-vector-search--graph-knowledge)
4. [Project Structure & Component Breakdown](#project-structure--component-breakdown)
5. [Step 1: Infrastructure Setup with Terraform](#step-1-infrastructure-setup-with-terraform)
6. [Step 2: Data Models & Schema Design](#step-2-data-models--schema-design)
7. [Step 3: Document Ingestion Pipeline](#step-3-document-ingestion-pipeline)
8. [Step 4: Vector Search with Vertex AI](#step-4-vector-search-with-vertex-ai)
9. [Step 5: Graph Database with Neo4j](#step-5-graph-database-with-neo4j)
10. [Step 6: Hybrid Retrieval Strategy](#step-6-hybrid-retrieval-strategy)
11. [Step 7: Query Processing & Answer Generation](#step-7-query-processing--answer-generation)
12. [Step 8: Deployment & Operations](#step-8-deployment--operations)
13. [Advanced Topics & Extensions](#advanced-topics--extensions)

---

## Introduction & Architecture Overview

### What is This Project?

This project implements a **Hybrid Retrieval-Augmented Generation (RAG)** system on Google Cloud Platform. It combines:

- **Vector Search** (semantic similarity) via Vertex AI Vector Search
- **Graph Traversal** (structured relationships) via Neo4j
- **LLM Generation** via Vertex AI Gemini models

The system ingests documents, extracts knowledge, and answers questions with citations.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Upload                              │
│                    (PDF, TXT, MD, Images)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Google Cloud Storage                          │
│              (Document Storage Bucket)                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ OBJECT_FINALIZE event
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cloud Pub/Sub Topic                           │
│              (Event Notification Queue)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Cloud Function (Gen 2)                              │
│              Ingestion Pipeline                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Extract Text/Images                                    │  │
│  │ 2. Chunk Text (overlapping windows)                      │  │
│  │ 3. Generate Embeddings (Vertex AI)                      │  │
│  │ 4. Upsert to Vector Search Index                          │  │
│  │ 5. Extract Entities                                      │  │
│  │ 6. Upsert to Neo4j Graph                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────┬───────────────────────────────┬─────────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   Vertex AI Vector Search    │  │      Neo4j Graph Database     │
│   (Semantic Similarity)      │  │   (Entity Relationships)      │
│                              │  │                              │
│  - Chunk Embeddings          │  │  - Documents                 │
│  - Similarity Search         │  │  - Chunks                    │
│  - Top-K Retrieval           │  │  - Entities                  │
│                              │  │  - Relationships             │
└──────────────────────────────┘  └──────────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cloud Run Service                            │
│              FastAPI RAG Agent API                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Receive Query                                         │  │
│  │ 2. Generate Query Embedding                             │  │
│  │ 3. Vector Search (top-K chunks)                         │  │
│  │ 4. Extract Query Entities                               │  │
│  │ 5. Graph Expansion (entity-based)                        │  │
│  │ 6. Merge & Re-rank Results                              │  │
│  │ 7. Generate Answer with Gemini                          │  │
│  │ 8. Return Answer + Citations                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         User Response                            │
│              Answer + Source Citations                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Event-Driven Ingestion**: Automatic processing when documents are uploaded
2. **Hybrid Retrieval**: Combines semantic (vector) and structural (graph) search
3. **Scalable Architecture**: Serverless functions and managed services
4. **Citation Tracking**: Every answer includes source references
5. **Separation of Concerns**: Ingestion vs. query processing

---

## Understanding RAG Fundamentals

### What is RAG?

**Retrieval-Augmented Generation (RAG)** is a technique that enhances LLM responses by:

1. **Retrieving** relevant context from a knowledge base
2. **Augmenting** the LLM prompt with this context
3. **Generating** answers grounded in the retrieved information

### Why RAG?

**Problem**: LLMs have knowledge cutoffs and can hallucinate.

**Solution**: RAG provides:
- ✅ **Up-to-date information** (documents can be updated)
- ✅ **Domain-specific knowledge** (your documents)
- ✅ **Reduced hallucinations** (answers grounded in sources)
- ✅ **Transparency** (citations show sources)

### Traditional RAG Flow

```
Query → Embed Query → Vector Search → Retrieve Top-K → Prompt LLM → Answer
```

**Limitations**:
- Only finds semantically similar text
- Misses relationships between concepts
- Can't traverse entity connections

### Hybrid RAG Flow (This Project)

```
Query → Embed Query → Vector Search ──┐
       ↓                              ├─→ Merge & Re-rank → Prompt LLM → Answer
       Extract Entities → Graph Search ┘
```

**Advantages**:
- ✅ Semantic similarity (vector search)
- ✅ Relationship traversal (graph search)
- ✅ Better recall (finds related concepts)
- ✅ More accurate answers

---

## Why Hybrid RAG? Vector Search + Graph Knowledge

### Vector Search: Semantic Similarity

**How it works**:
1. Text is converted to dense vectors (embeddings)
2. Similar texts have similar vectors
3. Search finds nearest neighbors in vector space

**Strengths**:
- Finds semantically similar content
- Works well for paraphrased queries
- Handles synonyms and related concepts

**Limitations**:
- Misses explicit relationships (e.g., "Company A acquired Company B")
- Can't traverse multi-hop connections
- Struggles with rare entities

### Graph Search: Relationship Traversal

**How it works**:
1. Entities are extracted from documents
2. Relationships are modeled as edges
3. Queries traverse the graph structure

**Strengths**:
- Captures explicit relationships
- Multi-hop reasoning (A → B → C)
- Entity-centric queries work well

**Limitations**:
- Requires entity extraction
- Can miss semantically similar but differently worded content
- Needs structured knowledge

### Combining Both: The Best of Both Worlds

**Example Query**: "What products did Company X launch after acquiring Company Y?"

**Vector Search** might find:
- Documents mentioning "Company X products"
- Documents mentioning "Company Y acquisition"

**Graph Search** might find:
- (Company X)-[:ACQUIRED]->(Company Y)
- (Company Y)-[:HAS_PRODUCT]->(Product Z)
- (Company X)-[:LAUNCHED]->(Product Z)

**Merged Results**:
- More complete context
- Better answer quality
- Higher recall

---

## Project Structure & Component Breakdown

```
gcp-gen-ai/
├── infra/                    # Infrastructure as Code (Terraform)
│   ├── main.tf              # Resource definitions
│   ├── variables.tf         # Input variables
│   ├── outputs.tf           # Output values
│   ├── providers.tf         # Provider configuration
│   └── versions.tf          # Version constraints
│
├── ingestion/               # Document ingestion pipeline
│   ├── function/           # Cloud Function (Gen 2)
│   │   ├── main.py         # Entry point (Pub/Sub trigger)
│   │   └── requirements.txt
│   └── processors/         # Processing modules
│       ├── extract_text.py # Text extraction (PDF, TXT, MD)
│       ├── chunk.py        # Text chunking with overlap
│       ├── embed.py        # Embedding generation
│       ├── upsert_vector.py # Vector Search upsert
│       ├── upsert_graph.py  # Neo4j graph upsert
│       └── schema.py       # Data models
│
├── service/                # Query/Answer API
│   ├── Dockerfile          # Container image
│   └── app/
│       ├── main.py         # FastAPI application
│       ├── requirements.txt
│       └── rag/            # RAG components
│           ├── retriever.py    # (Future: unified retriever)
│           ├── hybrid.py       # Hybrid search logic
│           ├── prompts.py      # (Future: prompt templates)
│           ├── agent.py         # (Future: agent orchestration)
│           ├── citations.py     # Citation formatting
│           ├── vertex_vector.py # Vector Search client
│           ├── graph_neo4j.py   # Neo4j client
│           ├── llm.py           # Gemini client
│           └── schemas.py       # API request/response models
│
└── shared/                 # Shared utilities
    ├── config.py           # Configuration management
    ├── models.py           # Shared data models
    └── utils.py            # Helper functions
```

### Component Responsibilities

#### Infrastructure (`infra/`)
- **Purpose**: Define and provision GCP resources
- **Key Resources**:
  - GCS bucket for documents
  - Pub/Sub topic for events
  - Cloud Function for ingestion
  - Cloud Run for API
  - Vertex AI Vector Search index
  - Service accounts and IAM

#### Ingestion Pipeline (`ingestion/`)
- **Purpose**: Process uploaded documents
- **Flow**:
  1. Triggered by GCS object creation
  2. Extract text from documents
  3. Chunk text into overlapping segments
  4. Generate embeddings
  5. Store in Vector Search
  6. Extract entities
  7. Store in Neo4j graph

#### Query Service (`service/`)
- **Purpose**: Answer questions using RAG
- **Flow**:
  1. Receive query
  2. Perform hybrid search (vector + graph)
  3. Merge and re-rank results
  4. Generate answer with LLM
  5. Return answer with citations

---

## Step 1: Infrastructure Setup with Terraform

### Understanding Terraform Files

#### `versions.tf` - Provider Requirements

```hcl
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.30.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4.0"
    }
  }
}
```

**Why these providers?**
- `google`: Standard GCP resources
- `google-beta`: Vector Search (beta feature)
- `archive`: Zip function code for deployment

#### `providers.tf` - Provider Configuration

```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
```

**Key Points**:
- Uses variables for project/region
- Separate beta provider for Vector Search

#### `variables.tf` - Input Parameters

**Required Variables**:
- `project_id`: GCP project ID
- `bucket_name`: GCS bucket name
- `cloud_run_image_uri`: Container image URI
- `neo4j_uri`, `neo4j_user`, `neo4j_password`: Neo4j connection

**Optional Variables** (with defaults):
- `region`: Default "us-central1"
- `create_vector_search`: Default true
- `vector_dimensions`: Default 768 (for text-embedding-004)
- `embedding_model`: Default "text-embedding-004"
- `generative_model`: Default "gemini-1.5-flash"
- `top_k`: Default 8

#### `main.tf` - Resource Definitions

**1. API Enablement**
```hcl
locals {
  required_apis = [
    "aiplatform.googleapis.com",      # Vertex AI
    "cloudfunctions.googleapis.com",  # Cloud Functions
    "run.googleapis.com",             # Cloud Run
    "eventarc.googleapis.com",        # Event triggers
    "pubsub.googleapis.com",          # Pub/Sub
    "storage.googleapis.com",         # Cloud Storage
    "artifactregistry.googleapis.com", # Container registry
    "cloudbuild.googleapis.com",      # Build service
    "logging.googleapis.com",        # Logging
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)
  project  = var.project_id
  service  = each.value
}
```

**Why enable APIs?**
- GCP requires explicit API enablement
- Some services depend on others
- `for_each` enables all in one block

**2. Storage & Event Notification**
```hcl
resource "google_storage_bucket" "rag_bucket" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
}

resource "google_pubsub_topic" "rag_ingest_topic" {
  name = var.pubsub_topic_name
}

resource "google_storage_notification" "gcs_to_pubsub" {
  bucket         = google_storage_bucket.rag_bucket.name
  topic          = google_pubsub_topic.rag_ingest_topic.id
  payload_format = "JSON_API_V1"
  event_types    = ["OBJECT_FINALIZE"]
}
```

**How it works**:
- When a file is uploaded to GCS → `OBJECT_FINALIZE` event
- GCS publishes to Pub/Sub topic
- Cloud Function subscribes to topic
- Function processes the document

**3. Service Accounts & IAM**
```hcl
resource "google_service_account" "function_sa" {
  account_id   = "rag-ingest-sa"
  display_name = "SA for RAG ingestion function"
}

resource "google_project_iam_member" "function_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}
```

**Principle of Least Privilege**:
- Separate service accounts for function vs. API
- Only grant necessary permissions
- Function needs: Vertex AI, Storage (read)
- API needs: Vertex AI, Storage (read)

**4. Vertex AI Vector Search**
```hcl
resource "google_beta_vertex_ai_index" "rag_index" {
  display_name = var.vector_index_display_name
  region       = var.region
  
  metadata {
    contents_delta_uri = "gs://${var.bucket_name}/vector_index_seed/"
    config {
      dimensions = var.vector_dimensions
      approximate_neighbors_count = 100
      distance_measure_type = "DOT_PRODUCT_DISTANCE"
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count = 1000
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }
}
```

**Key Parameters**:
- `dimensions`: Embedding vector size (768 for text-embedding-004)
- `distance_measure_type`: DOT_PRODUCT_DISTANCE (common for normalized embeddings)
- `tree_ah_config`: Approximate nearest neighbor algorithm (scalable)

**Index Endpoint**:
```hcl
resource "google_beta_vertex_ai_index_endpoint" "rag_index_endpoint" {
  display_name = "rag-index-endpoint"
  region       = var.region
}

resource "google_beta_vertex_ai_index_endpoint_deployed_index" "deployed" {
  index_endpoint = google_beta_vertex_ai_index_endpoint.rag_index_endpoint[0].name
  deployed_index_id = "rag_chunks"
  index = google_beta_vertex_ai_index.rag_index[0].name
}
```

**Why endpoint?**
- Index must be deployed to an endpoint to query
- Endpoint provides the API for search
- Can deploy multiple indexes to one endpoint

**5. Cloud Function (Gen 2)**
```hcl
resource "google_cloudfunctions2_function" "ingest_func" {
  name     = var.function_name
  location = var.region
  
  build_config {
    runtime     = "python310"
    entry_point = "ingest_document"
    source {
      storage_source {
        bucket = google_storage_bucket.rag_bucket.name
        object = google_storage_bucket_object.function_source_zip.name
      }
    }
  }
  
  service_config {
    available_memory      = "1024M"
    timeout_seconds       = 120
    service_account_email = google_service_account.function_sa.email
    environment_variables = {
      PROJECT_ID = var.project_id
      REGION     = var.region
      # ... more env vars
    }
  }
  
  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.rag_ingest_topic.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }
}
```

**Gen 2 vs Gen 1**:
- Gen 2: More features, better scaling, Cloud Run-based
- Event triggers: Pub/Sub, HTTP, or direct
- Service config: Memory, timeout, concurrency

**6. Cloud Run Service**
```hcl
resource "google_cloud_run_v2_service" "rag_api" {
  name     = var.cloud_run_service_name
  location = var.region
  
  template {
    service_account = google_service_account.run_sa.email
    containers {
      image = var.cloud_run_image_uri
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      # ... more env vars
    }
  }
}
```

**Note**: Image must be built/pushed separately (not in Terraform).

#### `outputs.tf` - Exported Values

```hcl
output "cloud_run_url" {
  value = google_cloud_run_v2_service.rag_api.uri
}

output "vector_index_endpoint" {
  value = var.create_vector_search ? google_beta_vertex_ai_index_endpoint.rag_index_endpoint[0].name : ""
}
```

**Use cases**:
- Get API URL after deployment
- Reference endpoint IDs in other configs
- Share with team members

### Deployment Steps

1. **Initialize Terraform**:
   ```bash
   cd infra
   terraform init
   ```

2. **Create `terraform.tfvars`**:
   ```hcl
   project_id = "your-gcp-project"
   region = "us-central1"
   bucket_name = "your-rag-bucket"
   cloud_run_image_uri = "gcr.io/your-project/rag-api:latest"
   neo4j_uri = "neo4j+s://your-instance.databases.neo4j.io"
   neo4j_user = "neo4j"
   neo4j_password = "your-password"
   ```

3. **Plan**:
   ```bash
   terraform plan
   ```

4. **Apply**:
   ```bash
   terraform apply
   ```

5. **Get outputs**:
   ```bash
   terraform output cloud_run_url
   ```

---

## Step 2: Data Models & Schema Design

### Vector Search Data Model

Each chunk stored in Vector Search contains:

```python
{
    "id": "doc_id::chunk_id",  # Composite key
    "embedding": [0.123, -0.456, ...],  # 768-dim vector
    # Optional: metadata stored separately or in external store
}
```

**ID Convention**: `doc_id::chunk_id`
- Enables tracking source document
- Unique chunk identifier
- Parsed during retrieval

**Why composite ID?**
- Vector Search typically stores minimal metadata
- ID can encode document + chunk info
- Alternative: Store full metadata in Firestore/GCS, reference by ID

### Neo4j Graph Schema

#### Node Types

**1. Document Node**
```cypher
(:Document {
    doc_id: "doc_123",
    title: "Product Launch Plan",
    gcs_uri: "gs://bucket/file.pdf",
    created_at: "2024-01-15T10:00:00Z",
    file_type: "pdf",
    file_size: 1024000
})
```

**Properties**:
- `doc_id`: Unique identifier
- `title`: Document title (extracted or filename)
- `gcs_uri`: Source location
- `created_at`: Timestamp
- `file_type`, `file_size`: Metadata

**2. Chunk Node**
```cypher
(:Chunk {
    chunk_id: "chunk_456",
    chunk_index: 3,
    page: 2,
    text_preview: "The product will launch in Q2...",
    token_count: 512
})
```

**Properties**:
- `chunk_id`: Unique identifier
- `chunk_index`: Position in document
- `page`: Source page (for PDFs)
- `text_preview`: First 200-300 chars
- `token_count`: For chunking validation

**3. Entity Node**
```cypher
(:Entity {
    name: "Company X",
    type: "ORGANIZATION",
    frequency: 15
})
```

**Properties**:
- `name`: Entity name (normalized)
- `type`: PERSON, ORGANIZATION, PRODUCT, etc.
- `frequency`: How many times mentioned (optional)

#### Relationship Types

**1. Document → Chunk**
```cypher
(:Document)-[:HAS_CHUNK {
    order: 3,
    created_at: "2024-01-15T10:05:00Z"
}]->(:Chunk)
```

**Purpose**: Links documents to their chunks

**2. Chunk → Entity**
```cypher
(:Chunk)-[:MENTIONS {
    confidence: 0.95,
    position: 42
}]->(:Entity)
```

**Purpose**: Tracks which entities appear in which chunks

**3. Entity → Entity (Optional)**
```cypher
(:Entity)-[:RELATED_TO {
    relationship_type: "ACQUIRED",
    strength: 0.8
}]->(:Entity)
```

**Purpose**: Model relationships between entities (future enhancement)

**4. Document → Entity (Optional)**
```cypher
(:Document)-[:ABOUT {
    relevance: 0.9
}]->(:Entity)
```

**Purpose**: Document-level entity associations

### Complete Graph Example

```
(doc1:Document {doc_id: "d1", title: "Acquisition News"})
    -[:HAS_CHUNK]->(chunk1:Chunk {chunk_id: "c1"})
    -[:HAS_CHUNK]->(chunk2:Chunk {chunk_id: "c2"})

(chunk1)-[:MENTIONS]->(companyA:Entity {name: "Company A"})
(chunk1)-[:MENTIONS]->(companyB:Entity {name: "Company B"})
(chunk2)-[:MENTIONS]->(companyB:Entity {name: "Company B"})

(companyA)-[:RELATED_TO {type: "ACQUIRED"}]->(companyB)
```

**Query Example**: Find chunks mentioning entities related to "Company A"
```cypher
MATCH (e:Entity {name: "Company A"})<-[:MENTIONS]-(c:Chunk)
RETURN c
```

### Data Flow: Ingestion to Storage

```
Document Upload
    ↓
Extract Text → Chunks
    ↓
Generate Embeddings
    ↓
┌─────────────────┬─────────────────┐
│ Vector Search   │   Neo4j Graph   │
│                 │                 │
│ - chunk_id      │ - Document node │
│ - doc_id        │ - Chunk nodes   │
│ - embedding     │ - Entity nodes  │
│ - (metadata)    │ - Relationships │
└─────────────────┴─────────────────┘
```

---

## Step 3: Document Ingestion Pipeline

### Overview: Event-Driven Processing

**Trigger**: GCS `OBJECT_FINALIZE` event → Pub/Sub → Cloud Function

**Function Flow**:
1. Receive Pub/Sub message
2. Extract GCS URI (bucket + object name)
3. Download document
4. Extract text/images
5. Chunk text
6. Generate embeddings
6. Upsert to Vector Search
7. Extract entities
8. Upsert to Neo4j

### Cloud Function Entry Point

**File**: `ingestion/function/main.py`

```python
import base64
import json
import os

def ingest_document(event, context):
    # Decode Pub/Sub message
    payload = base64.b64decode(event["data"]).decode("utf-8")
    msg = json.loads(payload)
    
    bucket = msg.get("bucket")
    name = msg.get("name")
    if not bucket or not name:
        print("Missing bucket/name:", msg)
        return
    
    gcs_uri = f"gs://{bucket}/{name}"
    print("Ingestion triggered for:", gcs_uri)
    
    # TODO: Implement processing pipeline
    # 1. extract_text.extract(gcs_uri)
    # 2. chunk.chunk_text(text)
    # 3. embed.generate_embeddings(chunks)
    # 4. upsert_vector.upsert(embeddings)
    # 5. extract_entities(chunks)
    # 6. upsert_graph.upsert(doc, chunks, entities)
```

**Pub/Sub Message Format**:
```json
{
  "bucket": "my-rag-bucket",
  "name": "documents/report.pdf",
  "contentType": "application/pdf",
  "size": "1024000"
}
```

### Step 3.1: Text Extraction

**File**: `ingestion/processors/extract_text.py`

**Supported Formats**:
- **PDF**: Use `pypdf` or `pdfplumber`
- **TXT/MD**: Direct read
- **Images**: Extract metadata, optional OCR

**Implementation Pattern**:
```python
def extract_text(gcs_uri: str) -> dict:
    """
    Returns:
    {
        "text": "full document text",
        "metadata": {
            "file_type": "pdf",
            "page_count": 10,
            "title": "extracted title"
        },
        "images": [
            {"page": 1, "gcs_uri": "gs://...", "caption": "..."}
        ]
    }
    """
    file_type = detect_file_type(gcs_uri)
    
    if file_type == "pdf":
        return extract_pdf(gcs_uri)
    elif file_type in ["txt", "md"]:
        return extract_text_file(gcs_uri)
    elif file_type in ["png", "jpg"]:
        return extract_image_metadata(gcs_uri)
    else:
        raise ValueError(f"Unsupported type: {file_type}")
```

**PDF Extraction Example**:
```python
from pypdf import PdfReader
from google.cloud import storage

def extract_pdf(gcs_uri: str) -> dict:
    client = storage.Client()
    bucket_name, blob_name = parse_gcs_uri(gcs_uri)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Download to memory
    pdf_bytes = blob.download_as_bytes()
    
    # Extract text
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text())
    
    full_text = "\n\n".join(text_parts)
    
    return {
        "text": full_text,
        "metadata": {
            "file_type": "pdf",
            "page_count": len(reader.pages),
            "title": reader.metadata.get("/Title", "")
        }
    }
```

**Key Considerations**:
- Handle large files (stream if needed)
- Preserve page boundaries (for citations)
- Extract metadata (title, author, etc.)
- Error handling (corrupted files, unsupported formats)

### Step 3.2: Text Chunking

**File**: `ingestion/processors/chunk.py`

**Why Chunk?**
- LLMs have token limits
- Smaller chunks = more precise retrieval
- Overlap prevents information loss at boundaries

**Chunking Strategy**:
- **Target size**: 500-800 tokens
- **Overlap**: 80-120 tokens
- **Method**: Token-aware (respect sentence boundaries)

**Implementation**:
```python
def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list:
    """
    Returns list of chunks:
    [
        {
            "chunk_id": "chunk_0",
            "text": "...",
            "start_token": 0,
            "end_token": 600,
            "page": 1
        },
        ...
    ]
    """
    # Tokenize (simplified - use tiktoken in production)
    tokens = tokenize(text)
    
    chunks = []
    start = 0
    chunk_index = 0
    
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        
        # Convert back to text (preserve sentences)
        chunk_text = detokenize(chunk_tokens)
        
        chunks.append({
            "chunk_id": f"chunk_{chunk_index}",
            "text": chunk_text,
            "start_token": start,
            "end_token": end,
            "chunk_index": chunk_index
        })
        
        # Move start forward with overlap
        start = end - overlap
        chunk_index += 1
    
    return chunks
```

**Better Approach: Sentence-Aware Chunking**:
```python
import re

def chunk_text_sentences(text: str, chunk_size: int = 600, overlap: int = 100) -> list:
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_size = 0
    chunk_index = 0
    
    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        
        if current_size + sentence_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunks.append({
                "chunk_id": f"chunk_{chunk_index}",
                "text": " ".join(current_chunk),
                "chunk_index": chunk_index
            })
            
            # Start new chunk with overlap
            overlap_sentences = current_chunk[-overlap//50:]  # Approximate
            current_chunk = overlap_sentences + [sentence]
            current_size = sum(count_tokens(s) for s in current_chunk)
            chunk_index += 1
        else:
            current_chunk.append(sentence)
            current_size += sentence_tokens
    
    # Add final chunk
    if current_chunk:
        chunks.append({
            "chunk_id": f"chunk_{chunk_index}",
            "text": " ".join(current_chunk),
            "chunk_index": chunk_index
        })
    
    return chunks
```

**Why Sentence-Aware?**
- Prevents cutting mid-sentence
- Better semantic units
- Cleaner chunk boundaries

### Step 3.3: Embedding Generation

**File**: `ingestion/processors/embed.py`

**Vertex AI Embeddings**:
- Model: `text-embedding-004` (768 dimensions)
- Normalized vectors (unit length)
- Optimized for semantic similarity

**Implementation**:
```python
from vertexai.language_models import TextEmbeddingModel
import vertexai

def generate_embeddings(chunks: list, project_id: str, region: str) -> list:
    """
    Returns chunks with embeddings:
    [
        {
            "chunk_id": "chunk_0",
            "text": "...",
            "embedding": [0.123, -0.456, ...]
        },
        ...
    ]
    """
    vertexai.init(project=project_id, location=region)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    
    # Batch embeddings (more efficient)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.get_embeddings(texts)
    
    # Attach embeddings to chunks
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = list(emb.values)
    
    return chunks
```

**Batch Processing**:
- Vertex AI supports batch embedding
- More efficient than one-by-one
- Typical batch size: 100-1000

**Cost Considerations**:
- Embedding API charges per token
- Cache embeddings for unchanged chunks
- Consider embedding only new/updated documents

### Step 3.4: Vector Search Upsert

**File**: `ingestion/processors/upsert_vector.py`

**Vertex AI Vector Search API**:
- Create index (done in Terraform)
- Upsert datapoints (chunks)
- Query for nearest neighbors

**Implementation**:
```python
from google.cloud import aiplatform
from google.cloud.aiplatform import MatchingEngineIndex
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import MatchingEngineIndexEndpoint

def upsert_chunks(chunks: list, doc_id: str, index_endpoint: str, deployed_index_id: str):
    """
    Upsert chunks to Vector Search index.
    
    Datapoint format:
    {
        "id": "doc_id::chunk_id",
        "embedding": [0.123, -0.456, ...]
    }
    """
    endpoint = MatchingEngineIndexEndpoint(index_endpoint_name=index_endpoint)
    
    datapoints = []
    for chunk in chunks:
        datapoints.append({
            "id": f"{doc_id}::{chunk['chunk_id']}",
            "embedding": chunk["embedding"]
        })
    
    # Upsert in batches (recommended: 100-1000 per batch)
    batch_size = 100
    for i in range(0, len(datapoints), batch_size):
        batch = datapoints[i:i+batch_size]
        endpoint.upsert_datapoints(
            deployed_index_id=deployed_index_id,
            datapoints=batch
        )
```

**Important Notes**:
- Index must be deployed before upserting
- Upserts are eventually consistent (few seconds delay)
- Can upsert same ID to update embedding
- Delete by ID if needed

### Step 3.5: Entity Extraction

**Simple Approach (Current)**:
```python
import re

def extract_entities_simple(text: str) -> list:
    """
    Heuristic: Capitalized words (potential entities)
    """
    candidates = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", text)
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen[:6]  # Limit to top 6
```

**Better Approach: LLM-Based Extraction**:
```python
from vertexai.generative_models import GenerativeModel

def extract_entities_llm(text: str, project_id: str, region: str) -> list:
    """
    Use Gemini to extract entities.
    """
    vertexai.init(project=project_id, location=region)
    model = GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    Extract all named entities (people, organizations, products, locations) from this text.
    Return as JSON array: [{{"name": "...", "type": "PERSON|ORGANIZATION|PRODUCT|LOCATION"}}]
    
    Text:
    {text[:2000]}  # Limit to avoid token limits
    """
    
    response = model.generate_content(prompt)
    # Parse JSON response
    entities = json.loads(response.text)
    return entities
```

**Best Approach: Vertex AI Entity Extraction API** (if available):
- Specialized model for NER
- Better accuracy
- Handles multiple entity types

### Step 3.6: Neo4j Graph Upsert

**File**: `ingestion/processors/upsert_graph.py`

**Implementation**:
```python
from neo4j import GraphDatabase

def upsert_document_graph(doc_id: str, doc_metadata: dict, chunks: list, entities: list):
    """
    Create/update graph:
    - Document node
    - Chunk nodes
    - Entity nodes
    - Relationships
    """
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    with driver.session() as session:
        # Create/update Document
        session.run("""
            MERGE (d:Document {doc_id: $doc_id})
            SET d.title = $title,
                d.gcs_uri = $gcs_uri,
                d.created_at = $created_at
        """, doc_id=doc_id, **doc_metadata)
        
        # Create Chunks and link to Document
        for chunk in chunks:
            session.run("""
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.chunk_index = $chunk_index,
                    c.text_preview = $text_preview
                
                WITH c
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (d)-[:HAS_CHUNK {order: $chunk_index}]->(c)
            """, chunk_id=chunk["chunk_id"], 
                chunk_index=chunk["chunk_index"],
                text_preview=chunk["text"][:200],
                doc_id=doc_id)
        
        # Create Entities and link to Chunks
        for entity in entities:
            session.run("""
                MERGE (e:Entity {name: $name})
                SET e.type = $type
                
                WITH e
                UNWIND $chunk_ids AS chunk_id
                MATCH (c:Chunk {chunk_id: chunk_id})
                MERGE (c)-[:MENTIONS]->(e)
            """, name=entity["name"],
                type=entity.get("type", "UNKNOWN"),
                chunk_ids=[c["chunk_id"] for c in chunks])
    
    driver.close()
```

**Cypher Query Explanation**:
- `MERGE`: Create if not exists, otherwise match
- `SET`: Update properties
- `MATCH`: Find existing nodes
- `UNWIND`: Expand list into rows

**Transaction Safety**:
- Use transactions for atomicity
- Batch operations for performance
- Handle errors gracefully

### Complete Ingestion Flow

**Putting it all together**:
```python
def ingest_document(event, context):
    # 1. Parse event
    gcs_uri = parse_event(event)
    doc_id = generate_doc_id(gcs_uri)
    
    # 2. Extract text
    extracted = extract_text.extract(gcs_uri)
    
    # 3. Chunk
    chunks = chunk.chunk_text(extracted["text"])
    
    # 4. Embed
    chunks_with_embeddings = embed.generate_embeddings(
        chunks, 
        PROJECT_ID, 
        REGION
    )
    
    # 5. Upsert to Vector Search
    upsert_vector.upsert_chunks(
        chunks_with_embeddings,
        doc_id,
        INDEX_ENDPOINT,
        DEPLOYED_INDEX_ID
    )
    
    # 6. Extract entities
    entities = extract_entities(extracted["text"])
    
    # 7. Upsert to Neo4j
    upsert_graph.upsert_document_graph(
        doc_id,
        extracted["metadata"],
        chunks,
        entities
    )
    
    print(f"Ingestion complete: {doc_id}, {len(chunks)} chunks")
```

---

## Step 4: Vector Search with Vertex AI

### Understanding Vector Embeddings

**What are embeddings?**
- Dense vector representations of text
- Similar texts → similar vectors
- Distance in vector space = semantic similarity

**Example**:
```
"machine learning" → [0.1, -0.3, 0.5, ...]
"artificial intelligence" → [0.12, -0.28, 0.48, ...]  # Similar!
"cooking recipes" → [-0.2, 0.4, -0.1, ...]  # Different
```

### Vertex AI Embedding Models

**text-embedding-004**:
- 768 dimensions
- Normalized (unit length)
- Optimized for semantic search
- Multilingual support

**Usage**:
```python
from vertexai.language_models import TextEmbeddingModel

model = TextEmbeddingModel.from_pretrained("text-embedding-004")
embeddings = model.get_embeddings(["text 1", "text 2"])
vector = list(embeddings[0].values)  # 768-dim list
```

### Vertex AI Vector Search Architecture

**Components**:
1. **Index**: Stores embeddings (created once)
2. **Endpoint**: Query interface (deployed index)
3. **Datapoints**: Individual embeddings (upserted)

**Index Configuration**:
```hcl
resource "google_beta_vertex_ai_index" "rag_index" {
  metadata {
    config {
      dimensions = 768
      distance_measure_type = "DOT_PRODUCT_DISTANCE"
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count = 1000
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }
}
```

**Algorithm: Tree-AH (Approximate Nearest Neighbor)**:
- Builds tree structure for fast search
- Approximate (not exact) but much faster
- Trade-off: Speed vs. accuracy

### Vector Search Client Implementation

**File**: `service/app/rag/vertex_vector.py`

```python
class VertexVectorClient:
    def __init__(self, project_id: str, region: str):
        aiplatform.init(project=project_id, location=region)
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        self.index_endpoint = os.getenv("VECTOR_INDEX_ENDPOINT")
        self.deployed_index_id = os.getenv("DEPLOYED_INDEX_ID")
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding for query text."""
        emb = self.embedding_model.get_embeddings([text])[0].values
        return list(emb)
    
    def search(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        """Search for similar chunks."""
        endpoint = MatchingEngineIndexEndpoint(
            index_endpoint_name=self.index_endpoint
        )
        
        resp = endpoint.find_neighbors(
            deployed_index_id=self.deployed_index_id,
            queries=[query_embedding],
            num_neighbors=top_k,
        )
        
        results = []
        for neighbor in resp[0]:
            results.append({
                "id": neighbor.id,  # "doc_id::chunk_id"
                "score": float(neighbor.distance)
            })
        return results
```

### Query Flow

1. **User Query**: "What is machine learning?"
2. **Embed Query**: Generate 768-dim vector
3. **Search**: Find nearest neighbors in index
4. **Results**: Top-K chunks with similarity scores

**Distance Metrics**:
- `DOT_PRODUCT_DISTANCE`: For normalized embeddings (this project)
- `EUCLIDEAN_DISTANCE`: Standard L2 distance
- `COSINE_DISTANCE`: 1 - cosine similarity

**Why DOT_PRODUCT for normalized vectors?**
- Normalized vectors: dot product = cosine similarity
- Faster computation
- Good for semantic similarity

### Limitations & Considerations

**1. Metadata Storage**:
- Vector Search stores minimal metadata
- Options:
  - Store full metadata in Firestore/GCS, reference by ID
  - Include metadata in datapoint (limited size)
  - Use external metadata store

**2. Update Strategy**:
- Upsert same ID to update
- Delete old, insert new for major changes
- Consider versioning

**3. Scaling**:
- Index supports millions of vectors
- Query latency: ~10-100ms
- Upsert throughput: thousands per second

---

## Step 5: Graph Database with Neo4j

### Why Graph for RAG?

**Graph Advantages**:
1. **Relationship Traversal**: Follow connections between entities
2. **Multi-hop Reasoning**: A → B → C relationships
3. **Entity-Centric Queries**: "What documents mention entities related to X?"
4. **Structure Preservation**: Maintains document/chunk/entity relationships

### Neo4j Basics

**Cypher Query Language**:
- Declarative (describe what you want)
- Pattern matching
- Similar to SQL but for graphs

**Basic Patterns**:
```cypher
// Find all chunks in a document
MATCH (d:Document {doc_id: "doc1"})-[:HAS_CHUNK]->(c:Chunk)
RETURN c

// Find entities mentioned in chunks
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
RETURN e.name, count(c) as mentions
ORDER BY mentions DESC
```

### Graph Client Implementation

**File**: `service/app/rag/graph_neo4j.py`

```python
class Neo4jGraphClient:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def expand_by_entities(self, entities: List[str], limit: int = 10) -> List[Dict]:
        """
        Given entity names, find related chunks via graph traversal.
        """
        cypher = """
        UNWIND $entities AS e
        MATCH (ent:Entity {name: e})<-[:MENTIONS]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
        RETURN c.chunk_id AS chunk_id, 
               d.doc_id AS doc_id, 
               d.gcs_uri AS source, 
               c.text_preview AS text_preview
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            rows = session.run(cypher, entities=entities, limit=limit)
            return [dict(row) for row in rows]
```

**Query Explanation**:
1. `UNWIND $entities`: Expand entity list into rows
2. `MATCH`: Find pattern: Entity ← Chunk ← Document
3. `RETURN`: Extract chunk/document info
4. `LIMIT`: Restrict results

### Advanced Graph Queries

**1. Multi-hop Traversal**:
```cypher
// Find chunks mentioning entities related to "Company A"
MATCH (e1:Entity {name: "Company A"})-[:RELATED_TO*1..2]-(e2:Entity)
MATCH (e2)<-[:MENTIONS]-(c:Chunk)
RETURN DISTINCT c
```

**2. Entity Co-occurrence**:
```cypher
// Find chunks where multiple entities appear together
MATCH (c:Chunk)-[:MENTIONS]->(e1:Entity)
MATCH (c)-[:MENTIONS]->(e2:Entity)
WHERE e1.name IN $entities AND e2.name <> e1.name
RETURN c, e1, e2
```

**3. Document Similarity (via shared entities)**:
```cypher
// Find documents with similar entity profiles
MATCH (d1:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
MATCH (d2:Document)-[:HAS_CHUNK]->(c2:Chunk)-[:MENTIONS]->(e)
WHERE d2.doc_id <> d1.doc_id
RETURN d2, count(DISTINCT e) as shared_entities
ORDER BY shared_entities DESC
```

### Neo4j Deployment Options

**Option A: Neo4j Aura (Managed)**
- ✅ Easiest setup
- ✅ Managed backups
- ✅ Auto-scaling
- ✅ Free tier available
- ❌ External to GCP

**Option B: Neo4j on GCE**
- ✅ All in GCP
- ✅ More control
- ❌ More setup/maintenance
- ❌ Need to handle backups

**Recommendation**: Start with Aura, migrate to GCE if needed.

### Graph Schema Best Practices

**1. Index Key Properties**:
```cypher
CREATE INDEX doc_id_index FOR (d:Document) ON (d.doc_id)
CREATE INDEX chunk_id_index FOR (c:Chunk) ON (c.chunk_id)
CREATE INDEX entity_name_index FOR (e:Entity) ON (e.name)
```

**2. Constrain Uniqueness**:
```cypher
CREATE CONSTRAINT doc_id_unique FOR (d:Document) REQUIRE d.doc_id IS UNIQUE
CREATE CONSTRAINT chunk_id_unique FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE
```

**3. Relationship Properties**:
- Store metadata on relationships (confidence, timestamp)
- Useful for ranking/filtering

---

## Step 6: Hybrid Retrieval Strategy

### The Hybrid Approach

**Combining Vector + Graph**:
1. **Vector Search**: Semantic similarity (broad recall)
2. **Graph Search**: Entity relationships (targeted recall)
3. **Merge & Re-rank**: Combine results intelligently

### Implementation

**File**: `service/app/rag/hybrid.py`

```python
def merge_and_score(vector_hits: List[Dict], graph_hits: List[Dict]) -> List[Dict]:
    """
    Merge results from both sources and assign scores.
    
    Strategy:
    - Vector hits: Use similarity score as-is
    - Graph hits: Baseline score (0.35) + bonus if also in vector results
    - Re-rank by combined score
    """
    out = {}
    
    # Process vector hits
    for h in vector_hits:
        doc_id, chunk_id = parse_id(h["id"])  # "doc_id::chunk_id"
        key = f"{doc_id}::{chunk_id}"
        out[key] = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "source": "vector_search",
            "score": float(h.get("score", 0.0)),
            "text_preview": ""
        }
    
    # Process graph hits
    for g in graph_hits:
        key = f"{g['doc_id']}::{g['chunk_id']}"
        if key not in out:
            # New result from graph
            out[key] = {
                "chunk_id": g["chunk_id"],
                "doc_id": g["doc_id"],
                "source": "graph_search",
                "score": 0.35,  # Baseline
                "text_preview": g.get("text_preview", "")
            }
        else:
            # Overlap: boost score
            out[key]["score"] += 0.15
            if not out[key]["text_preview"]:
                out[key]["text_preview"] = g.get("text_preview", "")
    
    # Re-rank by score
    ranked = sorted(out.values(), key=lambda x: x["score"], reverse=True)
    return ranked
```

### Scoring Strategy

**Why these scores?**
- **Vector score**: Direct similarity (0.0-1.0 typically)
- **Graph baseline (0.35)**: Moderate confidence for entity matches
- **Overlap bonus (+0.15)**: Higher confidence when both sources agree

**Tuning Tips**:
- Adjust graph baseline based on entity extraction quality
- Increase overlap bonus if you want to prioritize consensus
- Consider normalizing vector scores to [0, 1] range

### Entity Extraction for Queries

**Current Implementation** (simple):
```python
def extract_entities_simple(text: str) -> List[str]:
    """Heuristic: Capitalized words."""
    candidates = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", text)
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen[:6]
```

**Better: LLM-Based**:
```python
def extract_entities_llm(query: str) -> List[str]:
    """Use Gemini to extract entities from query."""
    prompt = f"""
    Extract named entities from this query: "{query}"
    Return as JSON array of entity names: ["Entity1", "Entity2"]
    """
    response = llm_client.generate(prompt)
    entities = json.loads(response.text)
    return entities
```

### Query Processing Flow

**In API endpoint** (`service/app/main.py`):
```python
@app.post("/ask")
def ask(req: AskRequest):
    # 1. Generate query embedding
    q_emb = vector_client.embed(req.question)
    
    # 2. Vector search
    vec_hits = vector_client.search(q_emb, top_k=req.top_k)
    
    # 3. Extract entities
    entities = extract_entities_simple(req.question)
    
    # 4. Graph expansion
    graph_hits = graph_client.expand_by_entities(entities, limit=req.top_k)
    
    # 5. Merge & re-rank
    merged = merge_and_score(vec_hits, graph_hits)[:req.top_k]
    
    # 6. Generate answer (see Step 7)
    # ...
```

### Why Hybrid Works Better

**Example Query**: "What did Company A acquire?"

**Vector Search** might find:
- Documents with "Company A" and "acquire" (semantic match)
- Score: 0.85

**Graph Search** might find:
- Chunks where (Company A)-[:ACQUIRED]->(Company B) relationship exists
- Score: 0.35 (baseline)

**Merged Result**:
- Both sources agree → boosted score: 0.85 + 0.15 = 1.0
- More complete context
- Better answer quality

---

## Step 7: Query Processing & Answer Generation

### API Endpoints

**File**: `service/app/main.py`

**1. Health Check**:
```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

**2. Search Endpoint** (debugging):
```python
@app.post("/search", response_model=SearchResponse)
def search(req: AskRequest):
    """Return retrieved chunks without generating answer."""
    top_k = req.top_k or TOP_K_DEFAULT
    
    q_emb = vector_client.embed(req.question)
    vec_hits = vector_client.search(q_emb, top_k=top_k)
    
    entities = extract_entities_simple(req.question)
    graph_hits = graph_client.expand_by_entities(entities, limit=top_k)
    
    merged = merge_and_score(vec_hits, graph_hits)[:top_k]
    
    results = [
        Citation(
            chunk_id=m["chunk_id"],
            doc_id=m["doc_id"],
            source=m["source"],
            score=m["score"],
            text_preview=m["text_preview"][:240]
        )
        for m in merged
    ]
    return SearchResponse(results=results)
```

**3. Ask Endpoint** (main):
```python
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """Generate answer with citations."""
    # ... retrieval (same as search) ...
    
    # Format context for LLM
    context_items = [
        {
            "chunk_id": m["chunk_id"],
            "doc_id": m["doc_id"],
            "source": m["source"],
            "text_preview": m.get("text_preview", "")
        }
        for m in merged
    ]
    
    context_blocks = make_context_block(context_items)
    answer = llm_client.answer(req.question, context_blocks)
    
    citations = [
        Citation(
            chunk_id=m["chunk_id"],
            doc_id=m["doc_id"],
            source=m["source"],
            score=m["score"],
            text_preview=m.get("text_preview", "")[:240]
        )
        for m in merged
    ]
    
    return AskResponse(answer=answer, citations=citations)
```

### Context Formatting

**File**: `service/app/rag/citations.py`

```python
def make_context_block(items: List[Dict]) -> str:
    """
    Format retrieved chunks for LLM prompt.
    
    Format:
    chunk_id=abc | doc_id=doc1 | source=vector_search
    Text preview...
    ---
    chunk_id=def | doc_id=doc2 | source=graph_search
    Text preview...
    """
    blocks = []
    for it in items:
        blocks.append(
            f"chunk_id={it['chunk_id']} | doc_id={it['doc_id']} | source={it['source']}\n"
            f"{it['text_preview']}\n"
        )
    return "\n---\n".join(blocks)
```

**Why this format?**
- Clear chunk boundaries
- Includes metadata (chunk_id, doc_id, source)
- Easy for LLM to reference in citations

### LLM Answer Generation

**File**: `service/app/rag/llm.py`

```python
class GeminiClient:
    def __init__(self, project_id: str, region: str):
        vertexai.init(project=project_id, location=region)
        model_name = os.getenv("GENERATIVE_MODEL", "gemini-1.5-flash")
        self.model = GenerativeModel(model_name)
    
    def answer(self, question: str, context_blocks: str) -> str:
        prompt = f"""
You are a helpful assistant. Answer using ONLY the provided context.
If the answer is not in the context, say you don't know.
Include brief citations by chunk id in brackets like [chunk:abc123].

QUESTION:
{question}

CONTEXT:
{context_blocks}
"""
        resp = self.model.generate_content(prompt)
        return resp.text
```

### Prompt Engineering Best Practices

**1. System Instructions**:
- Clear role definition
- Citation requirements
- Honesty about uncertainty

**2. Context Format**:
- Structured (chunk boundaries)
- Include metadata
- Limit length (token budget)

**3. Citation Format**:
- Consistent format: `[chunk:abc123]`
- Easy to parse
- Links to source

**Enhanced Prompt** (future):
```python
prompt = f"""
You are an expert assistant answering questions based on provided documents.

RULES:
1. Use ONLY information from the CONTEXT below
2. If the answer isn't in the context, say "I don't have that information"
3. Cite sources using [chunk:chunk_id] format
4. Be concise but complete
5. If information conflicts, mention both perspectives

QUESTION: {question}

CONTEXT:
{context_blocks}

ANSWER:
"""
```

### Response Schema

**File**: `service/app/rag/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: Optional[int] = None

class Citation(BaseModel):
    chunk_id: str
    doc_id: str
    source: str  # "vector_search" or "graph_search"
    score: float
    text_preview: str

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]

class SearchResponse(BaseModel):
    results: List[Citation]
```

**Why Pydantic?**
- Automatic validation
- Type safety
- API documentation (OpenAPI/Swagger)

---

## Step 8: Deployment & Operations

### Building the Container Image

**Dockerfile** (`service/Dockerfile`):
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
ENV PYTHONPATH=/app

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Build & Push**:
```bash
# Build
docker build -t gcr.io/PROJECT_ID/rag-api:latest ./service

# Push to Artifact Registry (or GCR)
docker push gcr.io/PROJECT_ID/rag-api:latest
```

**Note**: Update `cloud_run_image_uri` in Terraform variables.

### Environment Variables

**Cloud Function** (ingestion):
- `PROJECT_ID`
- `REGION`
- `BUCKET_NAME`
- `VECTOR_INDEX_ENDPOINT`
- `DEPLOYED_INDEX_ID`
- `EMBEDDING_MODEL`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`

**Cloud Run** (API):
- Same as above, plus:
- `GENERATIVE_MODEL`
- `TOP_K`

### Monitoring & Logging

**Cloud Function Logs**:
```python
import logging
logging.info(f"Ingestion started: {gcs_uri}")
logging.error(f"Error: {error}")
```

**Cloud Run Logs**:
- Automatic logging via `print()` or `logging`
- View in Cloud Logging console
- Filter by service name

**Key Metrics to Track**:
1. **Ingestion**:
   - Documents processed per day
   - Chunks per document
   - Embedding generation time
   - Vector upsert success rate
   - Graph nodes/edges created

2. **Query**:
   - Query latency (p50, p95, p99)
   - Top-K retrieval time
   - LLM generation time
   - Citations per answer

**BigQuery Metrics** (future):
```sql
CREATE TABLE rag_metrics.ingestion_runs (
    doc_id STRING,
    chunks_count INT64,
    ingestion_time TIMESTAMP,
    duration_seconds FLOAT64,
    status STRING
);

CREATE TABLE rag_metrics.query_runs (
    request_id STRING,
    query TEXT,
    top_k INT64,
    retrieval_time_ms FLOAT64,
    llm_time_ms FLOAT64,
    total_time_ms FLOAT64,
    citations_count INT64
);
```

### Error Handling

**Ingestion Errors**:
- Retry on transient failures
- Log errors for manual review
- Consider dead-letter queue (Pub/Sub)

**Query Errors**:
- Return error response (don't crash)
- Log errors for debugging
- Fallback to simpler retrieval if hybrid fails

### Testing

**1. Unit Tests**:
- Chunking logic
- Entity extraction
- Scoring/merging

**2. Integration Tests**:
- End-to-end ingestion
- Query → answer flow
- Vector + graph retrieval

**3. Load Testing**:
- Concurrent queries
- Large document ingestion
- Vector search performance

---

## Step 9: Advanced Topics & Extensions

### 1. Multimodal Support

**Current**: Text-only

**Enhancement**: Images
- Extract images from PDFs
- Generate captions (Gemini Vision)
- Store image URIs in metadata
- Include images in citations

**Implementation**:
```python
def process_images(pdf_path: str) -> List[Dict]:
    """Extract images and generate captions."""
    images = extract_images_from_pdf(pdf_path)
    captions = []
    for img in images:
        caption = gemini_vision.generate_caption(img)
        captions.append({
            "gcs_uri": upload_image(img),
            "caption": caption,
            "caption_embedding": embed(caption)
        })
    return captions
```

### 2. Async Ingestion Status

**Problem**: Long-running ingestion, no status updates

**Solution**: Firestore status tracking
```python
# Ingest start
firestore.collection("ingestion_status").document(doc_id).set({
    "status": "PROCESSING",
    "started_at": datetime.now(),
    "chunks_processed": 0,
    "total_chunks": len(chunks)
})

# Progress updates
firestore.collection("ingestion_status").document(doc_id).update({
    "chunks_processed": current,
    "status": "COMPLETE" if done else "PROCESSING"
})
```

### 3. Deduplication & Versioning

**Problem**: Re-uploading same document

**Solution**: Content hashing
```python
import hashlib

def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

# Check if exists
existing = firestore.collection("documents").where("content_hash", "==", hash).get()
if existing:
    # Skip or create version edge
    create_version_edge(existing_doc_id, new_doc_id)
```

### 4. PII Redaction

**Problem**: Sensitive data in documents

**Solution**: Redact before ingestion
```python
from google.cloud import dlp

def redact_pii(text: str) -> str:
    client = dlp.DlpServiceClient()
    response = client.deidentify_content(
        parent=f"projects/{PROJECT_ID}",
        deidentify_config={
            "info_type_transformations": {
                "transformations": [
                    {"primitive_transformation": {"replace_config": {"new_value": {"string_value": "[REDACTED]"}}}}
                ]
            }
        },
        item={"value": text}
    )
    return response.item.value.string_value
```

### 5. Evaluation Framework

**Metrics**:
- **Groundedness**: Answer supported by context?
- **Citation Quality**: Correct sources cited?
- **Answer Relevance**: Answers the question?

**Implementation**:
```python
def evaluate_answer(question: str, answer: str, citations: List[Citation]) -> Dict:
    # Use LLM to evaluate
    prompt = f"""
    Question: {question}
    Answer: {answer}
    Citations: {citations}
    
    Rate:
    1. Groundedness (0-1): Is answer supported by citations?
    2. Citation Quality (0-1): Are citations relevant?
    3. Relevance (0-1): Does answer address question?
    """
    evaluation = llm.generate(prompt)
    return parse_evaluation(evaluation)
```

### 6. Agent Orchestration

**Future**: Multi-step reasoning
- Break complex queries into steps
- Use tools (search, compute, etc.)
- Chain reasoning steps

**Example**:
```python
class RAGAgent:
    def answer(self, query: str):
        # Step 1: Retrieve context
        context = self.retrieve(query)
        
        # Step 2: Determine if follow-up needed
        if self.needs_followup(query, context):
            # Step 3: Refine query
            refined = self.refine_query(query, context)
            context = self.retrieve(refined)
        
        # Step 4: Generate answer
        return self.generate(query, context)
```

---

## Conclusion

### What You've Learned

1. **RAG Architecture**: How retrieval-augmented generation works
2. **Hybrid Retrieval**: Combining vector search and graph traversal
3. **GCP Services**: Vertex AI, Cloud Functions, Cloud Run, Vector Search
4. **Graph Databases**: Neo4j for relationship modeling
5. **Event-Driven Processing**: Automatic ingestion pipelines
6. **Production Patterns**: Error handling, monitoring, scaling

### Next Steps

1. **Implement Processors**: Complete the ingestion pipeline
2. **Test End-to-End**: Upload documents, query, verify answers
3. **Optimize**: Tune chunking, scoring, prompts
4. **Extend**: Add multimodal, evaluation, agent features
5. **Deploy**: Production deployment with monitoring

### Resources

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

---

**Happy Building! 🚀**
