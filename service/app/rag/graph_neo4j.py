import os
from typing import List, Dict
from neo4j import GraphDatabase

class Neo4jGraphClient:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def expand_by_entities(self, entities: List[str], limit: int = 10) -> List[Dict]:
        """
        Given entity names, return related chunks/documents from the graph.
        Assumes you store:
          (:Entity {name})-[:MENTIONED_IN]->(:Chunk {chunk_id, doc_id, source, text_preview})
        You can adapt to your ingestion graph schema.
        """
        if not entities:
            return []

        cypher = """
        UNWIND $entities AS e
        MATCH (ent:Entity {name: e})<-[:MENTIONS]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
        RETURN c.chunk_id AS chunk_id, d.doc_id AS doc_id, d.gcs_uri AS source, c.text_preview AS text_preview
        LIMIT $limit
        """

        with self.driver.session() as session:
            rows = session.run(cypher, entities=entities, limit=limit)
            out = []
            for r in rows:
                out.append({
                    "chunk_id": r["chunk_id"],
                    "doc_id": r["doc_id"],
                    "source": r["source"],
                    "text_preview": r["text_preview"] or ""
                })
            return out
