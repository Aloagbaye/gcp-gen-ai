#!/bin/bash
# =============================================================================
# Cleanup Script for Vertex AI Vector Search Index
# =============================================================================
# This script removes old document chunks from the Vector Search index.
# Use this when you need to re-upload documents after schema changes or
# when old documents don't have Neo4j metadata.
#
# Usage:
#   ./cleanup-vector-index.sh [doc_id] [max_chunks]
#
# Examples:
#   ./cleanup-vector-index.sh                           # Remove all known old docs
#   ./cleanup-vector-index.sh uploads_test_final_md 50  # Remove specific doc with 50 chunks
# =============================================================================

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-rag-vertex-ai-with-neoj}"
REGION="${REGION:-us-central1}"
INDEX_ID="${INDEX_ID:-projects/rag-vertex-ai-with-neoj/locations/us-central1/indexes/<index-id>"}"

# Function to remove chunks for a document
remove_doc_chunks() {
    local doc_id=$1
    local max_chunks=${2:-50}
    
    echo "Removing chunks for document: $doc_id (up to $max_chunks chunks)..."
    
    # Build comma-separated list of chunk IDs
    local chunk_ids=""
    for i in $(seq 0 $((max_chunks - 1))); do
        if [ -n "$chunk_ids" ]; then
            chunk_ids="${chunk_ids},"
        fi
        chunk_ids="${chunk_ids}${doc_id}::${doc_id}_chunk_${i}"
    done
    
    # Remove datapoints
    gcloud ai indexes remove-datapoints "$INDEX_ID" \
        --datapoint-ids="$chunk_ids" \
        --project="$PROJECT_ID" \
        2>&1 || echo "  Note: Some chunks may not exist (this is OK)"
    
    echo "  Done with $doc_id"
}

# Main execution
echo "========================================"
echo "Vector Search Index Cleanup"
echo "========================================"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Index: $INDEX_ID"
echo "========================================"
echo ""

if [ -n "$1" ]; then
    # Remove specific document
    remove_doc_chunks "$1" "${2:-50}"
else
    # Remove all known old documents (uploaded before Neo4j integration)
    OLD_DOCS=(
        "uploads_test_final_md"
        "uploads_TUTORIAL_md"
        "uploads_tutorial_test_md"
        "uploads_tutorial_final_test_md"
        "uploads_test_unique_txt"
        "uploads_test_final_neo4j_md"
    )
    
    echo "Removing ${#OLD_DOCS[@]} old documents..."
    echo ""
    
    for doc in "${OLD_DOCS[@]}"; do
        remove_doc_chunks "$doc" 50
    done
fi

echo ""
echo "========================================"
echo "Cleanup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Re-upload documents to trigger ingestion with Neo4j:"
echo "     gsutil cp TUTORIAL.md gs://rag-vertex-ai-bucket/uploads/tutorial-v2.md"
echo ""
echo "  2. Wait ~60 seconds for ingestion to complete"
echo ""
echo "  3. Test the API:"
echo "     curl -X POST https://rag-agent-api-<api-link>/ask \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"question\": \"What is hybrid RAG?\", \"top_k\": 5}'"
