# Fix for `/ask` Endpoint Returning "I don't know"

## Problem
The `/ask` endpoint returns "I don't know" because:
1. **Existing documents don't have metadata** - They were uploaded before we added `text_preview` storage in Vector Search
2. **API needs to be rebuilt** - The new code that retrieves metadata from Vector Search needs to be deployed

## Solution Steps

### Step 1: Rebuild and Redeploy the API

**No terraform apply needed** - Terraform only manages infrastructure. For code changes, rebuild the Docker image:

```powershell
cd C:\Users\aloag\personal-study\gcp-gen-ai

$PROJECT_ID = "rag-vertex-ai-with-neoj"
$REGION = "us-central1"
$REGISTRY = "$REGION-docker.pkg.dev/$PROJECT_ID/rag-artifacts"

# 1. Build the Docker image with new metadata retrieval code
Write-Host "Building API image..."
docker build -t "$REGISTRY/rag-api:latest" ./service

# 2. Push to Artifact Registry
Write-Host "Pushing to registry..."
docker push "$REGISTRY/rag-api:latest"

# 3. Deploy to Cloud Run
Write-Host "Deploying to Cloud Run..."
gcloud run deploy rag-agent-api `
  --image "$REGISTRY/rag-api:latest" `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --project $PROJECT_ID
```

### Step 2: Re-upload a Document (to get metadata)

Existing documents in the index don't have `text_preview` metadata. Re-upload a document so the ingestion function stores it:

```powershell
# Upload a document - it will trigger ingestion with metadata storage
gsutil cp TUTORIAL.md gs://rag-vertex-ai-bucket/uploads/tutorial-with-metadata.md

# Wait ~30-60 seconds for ingestion to complete
Write-Host "Waiting for ingestion (60 seconds)..."
Start-Sleep -Seconds 60
```

### Step 3: Test the `/ask` Endpoint

```powershell
$apiUrl = "https://rag-agent-api-cukcysp7ta-uc.a.run.app/ask"
$body = @{
    question = "What is hybrid RAG?"
    top_k = 5
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri $apiUrl -Method POST -Body $body -ContentType "application/json"
$response | ConvertTo-Json -Depth 10
```

You should now see:
- `text_preview` populated in citations
- A proper answer from the LLM (not "I don't know")

## Why This Happened

1. **Initial uploads**: Documents uploaded before we added metadata storage don't have `text_preview` in Vector Search
2. **Code update**: We updated the ingestion function to store metadata, but existing datapoints weren't updated
3. **API update**: We updated the API to retrieve metadata, but it wasn't rebuilt/deployed

## Verification

Check if metadata is being retrieved:

```powershell
# Test /search endpoint - should show text_preview if metadata exists
$searchBody = @{
    question = "What is hybrid RAG?"
    top_k = 3
} | ConvertTo-Json

$searchResponse = Invoke-RestMethod -Uri "https://rag-agent-api-cukcysp7ta-uc.a.run.app/search" `
  -Method POST -Body $searchBody -ContentType "application/json"

# Check if text_preview is populated
$searchResponse.results | Select-Object chunk_id, text_preview | Format-Table
```

If `text_preview` is still empty after re-uploading:
1. Check ingestion logs: `gcloud functions logs read rag-ingest-doc --region=us-central1 --limit=50`
2. Verify the ingestion function was redeployed with the new code (terraform apply already did this)
3. Check if the document was actually processed (look for "Successfully upserted" in logs)
