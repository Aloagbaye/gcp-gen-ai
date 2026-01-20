# =============================================================================
# Cleanup Script for Vertex AI Vector Search Index (PowerShell)
# =============================================================================
# This script removes old document chunks from the Vector Search index.
# Use this when you need to re-upload documents after schema changes or
# when old documents don't have Neo4j metadata.
#
# Usage:
#   .\cleanup-vector-index.ps1                           # Remove all known old docs
#   .\cleanup-vector-index.ps1 -DocId "uploads_test_md"  # Remove specific doc
# =============================================================================

param(
    [string]$DocId = "",
    [int]$MaxChunks = 50,
    [string]$ProjectId = "rag-vertex-ai-with-neoj",
    [string]$IndexId = "projects/rag-vertex-ai-with-neoj/locations/us-central1/indexes/<index-id>"
)

function Remove-DocChunks {
    param(
        [string]$DocId,
        [int]$MaxChunks
    )
    
    Write-Host "Removing chunks for document: $DocId (up to $MaxChunks chunks)..." -ForegroundColor Yellow
    
    # Build comma-separated list of chunk IDs
    $chunkIds = (0..($MaxChunks - 1) | ForEach-Object { "${DocId}::${DocId}_chunk_$_" }) -join ","
    
    # Remove datapoints
    try {
        gcloud ai indexes remove-datapoints $IndexId --datapoint-ids=$chunkIds --project=$ProjectId 2>&1 | Out-Null
        Write-Host "  Done with $DocId" -ForegroundColor Green
    }
    catch {
        Write-Host "  Note: Some chunks may not exist (this is OK)" -ForegroundColor Gray
    }
}

# Main execution
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Vector Search Index Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project: $ProjectId"
Write-Host "Index: $IndexId"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($DocId -ne "") {
    # Remove specific document
    Remove-DocChunks -DocId $DocId -MaxChunks $MaxChunks
}
else {
    # Remove all known old documents (uploaded before Neo4j integration)
    $oldDocs = @(
        "uploads_test_final_md",
        "uploads_TUTORIAL_md",
        "uploads_tutorial_test_md",
        "uploads_tutorial_final_test_md",
        "uploads_test_unique_txt",
        "uploads_test_final_neo4j_md"
    )
    
    Write-Host "Removing $($oldDocs.Count) old documents..." -ForegroundColor Yellow
    Write-Host ""
    
    foreach ($doc in $oldDocs) {
        Remove-DocChunks -DocId $doc -MaxChunks $MaxChunks
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cleanup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Re-upload documents to trigger ingestion with Neo4j:"
Write-Host "     gsutil cp TUTORIAL.md gs://rag-vertex-ai-bucket/uploads/tutorial-v2.md" -ForegroundColor White
Write-Host ""
Write-Host "  2. Wait ~60 seconds for ingestion to complete"
Write-Host ""
Write-Host "  3. Test the API:"
Write-Host '     $body = @{ question = "What is hybrid RAG?"; top_k = 5 } | ConvertTo-Json' -ForegroundColor White
Write-Host '     Invoke-RestMethod -Uri "https://rag-agent-api-<api-link>/ask" -Method POST -Body $body -ContentType "application/json"' -ForegroundColor White
