# Querying the RAG API After Document Upload

After successfully uploading and ingesting documents, you can query them using the API endpoints.

## API Endpoints

**Base URL**: `https://rag-agent-api-cukcysp7ta-uc.a.run.app`

### 1. `/search` - Search for Relevant Chunks

Returns matching document chunks with citations.

**Request Format**:
```json
{
  "question": "your question here",
  "top_k": 5  // optional, defaults to 8
}
```

**Response Format**:
```json
{
  "results": [
    {
      "chunk_id": "doc_id_chunk_0",
      "doc_id": "doc_id",
      "source": "gs://bucket/path/to/file.pdf",
      "score": 0.95,
      "text_preview": "First 240 characters of the chunk..."
    }
  ]
}
```

### 2. `/ask` - Get AI-Generated Answer

Returns an AI-generated answer based on relevant chunks, with citations.

**Request Format**:
```json
{
  "question": "your question here",
  "top_k": 5  // optional, defaults to 8
}
```

**Response Format**:
```json
{
  "answer": "AI-generated answer based on the documents...",
  "citations": [
    {
      "chunk_id": "doc_id_chunk_0",
      "doc_id": "doc_id",
      "source": "gs://bucket/path/to/file.pdf",
      "score": 0.95,
      "text_preview": "First 240 characters of the chunk..."
    }
  ]
}
```

---

## PowerShell Examples

### Example 1: Search for Relevant Chunks

```powershell
$apiUrl = "https://rag-agent-api-cukcysp7ta-uc.a.run.app/search"

$body = @{
    question = "What is hybrid RAG?"
    top_k = 5
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri $apiUrl -Method POST -Body $body -ContentType "application/json"

# Display results
$response.results | ForEach-Object {
    Write-Host "Score: $($_.score)"
    Write-Host "Doc: $($_.doc_id)"
    Write-Host "Preview: $($_.text_preview)"
    Write-Host "---"
}
```

### Example 2: Get AI-Generated Answer

```powershell
$apiUrl = "https://rag-agent-api-cukcysp7ta-uc.a.run.app/ask"

$body = @{
    question = "Explain how text chunking works"
    top_k = 8
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri $apiUrl -Method POST -Body $body -ContentType "application/json"

# Display answer
Write-Host "Answer:"
Write-Host $response.answer
Write-Host "`nCitations:"
$response.citations | ForEach-Object {
    Write-Host "- [$($_.score)] $($_.doc_id): $($_.text_preview.Substring(0, [Math]::Min(100, $_.text_preview.Length)))..."
}
```

### Example 3: Simple One-Liner Search

```powershell
Invoke-RestMethod -Uri "https://rag-agent-api-cukcysp7ta-uc.a.run.app/search" `
  -Method POST `
  -Body (@{question="What is vector search?"} | ConvertTo-Json) `
  -ContentType "application/json"
```

---

## cURL Examples (Alternative)

### Search Endpoint

```bash
curl -X POST https://rag-agent-api-cukcysp7ta-uc.a.run.app/search \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is hybrid RAG?",
    "top_k": 5
  }'
```

### Ask Endpoint

```bash
curl -X POST https://rag-agent-api-cukcysp7ta-uc.a.run.app/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain how text chunking works",
    "top_k": 8
  }'
```

---

## Python Examples

### Search Endpoint

```python
import requests

api_url = "https://rag-agent-api-cukcysp7ta-uc.a.run.app/search"

response = requests.post(
    api_url,
    json={
        "question": "What is hybrid RAG?",
        "top_k": 5
    }
)

results = response.json()
for result in results["results"]:
    print(f"Score: {result['score']}")
    print(f"Doc: {result['doc_id']}")
    print(f"Preview: {result['text_preview']}")
    print("---")
```

### Ask Endpoint

```python
import requests

api_url = "https://rag-agent-api-cukcysp7ta-uc.a.run.app/ask"

response = requests.post(
    api_url,
    json={
        "question": "Explain how text chunking works",
        "top_k": 8
    }
)

data = response.json()
print("Answer:", data["answer"])
print("\nCitations:")
for citation in data["citations"]:
    print(f"- [{citation['score']}] {citation['doc_id']}: {citation['text_preview'][:100]}...")
```

---

## Testing After Upload

After uploading `TUTORIAL.md`, try these queries:

```powershell
# Query about the tutorial content
$body = @{
    question = "What is this tutorial about?"
    top_k = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://rag-agent-api-cukcysp7ta-uc.a.run.app/search" `
  -Method POST -Body $body -ContentType "application/json"
```

```powershell
# Get an AI answer about chunking
$body = @{
    question = "How does text chunking work?"
    top_k = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://rag-agent-api-cukcysp7ta-uc.a.run.app/ask" `
  -Method POST -Body $body -ContentType "application/json"
```

---

## Understanding the Response

### Search Response Fields:
- **chunk_id**: Unique identifier for the chunk (format: `{doc_id}_chunk_{index}`)
- **doc_id**: Document identifier (derived from GCS URI)
- **source**: GCS URI of the source document
- **score**: Similarity score (higher = more relevant)
- **text_preview**: First 240 characters of the chunk text

### Ask Response Fields:
- **answer**: AI-generated answer based on retrieved chunks
- **citations**: List of source chunks used to generate the answer (same format as search results)

---

## Troubleshooting

### No Results Returned?
1. **Check ingestion logs**: Verify the document was processed successfully
   ```powershell
   gcloud run services logs read rag-ingest-doc --region=us-central1 --limit=50
   ```

2. **Verify Vector Search**: Check if chunks were upserted
   ```powershell
   # Check function logs for "Successfully upserted to Vector Search"
   ```

3. **Wait a few seconds**: Vector Search indexing may take a moment

### API Returns Error?
- Check if the API is running: `https://rag-agent-api-cukcysp7ta-uc.a.run.app/health`
- Verify the question is at least 3 characters long
- Check API logs in Cloud Run console

---

## Quick Test Script

Save this as `test-api.ps1`:

```powershell
param(
    [string]$Question = "What is hybrid RAG?",
    [int]$TopK = 5,
    [switch]$Ask = $false
)

$endpoint = if ($Ask) { "ask" } else { "search" }
$apiUrl = "https://rag-agent-api-cukcysp7ta-uc.a.run.app/$endpoint"

$body = @{
    question = $Question
    top_k = $TopK
} | ConvertTo-Json

Write-Host "Querying: $Question" -ForegroundColor Cyan
Write-Host "Endpoint: $endpoint" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri $apiUrl -Method POST -Body $body -ContentType "application/json"
    
    if ($Ask) {
        Write-Host "Answer:" -ForegroundColor Green
        Write-Host $response.answer
        Write-Host "`nCitations:" -ForegroundColor Yellow
        $response.citations | ForEach-Object {
            Write-Host "- [$($_.score)] $($_.doc_id): $($_.text_preview.Substring(0, [Math]::Min(100, $_.text_preview.Length)))..."
        }
    } else {
        Write-Host "Found $($response.results.Count) results:" -ForegroundColor Green
        $response.results | ForEach-Object {
            Write-Host "`nScore: $($_.score)" -ForegroundColor Yellow
            Write-Host "Doc: $($_.doc_id)"
            Write-Host "Chunk: $($_.chunk_id)"
            Write-Host "Preview: $($_.text_preview.Substring(0, [Math]::Min(150, $_.text_preview.Length)))..."
        }
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
```

**Usage**:
```powershell
# Search
.\test-api.ps1 -Question "What is chunking?"

# Ask
.\test-api.ps1 -Question "Explain embeddings" -Ask

# Custom top_k
.\test-api.ps1 -Question "What is RAG?" -TopK 10
```
