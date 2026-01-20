import os
from typing import List, Dict, Any
from google.cloud import aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel

class VertexVectorClient:
    def __init__(self, project_id: str, region: str):
        self.project_id = project_id
        self.region = region
        aiplatform.init(project=project_id, location=region)
        vertexai.init(project=project_id, location=region)

        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
        self.index_endpoint = os.getenv("VECTOR_INDEX_ENDPOINT", "")
        self.deployed_index_id = os.getenv("DEPLOYED_INDEX_ID", "")

        self.embed_model = TextEmbeddingModel.from_pretrained(self.embedding_model_name)

    def embed(self, text: str) -> List[float]:
        emb = self.embed_model.get_embeddings([text])[0].values
        return list(emb)

    def search(self, query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        """
        Returns list of {id, score, metadata?}
        Note: Depending on how you upsert datapoints, metadata may be stored externally.
        For portfolio simplicity, store doc_id/chunk_id/source in datapoint "id" pattern or restrict to ID lookup.
        """
        if not self.index_endpoint or not self.deployed_index_id:
            # Allows local dev without vector infra
            return []

        endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=self.index_endpoint)

        resp = endpoint.find_neighbors(
            deployed_index_id=self.deployed_index_id,
            queries=[query_embedding],
            num_neighbors=top_k,
            return_full_datapoint=True  # Required to get embedding_metadata
        )

        results = []
        # Handle empty response (no results or empty index)
        if resp and len(resp) > 0 and len(resp[0]) > 0:
            for neighbor in resp[0]:
                # Note: embedding_metadata is not available in google-cloud-aiplatform==1.67.0
                # text_preview will be fetched from Neo4j (when implemented in steps 6-7)
                # For now, return empty string - Neo4j client will populate it
                results.append({
                    "id": neighbor.id,
                    "score": float(neighbor.distance) if neighbor.distance is not None else float(neighbor.score),
                    "text_preview": ""  # Will be populated from Neo4j when graph storage is implemented
                })
        return results
