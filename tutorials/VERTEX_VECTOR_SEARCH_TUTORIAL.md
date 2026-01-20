# Vertex AI Vector Search: Complete Terraform Configuration Guide

## Table of Contents

1. [Introduction to Vertex AI Vector Search](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [Understanding the Terraform Resources](#terraform-resources)
4. [Index Configuration Deep Dive](#index-configuration-deep-dive)
5. [Distance Measures Explained](#distance-measures-explained)
6. [Algorithm Configuration: Tree-AH](#algorithm-configuration-tree-ah)
7. [Index Endpoint and Deployment](#index-endpoint-and-deployment)
8. [Complete Workflow](#complete-workflow)
9. [Best Practices and Tuning](#best-practices-and-tuning)
10. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Introduction to Vertex AI Vector Search

### What is Vertex AI Vector Search?

**Vertex AI Vector Search** (formerly known as Vertex AI Matching Engine) is Google Cloud's managed service for similarity search on large-scale vector embeddings. It enables you to:

- **Store millions of vectors** efficiently
- **Search for similar vectors** in milliseconds
- **Scale automatically** without infrastructure management
- **Integrate seamlessly** with Vertex AI embeddings

### Why Use Vector Search for RAG?

**The Problem**:
- Traditional keyword search misses semantic similarity
- "Machine learning" ≠ "artificial intelligence" (keyword search)
- But they're semantically similar (vector search finds both)

**The Solution**:
- Embed documents into vectors (dense representations)
- Store vectors in Vector Search index
- Query with embedded question → find similar document chunks
- Retrieve most relevant context for LLM

### Key Concepts

**Vector Embedding**: A numerical representation of text (e.g., 768 numbers for text-embedding-004)

**Similarity Search**: Finding vectors closest to a query vector in high-dimensional space

**Approximate Nearest Neighbor (ANN)**: Fast algorithm to find similar vectors without checking every vector

---

## Architecture Overview

### Three-Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Vertex AI Vector Search                   │
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────┐ │
│  │    Index     │      │   Endpoint   │      │ Deployed │ │
│  │              │      │              │      │  Index   │ │
│  │ - Defines    │──────│ - Provides   │──────│ - Active │ │
│  │   structure  │      │   API        │      │   index  │ │
│  │ - Stores     │      │   endpoint   │      │ - Ready  │ │
│  │   vectors    │      │ - Manages    │      │   to     │ │
│  │              │      │   deployments│      │   query  │ │
│  └──────────────┘      └──────────────┘      └──────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Component Roles

**1. Index** (`google_beta_vertex_ai_index`)
- **Purpose**: Defines the structure and configuration of your vector database
- **Contains**: Metadata, dimensions, distance measure, algorithm config
- **State**: Created but not yet queryable

**2. Index Endpoint** (`google_beta_vertex_ai_index_endpoint`)
- **Purpose**: Provides the API endpoint for querying
- **Contains**: Network configuration, access controls
- **State**: Created but empty (no index deployed yet)

**3. Deployed Index** (`google_beta_vertex_ai_index_endpoint_deployed_index`)
- **Purpose**: Links an index to an endpoint, making it queryable
- **Contains**: Index reference, deployment ID
- **State**: Active and ready for queries

### Why Three Components?

**Separation of Concerns**:
- **Index**: Configuration (created once, rarely changes)
- **Endpoint**: Infrastructure (reusable for multiple indexes)
- **Deployed Index**: Active deployment (can update/redeploy without recreating index)

**Benefits**:
- Deploy same index to multiple endpoints (dev/staging/prod)
- Update index without recreating endpoint
- A/B test different index configurations

---

## Understanding the Terraform Resources

### Resource 1: Index Definition

```hcl
resource "google_beta_vertex_ai_index" "rag_index" {
  count        = var.create_vector_search ? 1 : 0
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
  
  depends_on = [google_project_service.apis, google_storage_bucket.rag_bucket]
}
```

**Breaking Down Each Field**:

#### `count = var.create_vector_search ? 1 : 0`
- **Purpose**: Conditional creation (optional feature)
- **Why**: Allows disabling Vector Search if using alternative (e.g., only graph search)
- **Usage**: Set `create_vector_search = false` in variables to skip

#### `display_name = var.vector_index_display_name`
- **Purpose**: Human-readable name for the index
- **Example**: "rag-chunks-index"
- **Note**: Not used in API calls (use resource name instead)

#### `region = var.region`
- **Purpose**: GCP region where index is created
- **Important**: Must match region of embeddings and queries
- **Common**: "us-central1", "us-east1", "europe-west1"
- **Why**: Reduces latency, ensures data residency

#### `metadata { contents_delta_uri = "gs://..." }`
- **Purpose**: Optional initial data location
- **What it does**: Can pre-populate index with vectors from GCS
- **Format**: JSON Lines (JSONL) with embeddings
- **In this config**: Points to empty folder (can upsert later via API)
- **When to use**: Bulk initial load of millions of vectors

**Example JSONL format**:
```jsonl
{"id": "doc1_chunk0", "embedding": [0.1, -0.2, 0.3, ...]}
{"id": "doc1_chunk1", "embedding": [0.2, -0.1, 0.4, ...]}
```

---

## Index Configuration Deep Dive

### `config { dimensions = var.vector_dimensions }`

**What it is**: The size of each embedding vector

**Common Values**:
- **768**: text-embedding-004 (Vertex AI)
- **1536**: text-embedding-ada-002 (OpenAI)
- **384**: all-MiniLM-L6-v2 (Sentence Transformers)

**Why it matters**:
- Must match your embedding model output
- Cannot change after index creation
- Larger dimensions = more storage, potentially better quality

**How to determine**:
```python
from vertexai.language_models import TextEmbeddingModel

model = TextEmbeddingModel.from_pretrained("text-embedding-004")
embedding = model.get_embeddings(["test"])[0]
dimensions = len(embedding.values)  # 768
```

**In this config**: `var.vector_dimensions = 768` (default)

### `approximate_neighbors_count = 100`

**What it is**: Target number of nearest neighbors the index should be optimized to find

**Purpose**: 
- Guides index construction algorithm
- Optimizes for finding ~100 similar vectors
- Doesn't limit your queries (you can request more or fewer)

**How it works**:
- Index structure is built to efficiently find ~100 neighbors
- Still works for other counts (1, 10, 50, 200) but may be slightly less optimal

**Choosing the value**:
- **10-50**: If you typically retrieve small numbers (Top-K=5-10)
- **100**: General purpose (good default)
- **200-500**: If you need many results or want to rerank

**In this config**: `100` (good default for Top-K=8)

**Recommendation**: Set to 2-3x your typical Top-K value

### `distance_measure_type = "DOT_PRODUCT_DISTANCE"`

**What it is**: How similarity between vectors is calculated

**Options**:
1. **DOT_PRODUCT_DISTANCE** (used here)
2. **EUCLIDEAN_DISTANCE**
3. **COSINE_DISTANCE**

**Detailed explanation in next section** ⬇️

---

## Distance Measures Explained

### 1. DOT_PRODUCT_DISTANCE

**Formula**: `distance = 1 - (A · B)` where `·` is dot product

**When to use**:
- ✅ **Normalized embeddings** (unit length vectors)
- ✅ **text-embedding-004** (Vertex AI embeddings are normalized)
- ✅ **Fast computation**
- ✅ **Semantic similarity** (when embeddings are normalized, dot product = cosine similarity)

**Example**:
```python
# Normalized vectors (length = 1.0)
vector_a = [0.5, 0.5, 0.5, ...]  # length = 1.0
vector_b = [0.6, 0.4, 0.5, ...]  # length = 1.0

dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
distance = 1 - dot_product  # Lower = more similar
```

**Why it works for normalized vectors**:
- Dot product of normalized vectors = cosine similarity
- Range: -1 (opposite) to 1 (identical)
- Distance: 0 (identical) to 2 (opposite)

**In this config**: ✅ Correct for text-embedding-004 (normalized)

### 2. COSINE_DISTANCE

**Formula**: `distance = 1 - cosine_similarity(A, B)`

**When to use**:
- ✅ **Non-normalized embeddings**
- ✅ **Direction matters more than magnitude**
- ✅ **General semantic similarity**

**Example**:
```python
cosine_sim = dot_product / (||A|| * ||B||)
distance = 1 - cosine_sim
```

**Comparison with DOT_PRODUCT**:
- For normalized vectors: COSINE = DOT_PRODUCT
- For non-normalized: COSINE accounts for vector magnitude

### 3. EUCLIDEAN_DISTANCE

**Formula**: `distance = sqrt(sum((A_i - B_i)²))`

**When to use**:
- ✅ **Absolute differences matter**
- ✅ **Magnitude is important**
- ✅ **Less common for text embeddings**

**Example**:
```python
distance = sqrt(sum((a - b)**2 for a, b in zip(vector_a, vector_b)))
```

**Comparison**:
- Measures actual distance in vector space
- Sensitive to vector magnitude
- Less intuitive for semantic similarity

### Choosing the Right Distance Measure

| Embedding Model | Normalized? | Recommended Distance |
|----------------|-------------|---------------------|
| text-embedding-004 | ✅ Yes | DOT_PRODUCT_DISTANCE |
| text-embedding-ada-002 | ❌ No | COSINE_DISTANCE |
| all-MiniLM-L6-v2 | ✅ Yes | DOT_PRODUCT_DISTANCE |
| Custom embeddings | Check | COSINE_DISTANCE (safe default) |

**In this config**: ✅ `DOT_PRODUCT_DISTANCE` is correct for text-embedding-004

---

## Algorithm Configuration: Tree-AH

### What is Tree-AH?

**Tree-AH** (Tree-based Approximate Nearest Neighbor with Asymmetric Hashing) is an algorithm for fast similarity search on large-scale vector datasets.

### How Tree-AH Works

```
┌─────────────────────────────────────────────────────────┐
│                    Tree-AH Algorithm                     │
│                                                           │
│  1. Build Tree Structure                                 │
│     - Organize vectors into hierarchical tree            │
│     - Each node contains multiple vectors                │
│                                                           │
│  2. Leaf Nodes                                           │
│     - Final level contains actual vectors                 │
│     - leaf_node_embedding_count = vectors per leaf       │
│                                                           │
│  3. Search Process                                       │
│     - Start at root, traverse down tree                  │
│     - Visit leaf_nodes_to_search_percent of leaves       │
│     - Return nearest neighbors from visited leaves       │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Configuration Parameters

#### `leaf_node_embedding_count = 1000`

**What it is**: Number of vectors stored in each leaf node

**Impact**:
- **Smaller (500-1000)**: More leaf nodes, more precise search, slower
- **Larger (2000-5000)**: Fewer leaf nodes, faster search, less precise

**Trade-offs**:
```
leaf_node_embedding_count = 500:
  ✅ More precise (searches more granular nodes)
  ❌ Slower (more nodes to traverse)
  ✅ Better for high-precision requirements

leaf_node_embedding_count = 2000:
  ✅ Faster (fewer nodes to traverse)
  ❌ Less precise (coarser granularity)
  ✅ Better for speed-critical applications
```

**In this config**: `1000` (balanced default)

**Recommendation**:
- **High precision needed**: 500-1000
- **Balanced**: 1000-1500 (default)
- **Speed critical**: 1500-3000

#### `leaf_nodes_to_search_percent = 7`

**What it is**: Percentage of leaf nodes to search during query

**Impact**:
- **Smaller (1-5%)**: Faster queries, may miss some results
- **Larger (10-20%)**: Slower queries, more thorough search

**How it works**:
```
Total leaf nodes: 10,000
leaf_nodes_to_search_percent = 7%
Nodes searched: 700 leaf nodes
```

**Trade-offs**:
```
leaf_nodes_to_search_percent = 3%:
  ✅ Very fast queries (~10-50ms)
  ❌ May miss some relevant results
  ✅ Good for real-time applications

leaf_nodes_to_search_percent = 15%:
  ✅ More thorough search
  ❌ Slower queries (~50-200ms)
  ✅ Better recall (finds more relevant results)
```

**In this config**: `7%` (balanced default)

**Recommendation**:
- **Real-time/low-latency**: 3-5%
- **Balanced**: 7-10% (default)
- **High recall needed**: 10-20%

### Algorithm Selection

**Why Tree-AH?**
- ✅ Scalable to millions of vectors
- ✅ Fast approximate search
- ✅ Good balance of speed and accuracy
- ✅ Production-proven

**Alternative Algorithms** (not in this config):
- **Brute Force**: Exact search (slow, only for small datasets)
- **LSH (Locality Sensitive Hashing)**: Different approach, similar performance

**Tree-AH is the recommended algorithm** for most RAG use cases.

---

## Index Endpoint and Deployment

### Resource 2: Index Endpoint

```hcl
resource "google_beta_vertex_ai_index_endpoint" "rag_index_endpoint" {
  count        = var.create_vector_search ? 1 : 0
  display_name = "rag-index-endpoint"
  region       = var.region
  
  depends_on = [google_project_service.apis]
}
```

**Purpose**: Creates the API endpoint infrastructure

**Key Fields**:
- `display_name`: Human-readable name
- `region`: Must match index region
- `count`: Conditional creation (same as index)

**What it provides**:
- Network endpoint URL
- Access control configuration
- Can host multiple deployed indexes

**State after creation**: Empty endpoint (no indexes deployed yet)

### Resource 3: Deployed Index

```hcl
resource "google_beta_vertex_ai_index_endpoint_deployed_index" "deployed" {
  count          = var.create_vector_search ? 1 : 0
  index_endpoint = google_beta_vertex_ai_index_endpoint.rag_index_endpoint[0].name
  deployed_index_id = "rag_chunks"
  index          = google_beta_vertex_ai_index.rag_index[0].name
  
  depends_on = [
    google_beta_vertex_ai_index.rag_index,
    google_beta_vertex_ai_index_endpoint.rag_index_endpoint
  ]
}
```

**Purpose**: Links index to endpoint, making it queryable

**Key Fields**:

#### `index_endpoint`
- **What**: Reference to the endpoint resource
- **Format**: Full resource name from endpoint
- **Example**: `projects/PROJECT/locations/REGION/indexEndpoints/ENDPOINT_ID`

#### `deployed_index_id = "rag_chunks"`
- **What**: Unique identifier for this deployment
- **Purpose**: Used in API calls to specify which index to query
- **Requirements**: 
  - Must be unique within the endpoint
  - Alphanumeric and hyphens only
  - Used in query code: `deployed_index_id="rag_chunks"`

#### `index`
- **What**: Reference to the index resource
- **Format**: Full resource name from index
- **Example**: `projects/PROJECT/locations/REGION/indexes/INDEX_ID`

**State after creation**: Index is deployed and ready for queries

### Deployment Process

```
1. Create Index (defines structure)
   ↓
2. Create Endpoint (creates API infrastructure)
   ↓
3. Deploy Index to Endpoint (links them together)
   ↓
4. Index is queryable via API
```

**Timeline**:
- Index creation: ~5-10 minutes
- Endpoint creation: ~2-5 minutes
- Deployment: ~10-30 minutes (depends on index size)

**Note**: The Terraform comment mentions deployment can be "finicky" - if it fails, deploy manually via `gcloud` or UI once, then reference the endpoint ID.

---

## Complete Workflow

### Step 1: Infrastructure Creation (Terraform)

```bash
# 1. Initialize Terraform
cd infra
terraform init

# 2. Plan
terraform plan

# 3. Apply (creates index, endpoint, deployment)
terraform apply
```

**What gets created**:
1. ✅ Index with configuration
2. ✅ Endpoint for API access
3. ✅ Deployed index (index → endpoint link)

### Step 2: Upsert Vectors (Application Code)

```python
from google.cloud import aiplatform
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import MatchingEngineIndexEndpoint

# Initialize
aiplatform.init(project=PROJECT_ID, location=REGION)

# Get endpoint
endpoint = MatchingEngineIndexEndpoint(
    index_endpoint_name=INDEX_ENDPOINT_NAME
)

# Prepare datapoints
datapoints = [
    {
        "id": "doc1_chunk0",
        "embedding": [0.1, -0.2, 0.3, ...]  # 768 dimensions
    },
    {
        "id": "doc1_chunk1",
        "embedding": [0.2, -0.1, 0.4, ...]
    }
]

# Upsert (add/update vectors)
endpoint.upsert_datapoints(
    deployed_index_id="rag_chunks",
    datapoints=datapoints
)
```

**Batch Upsert** (recommended):
```python
# Upsert in batches of 100-1000
batch_size = 100
for i in range(0, len(datapoints), batch_size):
    batch = datapoints[i:i+batch_size]
    endpoint.upsert_datapoints(
        deployed_index_id="rag_chunks",
        datapoints=batch
    )
```

### Step 3: Query Vectors (Application Code)

```python
# Generate query embedding
from vertexai.language_models import TextEmbeddingModel

embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
query_embedding = embedding_model.get_embeddings([user_query])[0].values

# Search
endpoint = MatchingEngineIndexEndpoint(index_endpoint_name=INDEX_ENDPOINT_NAME)

results = endpoint.find_neighbors(
    deployed_index_id="rag_chunks",
    queries=[list(query_embedding)],
    num_neighbors=8  # Top-K
)

# Process results
for neighbor in results[0]:
    print(f"ID: {neighbor.id}, Distance: {neighbor.distance}")
    # ID format: "doc_id::chunk_id"
```

### Complete Example

```python
# ingestion/processors/upsert_vector.py
def upsert_chunks(chunks: list, doc_id: str):
    """Upsert chunks to Vector Search."""
    endpoint = MatchingEngineIndexEndpoint(
        index_endpoint_name=os.getenv("VECTOR_INDEX_ENDPOINT")
    )
    
    datapoints = []
    for chunk in chunks:
        datapoints.append({
            "id": f"{doc_id}::{chunk['chunk_id']}",
            "embedding": chunk["embedding"]  # 768-dim vector
        })
    
    # Upsert in batches
    batch_size = 100
    for i in range(0, len(datapoints), batch_size):
        endpoint.upsert_datapoints(
            deployed_index_id=os.getenv("DEPLOYED_INDEX_ID"),
            datapoints=datapoints[i:i+batch_size]
        )

# service/app/rag/vertex_vector.py
def search(self, query_embedding: List[float], top_k: int):
    """Search for similar chunks."""
    endpoint = MatchingEngineIndexEndpoint(
        index_endpoint_name=self.index_endpoint
    )
    
    results = endpoint.find_neighbors(
        deployed_index_id=self.deployed_index_id,
        queries=[query_embedding],
        num_neighbors=top_k
    )
    
    return [
        {"id": n.id, "score": float(n.distance)}
        for n in results[0]
    ]
```

---

## Best Practices and Tuning

### 1. Dimension Configuration

**✅ Do**:
- Match embedding model dimensions exactly
- Verify dimensions before index creation
- Document which embedding model you're using

**❌ Don't**:
- Guess dimensions
- Use wrong dimensions (index won't work)
- Change dimensions after creation (must recreate index)

**Verification**:
```python
# Always verify dimensions
model = TextEmbeddingModel.from_pretrained("text-embedding-004")
test_embedding = model.get_embeddings(["test"])[0]
assert len(test_embedding.values) == 768  # Should match var.vector_dimensions
```

### 2. Distance Measure Selection

**✅ Do**:
- Use DOT_PRODUCT for normalized embeddings (text-embedding-004)
- Use COSINE for non-normalized embeddings
- Verify embedding normalization

**❌ Don't**:
- Mix distance measures with wrong embedding types
- Assume all embeddings are normalized

**Check Normalization**:
```python
import numpy as np

embedding = model.get_embeddings(["test"])[0].values
norm = np.linalg.norm(embedding)
print(f"Vector norm: {norm}")  # Should be ~1.0 for normalized
```

### 3. Algorithm Tuning

**For High Precision** (e.g., legal documents, medical records):
```hcl
algorithm_config {
  tree_ah_config {
    leaf_node_embedding_count = 500      # Smaller = more precise
    leaf_nodes_to_search_percent = 15    # Higher = more thorough
  }
}
```

**For Speed** (e.g., real-time chat, high-traffic):
```hcl
algorithm_config {
  tree_ah_config {
    leaf_node_embedding_count = 2000     # Larger = faster
    leaf_nodes_to_search_percent = 3     # Lower = faster
  }
}
```

**For Balanced** (most RAG use cases):
```hcl
algorithm_config {
  tree_ah_config {
    leaf_node_embedding_count = 1000     # Default
    leaf_nodes_to_search_percent = 7     # Default
  }
}
```

### 4. Approximate Neighbors Count

**Rule of thumb**: Set to 2-3x your typical Top-K

**Examples**:
- Top-K = 5 → `approximate_neighbors_count = 15`
- Top-K = 8 → `approximate_neighbors_count = 100` ✅ (current config)
- Top-K = 20 → `approximate_neighbors_count = 50-100`

### 5. Region Selection

**✅ Do**:
- Use same region for index, embeddings, and queries
- Consider data residency requirements
- Choose region close to users/applications

**Common Regions**:
- `us-central1`: Central US (good default)
- `us-east1`: East US
- `europe-west1`: Western Europe
- `asia-southeast1`: Southeast Asia

### 6. Index Updates

**Upsert Strategy**:
- ✅ Use batch upserts (100-1000 datapoints)
- ✅ Update existing IDs to modify vectors
- ✅ Delete old vectors before upserting new ones (if needed)

**Deletion**:
```python
# Delete vectors by ID
endpoint.remove_datapoints(
    deployed_index_id="rag_chunks",
    datapoint_ids=["doc1_chunk0", "doc1_chunk1"]
)
```

**Reindexing**:
- For major changes, consider creating new index
- Deploy to same endpoint with different `deployed_index_id`
- Switch traffic, then delete old deployment

### 7. Monitoring and Observability

**Key Metrics to Track**:
- Query latency (p50, p95, p99)
- Query throughput (queries per second)
- Index size (number of vectors)
- Upsert success rate
- Error rates

**Cloud Monitoring**:
```python
# Enable monitoring in Terraform (future enhancement)
# Or use Cloud Monitoring API
from google.cloud import monitoring_v3

client = monitoring_v3.MetricServiceClient()
# Create custom metrics for query performance
```

---

## Troubleshooting Common Issues

### Issue 1: "Index not found" or "Endpoint not found"

**Symptoms**:
- API calls fail with resource not found
- Terraform shows resources created but queries fail

**Causes**:
- Region mismatch
- Wrong resource names
- Resources not fully created

**Solutions**:
```python
# Verify region matches
assert INDEX_REGION == ENDPOINT_REGION == QUERY_REGION

# Verify resource names (use full resource names)
index_name = "projects/PROJECT/locations/REGION/indexes/INDEX_ID"
endpoint_name = "projects/PROJECT/locations/REGION/indexEndpoints/ENDPOINT_ID"

# Wait for deployment to complete (can take 10-30 minutes)
```

### Issue 2: "Dimension mismatch"

**Symptoms**:
- Upsert fails with dimension error
- Queries return errors

**Causes**:
- Embedding dimensions don't match index configuration
- Wrong embedding model

**Solutions**:
```python
# Verify dimensions match
embedding = model.get_embeddings(["test"])[0].values
assert len(embedding) == 768  # Must match var.vector_dimensions

# Check index configuration
# In Terraform: dimensions = 768
# In code: embedding must be 768 dimensions
```

### Issue 3: "Deployment failed" in Terraform

**Symptoms**:
- Terraform apply fails on `deployed_index` resource
- Error about deployment

**Causes**:
- Index or endpoint not ready
- Provider version issues
- Network/permissions issues

**Solutions**:
```bash
# Option 1: Deploy manually via gcloud
gcloud ai index-endpoints deploy-index ENDPOINT_ID \
  --deployed-index-id=rag_chunks \
  --index=INDEX_ID \
  --display-name="RAG Chunks"

# Option 2: Use Terraform import after manual deployment
terraform import \
  google_beta_vertex_ai_index_endpoint_deployed_index.deployed \
  projects/PROJECT/locations/REGION/indexEndpoints/ENDPOINT_ID/deployedIndexes/rag_chunks

# Option 3: Update Terraform provider version
terraform init -upgrade
```

### Issue 4: Slow Query Performance

**Symptoms**:
- Queries take >200ms
- High latency

**Causes**:
- Too many leaf nodes searched
- Large index size
- Network latency

**Solutions**:
```hcl
# Reduce search percentage (faster, less thorough)
algorithm_config {
  tree_ah_config {
    leaf_nodes_to_search_percent = 3  # Down from 7
  }
}

# Or increase leaf node size (fewer nodes to search)
algorithm_config {
  tree_ah_config {
    leaf_node_embedding_count = 2000  # Up from 1000
  }
}
```

### Issue 5: Low Recall (Missing Relevant Results)

**Symptoms**:
- Relevant chunks not retrieved
- Low answer quality

**Causes**:
- Too few leaf nodes searched
- Index not optimized for query patterns

**Solutions**:
```hcl
# Increase search percentage (more thorough)
algorithm_config {
  tree_ah_config {
    leaf_nodes_to_search_percent = 15  # Up from 7
  }
}

# Or decrease leaf node size (more granular)
algorithm_config {
  tree_ah_config {
    leaf_node_embedding_count = 500  # Down from 1000
  }
}
```

### Issue 6: Upsert Failures

**Symptoms**:
- Datapoints not appearing in index
- Errors during upsert

**Causes**:
- Batch size too large
- Invalid datapoint format
- Rate limiting

**Solutions**:
```python
# Use smaller batches
batch_size = 100  # Instead of 1000

# Verify datapoint format
for dp in datapoints:
    assert "id" in dp
    assert "embedding" in dp
    assert len(dp["embedding"]) == 768
    assert isinstance(dp["id"], str)

# Add retry logic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def upsert_with_retry(endpoint, datapoints):
    endpoint.upsert_datapoints(
        deployed_index_id="rag_chunks",
        datapoints=datapoints
    )
```

---

## Configuration Summary

### Your Current Configuration

```hcl
resource "google_beta_vertex_ai_index" "rag_index" {
  display_name = "rag-chunks-index"
  region       = "us-central1"  # or var.region
  
  metadata {
    contents_delta_uri = "gs://BUCKET/vector_index_seed/"  # Optional, can be empty
    config {
      dimensions = 768                                    # ✅ text-embedding-004
      approximate_neighbors_count = 100                  # ✅ Good for Top-K=8
      distance_measure_type = "DOT_PRODUCT_DISTANCE"     # ✅ Correct for normalized
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count = 1000               # ✅ Balanced
          leaf_nodes_to_search_percent = 7               # ✅ Balanced
        }
      }
    }
  }
}
```

### Configuration Checklist

- [x] **Dimensions**: 768 (matches text-embedding-004)
- [x] **Distance**: DOT_PRODUCT (correct for normalized embeddings)
- [x] **Algorithm**: Tree-AH (recommended)
- [x] **Leaf nodes**: 1000 (balanced default)
- [x] **Search percent**: 7% (balanced default)
- [x] **Approximate neighbors**: 100 (good for Top-K=8)

### When to Adjust

**Increase precision**:
- `leaf_node_embedding_count = 500`
- `leaf_nodes_to_search_percent = 15`

**Increase speed**:
- `leaf_node_embedding_count = 2000`
- `leaf_nodes_to_search_percent = 3`

**Different embedding model**:
- Update `dimensions` to match model
- Update `distance_measure_type` if not normalized

---

## Conclusion

### Key Takeaways

1. **Three Components**: Index (structure) → Endpoint (API) → Deployed Index (active)
2. **Dimensions Matter**: Must match embedding model exactly
3. **Distance Measure**: DOT_PRODUCT for normalized embeddings (text-embedding-004)
4. **Algorithm Tuning**: Balance speed vs. precision based on use case
5. **Region Consistency**: Keep index, endpoint, and queries in same region

### Your Configuration is Well-Tuned For

- ✅ **text-embedding-004** embeddings (768 dimensions, normalized)
- ✅ **Top-K=8** retrieval (approximate_neighbors_count=100)
- ✅ **Balanced performance** (speed and precision)
- ✅ **General RAG use cases**

### Next Steps

1. **Deploy**: Run `terraform apply`
2. **Upsert**: Add vectors via API
3. **Query**: Test search functionality
4. **Monitor**: Track query performance
5. **Tune**: Adjust algorithm config if needed

**Happy Searching! 🚀**
