## Debugging Guide: Major Issues & Helper Scripts

This file summarizes the **major bugs** encountered while building the hybrid RAG system and the **scripts/commands** that helped debug and fix them.

---

## 1. Cloud Function Timeouts & Neo4j Slowness

- **Symptoms**:
  - Ingestion Cloud Function (`rag-ingest-doc`) hit 30s+ and then 120s timeouts.
  - Logs showed many small Neo4j writes per chunk/entity.
- **Root Cause**:
  - Neo4j upsert logic ran **one query per chunk/entity**, leading to hundreds of round trips.
- **Fix**:
  - Rewrote `ingestion/processors/upsert_graph.py` to use **batched Cypher with `UNWIND`** for:
    - Documents
    - Chunks
    - Entities
    - `MENTIONS` relationships
  - Result: ~6–10x speedup and ingestion well under function timeout.
- **Helpful commands**:
  - Check logs:
    ```powershell
    gcloud functions logs read rag-ingest-doc `
      --region=us-central1 `
      --limit=50 `
      --project=rag-vertex-ai-with-neoj
    ```

---

## 2. Vertex AI Embedding Token Limit Errors

- **Symptoms**:
  - `InvalidArgument: 400 Unable to submit request because the input token count is 20923 but the model supports up to 20000`
- **Root Cause**:
  - In `ingestion/processors/embed.py`, we sent too many tokens in a single batch to `text-embedding-004`.
- **Fix**:
  - Implemented **token-aware batching**, estimating tokens per chunk and capping each batch to ~15k tokens (safety margin below the 20k limit).
- **Helpful commands**:
  - Inspect function logs for embedding errors (same `gcloud functions logs read` as above).

---

## 3. Vector Search `embedding_metadata` Not Supported

- **Symptoms**:
  - `ValueError: Unknown field for IndexDatapoint: embedding_metadata` during upsert.
- **Root Cause**:
  - The library version `google-cloud-aiplatform==1.67.0` did **not support** `embedding_metadata` on `IndexDatapoint`.
- **Fix**:
  - Removed metadata storage from `upsert_vector.py`.
  - Moved all `text_preview` storage to Neo4j and added a **fallback lookup** in the API.
    - `service/app/rag/hybrid.py` → `fetch_text_preview_from_neo4j()` + caching.

---

## 4. Old Documents Without Neo4j Data → `"I don't know"` Answers

- **Symptoms**:
  - `/ask` returned `"I don't know."` even though `/search` showed good matches.
  - `/search` results had **empty `text_preview`** for many `doc_id`s (e.g., `uploads_test_no_metadata_md`).
- **Root Causes**:
  1. Documents ingested **before** Neo4j integration had no graph nodes, so `text_preview` was unavailable.
  2. Vector Search still returned these old chunks with higher similarity than new documents.
- **Fixes**:
  - Implemented Neo4j fallback in `merge_and_score()` (`hybrid.py`):
    - If Vector Search `text_preview` is empty, call `fetch_text_preview_from_neo4j()`.
  - **Cleaned up old datapoints** from the Vector Search index and re-uploaded documents.

### Cleanup Scripts

- **PowerShell**: `scripts/cleanup-vector-index.ps1`
  - Removes old document chunks from the Vector Search index.
  - Usage:
    ```powershell
    cd C:\Users\aloag\personal-study\gcp-gen-ai\scripts

    # Remove all known old docs
    .\cleanup-vector-index.ps1

    # Or remove a specific document
    .\cleanup-vector-index.ps1 -DocId "uploads_test_no_metadata_md" -MaxChunks 100
    ```

  - **Manual one-off delete example** (for a single document ID):
    ```powershell
    $INDEX_ID = "projects/rag-vertex-ai-with-neoj/locations/us-central1/indexes/6899983021085032448"
    $PROJECT_ID = "rag-vertex-ai-with-neoj"
    $doc = "uploads_test_no_metadata_md"
    $chunkIds = (0..80 | ForEach-Object { "$doc::${doc}_chunk_$_" }) -join ","
    gcloud ai indexes remove-datapoints $INDEX_ID --datapoint-ids=$chunkIds --project=$PROJECT_ID
    ```

- **Bash**: `scripts/cleanup-vector-index.sh`
  - Same idea for shell environments:
    ```bash
    cd /path/to/gcp-gen-ai/scripts

    # All known old docs
    ./cleanup-vector-index.sh

    # Specific document
    ./cleanup-vector-index.sh uploads_test_no_metadata_md 100
    ```

---

## 5. UTF-16 Text Files Breaking Ingestion

- **Symptoms**:
  - Ingestion errors for `test-unique.txt`:
    - `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`
- **Root Cause**:
  - PowerShell `echo "..." > file.txt` created UTF-16 encoded files by default.
  - The extractor expected UTF-8.
- **Fix**:
  - Create test files using **explicit UTF-8 encoding** or use a proper editor.
- **Helper command (PowerShell)**:
  ```powershell
  [System.IO.File]::WriteAllText(
      "test-neo4j.txt",
      "Hybrid RAG combines vector search with graph traversal...",
      [System.Text.Encoding]::UTF8
  )
  gsutil cp test-neo4j.txt gs://rag-vertex-ai-bucket/uploads/test-neo4j.txt
  ```

---

## 6. Cloud Run Failing to Start After `gcloud run services update`

- **Symptoms**:
  - Error during update: *"The user-provided container failed to start and listen on the port..."*
  - Logs showed:
    - `neo4j.exceptions.ConfigurationError: URI scheme b'' is not supported`  
      → `NEO4J_URI` was **empty**.
- **Root Cause**:
  - Running `gcloud run services update ... --set-env-vars=...` **overwrote** existing env vars, dropping Neo4j settings.
- **Fix**:
  - Always include **all required env vars** in `--set-env-vars` when updating manually.
  - Example:
    ```powershell
    gcloud run services update rag-agent-api `
      --region=us-central1 `
      --project=rag-vertex-ai-with-neoj `
      --set-env-vars="PROJECT_ID=rag-vertex-ai-with-neoj,REGION=us-central1,VECTOR_INDEX_ENDPOINT=projects/rag-vertex-ai-with-neoj/locations/us-central1/indexEndpoints/6627902271722094592,DEPLOYED_INDEX_ID=rag_chunks_v2,EMBEDDING_MODEL=text-embedding-004,GENERATIVE_MODEL=gemini-2.5-flash-lite,TOP_K=8,NEO4J_URI=neo4j+s://<your-neo4j-host>,NEO4J_USER=<user>,NEO4J_PASSWORD=<password>,GEMINI_API_KEY=<your_gemini_api_key>"
    ```
  - Alternatively, let **Terraform manage env vars** (see `infra/main.tf`).

---

## 7. Gemini Model / Generative AI API Issues

- **Original Symptoms** (Vertex mode only):
  - Errors such as:
    - `"Gemini model 'gemini-1.5-flash' is not available. Please enable the Generative AI API"`
- **Root Cause**:
  - Generative AI API not enabled or model not accessible via Vertex AI in that project/region.
- **Final Fix**:
  - Updated `service/app/rag/llm.py` to optionally use **Gemini via API key**:
    - If `GEMINI_API_KEY` is set → use REST endpoint `.../models/gemini-2.5-flash-lite:generateContent?key=...`
    - Else → fall back to Vertex AI SDK (`vertexai.GenerativeModel`).
- **Helpful commands**:
  - Enable APIs (if using Vertex mode):
    ```powershell
    gcloud config set project rag-vertex-ai-with-neoj
    gcloud services enable aiplatform.googleapis.com
    gcloud services enable generativelanguage.googleapis.com
    ```
  - Set `GEMINI_API_KEY` on Cloud Run (API key mode):
    ```powershell
    gcloud run services update rag-agent-api `
      --region=us-central1 `
      --project=rag-vertex-ai-with-neoj `
      --set-env-vars="...,GEMINI_API_KEY=<your_gemini_api_key>"
    ```

---

## 8. Helpful Testing & Debugging Scripts

### 8.1 `QUERY_API_EXAMPLES.md`

- Contains ready-made examples for:
  - PowerShell calls to `/search` and `/ask`
  - cURL examples
  - Python examples
- Used to quickly verify:
  - API URL and endpoints
  - Payload shape (`question`, `top_k`)
  - That `text_preview` and `citations` are correctly returned.

### 8.2 Quick Test Script – `test-api.ps1` (inline in `QUERY_API_EXAMPLES.md`)

- PowerShell helper to call either `/search` or `/ask`:
  ```powershell
  .\test-api.ps1 -Question "What is hybrid RAG?"       # search
  .\test-api.ps1 -Question "Explain embeddings" -Ask   # ask
  ```
- Helped confirm:
  - When answers were `"I don't know"` due to missing context.
  - That citations and previews matched expectations after fixes.

---

## 9. General Debugging Tips Used in This Project

- **Check logs early and often**:
  - Cloud Functions: `gcloud functions logs read ...`
  - Cloud Run: `gcloud run services logs read ...`
- **Keep infra as code**:
  - Prefer Terraform for env vars and service settings to avoid drift.
- **Use small test documents**:
  - e.g., `test-neo4j.txt` with unique phrases to isolate retrieval behavior.
- **Clean up old index data** when schemas or storage strategies change.

This file should give you a quick reference to the most common failure modes and the tools you already have in this repo to debug them.

