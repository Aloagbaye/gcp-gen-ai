# Neo4j Implementation Summary

## Overview
Neo4j graph storage has been implemented to store document metadata, chunks, and entities. This enables:
1. **Graph-based retrieval** - Find related chunks via entity relationships
2. **Text preview storage** - Store `text_preview` in Neo4j when Vector Search metadata isn't available
3. **Hybrid RAG** - Combine vector search with graph traversal for better results

## Implementation Details

### Step 6: Entity Extraction (`extract_entities.py`)

**Purpose**: Extract named entities from chunks using regex-based heuristics.

**Features**:
- Extracts capitalized words/phrases (potential proper nouns)
- Finds acronyms (2-5 uppercase letters)
- Simple entity type classification (TECHNOLOGY, ORGANIZATION, LOCATION, OTHER)
- Deduplication and frequency-based ranking
- Returns top 50 entities per document

**Entity Types**:
- `TECHNOLOGY`: Contains keywords like "api", "sdk", "cloud", "platform"
- `ORGANIZATION`: Contains keywords like "inc", "corp", "company" or is an acronym
- `LOCATION`: Contains location-related keywords
- `OTHER`: Default for all other entities

**Future Enhancement**: Can be upgraded to use Gemini for better Named Entity Recognition (NER).

### Step 7: Neo4j Graph Storage (`upsert_graph.py`)

**Purpose**: Store document, chunks, and entities in Neo4j graph database.

**Graph Schema**:
```
(:Document {doc_id, gcs_uri, file_type, file_size, title, page_count, created_at})
  -[:HAS_CHUNK {order}]-> (:Chunk {chunk_id, doc_id, chunk_index, text_preview, page, token_count})
    -[:MENTIONS]-> (:Entity {name, type})
```

**Operations**:
1. **Document Node**: MERGE (create or update) Document node with metadata
2. **Chunk Nodes**: MERGE Chunk nodes and link to Document via `HAS_CHUNK` relationship
3. **Entity Nodes**: MERGE Entity nodes
4. **MENTIONS Relationships**: Link chunks to entities that appear in their text

**Error Handling**: Gracefully handles Neo4j connection failures without breaking ingestion.

### Step 8: Integration (`main.py`)

**Pipeline Flow**:
1. Extract text from GCS file
2. Chunk text into overlapping segments
3. Generate embeddings for chunks
4. Upsert embeddings to Vector Search
5. **Extract entities from chunks** (NEW)
6. **Upsert to Neo4j graph** (NEW)

**Environment Variables Required**:
- `NEO4J_URI`: Neo4j connection URI (e.g., `neo4j+s://xxx.databases.neo4j.io`)
- `NEO4J_USER`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password

### API Integration (`hybrid.py`)

**Text Preview Fallback**:
- When Vector Search returns empty `text_preview`, the API now fetches it from Neo4j
- Uses caching to avoid repeated Neo4j queries
- Falls back gracefully if Neo4j is unavailable

**Function Updates**:
- `merge_and_score()` now accepts `graph_client` parameter
- `fetch_text_preview_from_neo4j()` retrieves text_preview from Neo4j when needed

## Files Created/Modified

### New Files:
- `ingestion/processors/extract_entities.py` - Entity extraction logic
- `ingestion/processors/upsert_graph.py` - Neo4j graph storage logic

### Modified Files:
- `ingestion/function/main.py` - Added entity extraction and Neo4j upsert steps
- `service/app/rag/hybrid.py` - Added Neo4j text_preview fallback
- `service/app/main.py` - Updated to pass graph_client to merge_and_score

## Testing

### 1. Deploy Updated Ingestion Function

```powershell
cd C:\Users\aloag\personal-study\gcp-gen-ai\infra
terraform apply -lock=false -auto-approve
```

### 2. Upload a Document

```powershell
gsutil cp TUTORIAL.md gs://rag-vertex-ai-bucket/uploads/test-neo4j.md
```

### 3. Check Ingestion Logs

```powershell
gcloud functions logs read rag-ingest-doc --region=us-central1 --limit=50 | Select-String -Pattern "Step 5|Step 6|entities|Neo4j|Successfully"
```

Expected output:
- "Step 5: Extracting entities..."
- "Extracted X unique entities"
- "Step 6: Upserting to Neo4j graph..."
- "Created/updated Document node"
- "Created/updated X Chunk nodes"
- "Created/updated X Entity nodes"
- "Successfully upserted to Neo4j"

### 4. Verify Neo4j Data

Connect to your Neo4j instance and run:

```cypher
// Check documents
MATCH (d:Document) RETURN d LIMIT 5

// Check chunks
MATCH (c:Chunk) RETURN c.chunk_id, c.text_preview LIMIT 5

// Check entities
MATCH (e:Entity) RETURN e.name, e.type LIMIT 10

// Check relationships
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
RETURN d.doc_id, c.chunk_id, e.name LIMIT 10
```

### 5. Test API with Neo4j Fallback

```powershell
$body = @{
    question = "What is hybrid RAG?"
    top_k = 5
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "https://rag-agent-api-cukcysp7ta-uc.a.run.app/ask" `
  -Method POST -Body $body -ContentType "application/json"

# Check if text_preview is populated
$response.citations | Select-Object chunk_id, text_preview | Format-Table
```

## Configuration

### Terraform Variables

Neo4j credentials are already configured in `infra/variables.tf`:
- `neo4j_uri`
- `neo4j_user`
- `neo4j_password`

These are automatically passed to:
- Cloud Function (ingestion) via environment variables
- Cloud Run (API) via environment variables

### Neo4j Setup Options

1. **Neo4j Aura** (Cloud):
   - Create instance at https://neo4j.com/cloud/aura/
   - Get connection URI, username, and password
   - Add to `terraform.tfvars`

2. **Self-Hosted Neo4j**:
   - Install Neo4j on your infrastructure
   - Configure connection URI
   - Add credentials to `terraform.tfvars`

## Benefits

1. **Text Preview Storage**: Solves the Vector Search metadata limitation
2. **Graph Traversal**: Enables finding related chunks via entity relationships
3. **Hybrid Search**: Combines semantic similarity (vector) with structured relationships (graph)
4. **Better Context**: `/ask` endpoint now has access to chunk text via Neo4j

## Next Steps

1. **Deploy**: Run `terraform apply` to deploy updated ingestion function
2. **Re-upload Documents**: Upload documents to trigger ingestion with Neo4j storage
3. **Test API**: Verify `/ask` endpoint returns proper answers with text_preview
4. **Monitor**: Check Neo4j for stored data and relationships

## Troubleshooting

### Neo4j Connection Errors

If you see "Warning: Neo4j credentials not configured":
- Check environment variables in Terraform
- Verify `terraform.tfvars` has Neo4j credentials
- Run `terraform apply` to update function environment

### Empty Entities

If no entities are extracted:
- Check extraction logs for patterns matched
- Adjust regex patterns in `extract_entities.py` if needed
- Consider upgrading to Gemini-based NER for better results

### Missing Text Preview

If `text_preview` is still empty:
- Verify Neo4j has chunk data: `MATCH (c:Chunk) RETURN c LIMIT 5`
- Check API logs for Neo4j connection errors
- Ensure graph_client is properly initialized in API
