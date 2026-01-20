import os
import time
from typing import List
from neo4j import GraphDatabase

# Import schema - handle both relative and absolute imports
try:
    from .schema import DocumentMetadata, Chunk, Entity
except ImportError:
    from schema import DocumentMetadata, Chunk, Entity

def upsert_document_graph(
    doc_metadata: DocumentMetadata,
    chunks: List[Chunk],
    entities: List[Entity]
):
    """
    Store document, chunks, and entities in Neo4j graph database.
    
    Graph Structure:
    - (:Document {doc_id, gcs_uri, file_type, ...})
    - (:Chunk {chunk_id, chunk_index, text_preview, ...})
    - (:Entity {name, type})
    - Relationships:
      - (Document)-[:HAS_CHUNK {order}]->(Chunk)
      - (Chunk)-[:MENTIONS]->(Entity)
    
    Args:
        doc_metadata: DocumentMetadata object
        chunks: List of Chunk objects
        entities: List of Entity objects
    """
    # Get Neo4j connection details from environment
    neo4j_uri = os.environ.get("NEO4J_URI")
    neo4j_user = os.environ.get("NEO4J_USER")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")
    
    if not neo4j_uri or not neo4j_user or not neo4j_password:
        print("Warning: Neo4j credentials not configured. Skipping graph storage.")
        return
    
    # Set a timeout for the entire Neo4j operation (60 seconds max)
    # Note: signal.alarm only works on Unix, so we'll use a simpler approach
    import time
    start_time = time.time()
    max_duration = 60  # Maximum 60 seconds for Neo4j operations
    
    # Connect to Neo4j with timeout settings
    try:
        driver = GraphDatabase.driver(
            neo4j_uri, 
            auth=(neo4j_user, neo4j_password),
            max_connection_lifetime=30,  # 30 seconds max connection lifetime
            connection_timeout=5  # 5 seconds connection timeout
        )
    except Exception as e:
        print(f"Warning: Could not connect to Neo4j: {e}")
        return
    
    try:
        with driver.session() as session:
            # Check timeout before each major operation
            if time.time() - start_time > max_duration:
                print("Warning: Neo4j operation timeout, skipping remaining operations")
                return
            
            # 1. Create/update Document node
            session.run("""
                MERGE (d:Document {doc_id: $doc_id})
                SET d.gcs_uri = $gcs_uri,
                    d.file_type = $file_type,
                    d.file_size = $file_size,
                    d.title = $title,
                    d.page_count = $page_count,
                    d.created_at = $created_at
            """, 
                doc_id=doc_metadata.doc_id,
                gcs_uri=doc_metadata.gcs_uri,
                file_type=doc_metadata.file_type,
                file_size=doc_metadata.file_size,
                title=doc_metadata.title,
                page_count=doc_metadata.page_count,
                created_at=doc_metadata.created_at
            )
            print(f"Created/updated Document node: {doc_metadata.doc_id}")
            
            # Check timeout
            if time.time() - start_time > max_duration:
                print("Warning: Neo4j operation timeout, skipping chunk creation")
                return
            
            # 2. Batch create Chunk nodes and link to Document (much faster)
            if chunks:
                chunk_data = [
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "chunk_index": chunk.chunk_index,
                        "text_preview": chunk.text_preview,
                        "page": chunk.page,
                        "token_count": chunk.token_count
                    }
                    for chunk in chunks
                ]
                
                session.run("""
                    UNWIND $chunks AS chunk_data
                    MERGE (c:Chunk {chunk_id: chunk_data.chunk_id})
                    SET c.doc_id = chunk_data.doc_id,
                        c.chunk_index = chunk_data.chunk_index,
                        c.text_preview = chunk_data.text_preview,
                        c.page = chunk_data.page,
                        c.token_count = chunk_data.token_count
                    
                    WITH c, chunk_data
                    MATCH (d:Document {doc_id: chunk_data.doc_id})
                    MERGE (d)-[r:HAS_CHUNK]->(c)
                    SET r.order = chunk_data.chunk_index
                """, chunks=chunk_data)
                
                print(f"Created/updated {len(chunks)} Chunk nodes")
            
            # Check timeout
            if time.time() - start_time > max_duration:
                print("Warning: Neo4j operation timeout, skipping entity creation")
                return
            
            # 3. Batch create Entity nodes (much faster)
            if entities:
                entity_data = [{"name": e.name, "type": e.type} for e in entities]
                
                session.run("""
                    UNWIND $entities AS entity_data
                    MERGE (e:Entity {name: entity_data.name})
                    SET e.type = entity_data.type
                """, entities=entity_data)
                
                print(f"Created/updated {len(entities)} Entity nodes")
            
            # Check timeout
            if time.time() - start_time > max_duration:
                print("Warning: Neo4j operation timeout, skipping relationship creation")
                return
            
            # 4. Batch link Chunks to Entities (optimized)
            # Pre-compute which entities appear in which chunks
            if chunks and entities:
                mentions_data = []
                entity_names = {e.name.lower(): e.name for e in entities}
                
                for chunk in chunks:
                    chunk_text_lower = chunk.text.lower()
                    # Find entities mentioned in this chunk
                    for entity_lower, entity_name in entity_names.items():
                        if entity_lower in chunk_text_lower:
                            mentions_data.append({
                                "chunk_id": chunk.chunk_id,
                                "entity_name": entity_name
                            })
                
                if mentions_data:
                    # Batch create MENTIONS relationships
                    session.run("""
                        UNWIND $mentions AS mention
                        MATCH (c:Chunk {chunk_id: mention.chunk_id})
                        MATCH (e:Entity {name: mention.entity_name})
                        MERGE (c)-[:MENTIONS]->(e)
                    """, mentions=mentions_data)
                    
                    print(f"Created {len(mentions_data)} MENTIONS relationships")
            
    except Exception as e:
        # Don't fail the entire ingestion if Neo4j fails
        print(f"Warning: Error storing graph in Neo4j: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow ingestion to continue
    finally:
        try:
            driver.close()
        except:
            pass
