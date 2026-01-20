## Hybrid RAG on GCP with Vertex AI, Vector Search & Neo4j

This project implements a **hybrid RAG (Retrieval-Augmented Generation)** system on Google Cloud:

- **Vertex AI Text Embeddings** + **Vertex AI Vector Search** for semantic retrieval  
- **Neo4j** for document / chunk / entity graph storage  
- **FastAPI on Cloud Run** as the RAG API (`/search`, `/ask`)  
- **Cloud Functions Gen2** ingestion pipeline triggered by GCS uploads  

You can upload documents to GCS, they are ingested (chunked, embedded, indexed, written to Neo4j), and then queried via a simple HTTP API.

---

## High-Level Architecture

- **Storage & Ingestion**
  - Upload documents (e.g., `TUTORIAL.md`) to `gs://rag-vertex-ai-bucket/uploads/…`
  - GCS → Pub/Sub → Cloud Functions Gen2 (`rag-ingest-doc`)
  - Ingestion steps:
    1. Extract text from PDF / TXT / MD
    2. Chunk text (token-aware, overlapping)
    3. Generate embeddings with `text-embedding-004`
    4. Upsert embeddings to Vertex AI Vector Search
    5. Extract simple entities (regex-based)
    6. Upsert Document / Chunk / Entity graph to Neo4j

- **Serving**
  - FastAPI app on Cloud Run (`rag-agent-api`)
  - `/search`:
    - Embeds question
    - Runs Vector Search
    - Expands via Neo4j graph
    - Merges & scores results (hybrid RAG)
  - `/ask`:
    - Same retrieval as `/search`
    - Builds context from `text_preview`
    - Calls **Gemini** via API key (`gemini-2.5-flash-lite`)

---

## Prerequisites

- GCP project (this repo assumes: `rag-vertex-ai-with-neoj`)
- Billing enabled
- Tools installed locally:
  - `gcloud`
  - `gsutil`
  - `terraform`
  - `docker`
- A **Neo4j** instance (Aura or self-hosted) – the repo uses Aura
- A **Gemini API key** (Generative AI API key)

---

## Infrastructure Setup (Terraform)

Infra code lives in `infra/`.

1. **Configure variables** (already set up for the example project):

`infra/terraform.tfvars`:

- `project_id`
- `region`
- `bucket_name`
- `cloud_run_image_uri`
- `neo4j_uri`, `neo4j_user`, `neo4j_password`
- models and top_k

2. **Deploy infra**

```bash
cd infra
terraform init
terraform apply -lock=false
```

This provisions:
- GCS bucket (`rag-vertex-ai-bucket`)
- Pub/Sub topic & notification
- Cloud Functions Gen2 ingest function
- Vertex AI index + endpoint
- Cloud Run service (wiring env vars)

---

## Building & Deploying the RAG API (Cloud Run)

The API lives under `service/app/`.

1. **Build and push the Docker image**

```powershell
cd C:\Users\aloag\personal-study\gcp-gen-ai

$env:PROJECT_ID = "rag-vertex-ai-with-neoj"
$env:REGION = "us-central1"
$env:REGISTRY = "us-central1-docker.pkg.dev/$env:PROJECT_ID/rag-artifacts"

docker build -t "$env:REGISTRY/rag-api:latest" ./service
docker push "$env:REGISTRY/rag-api:latest"
```

2. **Deploy / update Cloud Run**

```powershell
gcloud run deploy rag-agent-api `
  --image "$env:REGISTRY/rag-api:latest" `
  --region $env:REGION `
  --platform managed `
  --allow-unauthenticated `
  --project $env:PROJECT_ID
```

> Terraform can also manage Cloud Run via `cloud_run_image_uri` in `terraform.tfvars`.

---

## Gemini via API Key

The API uses `GEMINI_API_KEY` + HTTP calls to:

`https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent`

Implementation: `service/app/rag/llm.py`

- If `GEMINI_API_KEY` is set → uses REST endpoint with that key
- Otherwise → falls back to Vertex AI SDK + ADC (requires Generative AI API enabled)

### Set `GEMINI_API_KEY` on Cloud Run

```powershell
gcloud run services update rag-agent-api `
  --region=us-central1 `
  --project=rag-vertex-ai-with-neoj `
  --set-env-vars="PROJECT_ID=rag-vertex-ai-with-neoj,REGION=us-central1,VECTOR_INDEX_ENDPOINT=projects/rag-vertex-ai-with-neoj/locations/us-central1/indexEndpoints/6627902271722094592,DEPLOYED_INDEX_ID=rag_chunks_v2,EMBEDDING_MODEL=text-embedding-004,GENERATIVE_MODEL=gemini-2.5-flash-lite,TOP_K=8,NEO4J_URI=neo4j+s://<your-neo4j-host>,NEO4J_USER=<user>,NEO4J_PASSWORD=<password>,GEMINI_API_KEY=<your_gemini_api_key>"
```

Adjust `NEO4J_*` to your instance.

---

## Ingestion Pipeline – How to Use

1. **Upload a document**

```powershell
cd C:\Users\aloag\personal-study\gcp-gen-ai
gsutil cp TUTORIAL.md gs://rag-vertex-ai-bucket/uploads/tutorial-v2.md
```

2. **Wait for ingestion**

The Cloud Function logs should include:

- `Successfully upserted <N> chunks to Vector Search`
- `Successfully upserted to Neo4j`
- `Ingestion complete: uploads_tutorial_v2_md`

3. **Check logs (optional)**

```powershell
gcloud functions logs read rag-ingest-doc `
  --region=us-central1 `
  --limit=50 `
  --project=rag-vertex-ai-with-neoj
```

---

## Querying the API

The Cloud Run URL looks like:

`https://rag-agent-api-XXXXXXXXXXXX.us-central1.run.app`

### `/search` – retrieve chunks

```powershell
$body = @{ question = "What is hybrid RAG?"; top_k = 5 } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "https://rag-agent-api-<api-link>/search" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

Response:

- `results`: list of citations with:
  - `chunk_id`
  - `doc_id`
  - `source`
  - `score`
  - `text_preview` (from Neo4j for ingested docs)

### `/ask` – answer with citations

```powershell
$body = @{ question = "What is hybrid RAG?"; top_k = 5 } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "https://rag-agent-api-<api-link>/ask" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

Response:

- `answer`: Gemini-generated answer grounded in context
- `citations`: same format as `/search` results

#### Example `/ask` JSON response

```json
{
  "answer": "RAG (Retrieval-Augmented Generation) is a technique that improves LLM responses by first retrieving relevant context from a knowledge base and then augmenting the LLM prompt with this retrieved context [chunk:uploads_tutorial_v2_md_chunk_4].",
  "citations": [
    {
      "chunk_id": "uploads_tutorial_v2_md_chunk_3",
      "doc_id": "uploads_tutorial_v2_md",
      "source": "vector_search",
      "score": 0.60797110503196716,
      "text_preview": "Generate Query Embedding ... 3. Vector Search (top-K chunks) ... 4. Extract Query Entities ..."
    },
    {
      "chunk_id": "uploads_test_neo4j_md_chunk_3",
      "doc_id": "uploads_test_neo4j_md",
      "source": "vector_search",
      "score": 0.60,
      "text_preview": "Hybrid RAG combines vector search with graph traversal for better retrieval. This unique test document demonstrates Neo4j integration..."
    }
  ]
}
```

If context is missing (e.g., old docs without Neo4j data), the answer may correctly be `"I don't know."`.

---

## Cleaning Old Vector Search Data

If you ingested documents **before** Neo4j integration, their chunks may not have `text_preview`. Use the cleanup scripts under `scripts/`:

- `scripts/cleanup-vector-index.ps1` – PowerShell
- `scripts/cleanup-vector-index.sh` – Bash

### PowerShell usage

```powershell
cd C:\Users\aloag\personal-study\gcp-gen-ai\scripts

# Remove all known old docs
.\cleanup-vector-index.ps1

# Or remove a specific doc (example)
.\cleanup-vector-index.ps1 -DocId "uploads_test_no_metadata_md" -MaxChunks 100
```

Then re-upload documents to re-ingest them with Neo4j metadata.

---

## Key Source Files

- **Ingestion**
  - `ingestion/function/main.py` – Cloud Function entrypoint
  - `ingestion/processors/extract_text.py`
  - `ingestion/processors/chunk.py`
  - `ingestion/processors/embed.py`
  - `ingestion/processors/upsert_vector.py`
  - `ingestion/processors/extract_entities.py`
  - `ingestion/processors/upsert_graph.py`

- **API**
  - `service/app/main.py` – FastAPI app
  - `service/app/rag/hybrid.py` – merge vector + graph results, Neo4j fallback for `text_preview`
  - `service/app/rag/vertex_vector.py` – Vector Search client
  - `service/app/rag/graph_neo4j.py` – Neo4j client
  - `service/app/rag/llm.py` – Gemini client (API key + ADC modes)

- **Infra**
  - `infra/main.tf` – Terraform for GCS, Pub/Sub, Functions, Vector Search, Cloud Run
  - `infra/variables.tf`, `infra/terraform.tfvars`

Additional docs:

- `INGESTION_IMPLEMENTATION_PLAN.md` – detailed ingestion design
- `NEO4J_IMPLEMENTATION.md` – graph schema & Neo4j details
- `PERFORMANCE_OPTIMIZATIONS.md` – notes on batching & performance
- `QUERY_API_EXAMPLES.md` – more query examples

---

## Troubleshooting

- **API returns `"I don't know."`**
  - Check `/search` to see if `text_preview` is populated.
  - If `text_preview` is empty and `doc_id` looks like an old upload, run cleanup and re-upload.

- **Cloud Run revision fails to start with Neo4j error**
  - Ensure `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` are set on the service.

- **Gemini errors / model not available**
  - Ensure `GEMINI_API_KEY` is set.
  - Or enable the Generative AI API and use Vertex AI mode.

For deeper details, see the markdown docs mentioned above.
