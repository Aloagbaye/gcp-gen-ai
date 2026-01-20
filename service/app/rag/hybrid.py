import re
from typing import List, Dict, Any
from .vertex_vector import VertexVectorClient
from .graph_neo4j import Neo4jGraphClient

# Cache for text_preview lookups (to avoid repeated Neo4j queries)
_text_preview_cache = {}

def extract_entities_simple(text: str) -> List[str]:
    """
    Lightweight heuristic entity extraction (starter).
    Replace later with Gemini entity extraction.
    """
    candidates = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", text)
    # de-dup, keep a few
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen[:6]

def fetch_text_preview_from_neo4j(chunk_id: str, doc_id: str, graph_client: Neo4jGraphClient) -> str:
    """
    Fetch text_preview from Neo4j for a given chunk.
    Uses caching to avoid repeated queries.
    """
    cache_key = f"{doc_id}::{chunk_id}"
    
    # Check cache first
    if cache_key in _text_preview_cache:
        return _text_preview_cache[cache_key]
    
    try:
        # Use the existing graph_client's driver
        if not graph_client or not hasattr(graph_client, 'driver'):
            return ""
        
        with graph_client.driver.session() as session:
            result = session.run("""
                MATCH (c:Chunk {chunk_id: $chunk_id, doc_id: $doc_id})
                RETURN c.text_preview AS text_preview
                LIMIT 1
            """, chunk_id=chunk_id, doc_id=doc_id)
            
            record = result.single()
            if record:
                text_preview = record["text_preview"] or ""
                _text_preview_cache[cache_key] = text_preview
                return text_preview
    except Exception as e:
        # Silently fail - Neo4j might not be available
        pass
    
    return ""

def merge_and_score(
    vector_hits: List[Dict[str, Any]], 
    graph_hits: List[Dict[str, Any]],
    graph_client: Neo4jGraphClient = None
) -> List[Dict[str, Any]]:
    """
    vector_hits: [{id, score, text_preview?}] where id can be "docid::chunkid"
    graph_hits:  [{chunk_id, doc_id, source, text_preview}]
    """
    out = {}

    # vector id convention: "doc_id::chunk_id"
    for h in vector_hits:
        vid = h["id"]
        if "::" in vid:
            doc_id, chunk_id = vid.split("::", 1)
        else:
            doc_id, chunk_id = "unknown", vid

        key = f"{doc_id}::{chunk_id}"
        text_preview = h.get("text_preview", "")
        
        # If text_preview is empty and we have Neo4j, try fetching from there
        if not text_preview and graph_client:
            text_preview = fetch_text_preview_from_neo4j(chunk_id, doc_id, graph_client)
        
        out[key] = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "source": "vector_search",
            "score": float(h.get("score", 0.0)),
            "text_preview": text_preview
        }

    # graph expansion adds coverage; give it a modest bonus
    for g in graph_hits:
        key = f"{g['doc_id']}::{g['chunk_id']}"
        if key not in out:
            out[key] = {
                "chunk_id": g["chunk_id"],
                "doc_id": g["doc_id"],
                "source": g["source"],
                "score": 0.35,  # baseline for graph recall
                "text_preview": g.get("text_preview", "")
            }
        else:
            out[key]["score"] += 0.15
            # Use graph text_preview if vector search doesn't have it
            if not out[key]["text_preview"] and g.get("text_preview"):
                out[key]["text_preview"] = g["text_preview"]

    ranked = sorted(out.values(), key=lambda x: x["score"], reverse=True)
    return ranked
