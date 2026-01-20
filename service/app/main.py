import os
from fastapi import FastAPI
from .rag.schemas import AskRequest, AskResponse, SearchResponse, Citation
from .rag.vertex_vector import VertexVectorClient
from .rag.graph_neo4j import Neo4jGraphClient
from .rag.hybrid import extract_entities_simple, merge_and_score
from .rag.llm import GeminiClient
from .rag.citations import make_context_block

PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION", "us-central1")
TOP_K_DEFAULT = int(os.getenv("TOP_K", "8"))

app = FastAPI(title="Hybrid RAG Agent API")

vector_client = VertexVectorClient(project_id=PROJECT_ID, region=REGION)
graph_client = Neo4jGraphClient()
llm_client = GeminiClient(project_id=PROJECT_ID, region=REGION)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/search", response_model=SearchResponse)
def search(req: AskRequest):
    top_k = req.top_k or TOP_K_DEFAULT

    q_emb = vector_client.embed(req.question)
    vec_hits = vector_client.search(q_emb, top_k=top_k)

    entities = extract_entities_simple(req.question)
    graph_hits = graph_client.expand_by_entities(entities, limit=top_k)

    merged = merge_and_score(vec_hits, graph_hits, graph_client)[:top_k]

    results = [
        Citation(
            chunk_id=m["chunk_id"],
            doc_id=m["doc_id"],
            source=m["source"],
            score=m["score"],
            text_preview=(m["text_preview"][:240] if m["text_preview"] else "")
        )
        for m in merged
    ]
    return SearchResponse(results=results)

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    top_k = req.top_k or TOP_K_DEFAULT

    q_emb = vector_client.embed(req.question)
    vec_hits = vector_client.search(q_emb, top_k=top_k)

    entities = extract_entities_simple(req.question)
    graph_hits = graph_client.expand_by_entities(entities, limit=top_k)

    merged = merge_and_score(vec_hits, graph_hits, graph_client)[:top_k]

    # For demo: context from what we have (graph hits carry previews; vector hits will once ingestion stores previews)
    context_items = []
    for m in merged:
        context_items.append({
            "chunk_id": m["chunk_id"],
            "doc_id": m["doc_id"],
            "source": m["source"],
            "text_preview": m.get("text_preview", "")
        })

    context_blocks = make_context_block(context_items)
    
    # Log warning if context is empty (no text_preview available)
    if not context_blocks.strip() or all(not item.get("text_preview", "").strip() for item in context_items):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Empty context for query: {req.question}. This may be because documents don't have metadata stored. Re-upload documents to store text_preview in Vector Search metadata.")
    
    answer = llm_client.answer(req.question, context_blocks)

    citations = [
        Citation(
            chunk_id=m["chunk_id"],
            doc_id=m["doc_id"],
            source=m["source"],
            score=m["score"],
            text_preview=(m.get("text_preview", "")[:240] if m.get("text_preview") else "")
        )
        for m in merged
    ]

    return AskResponse(answer=answer, citations=citations)
