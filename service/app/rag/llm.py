import os
import requests
import vertexai
from vertexai.generative_models import GenerativeModel
from google.api_core import exceptions

class GeminiClient:
    def __init__(self, project_id: str, region: str):
        """
        If GEMINI_API_KEY is set, use the public REST endpoint with the API key.
        Otherwise, fall back to Vertex AI SDK + ADC.
        """
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GENERATIVE_MODEL", "gemini-2.5-flash-lite")
        self.project_id = project_id
        self.region = region
        self.model = None

        if self.api_key:
            # Using API key mode (no ADC required)
            print("GeminiClient using API key via REST endpoint.")
        else:
            # ADC/Vertex AI mode
            vertexai.init(project=project_id, location=region)
            try:
                self.model = GenerativeModel(self.model_name)
            except Exception as e:
                # Fallback to older model if new one fails
                print(f"Warning: Failed to initialize {self.model_name}, trying fallback: {e}")
                fallback_models = ["gemini-1.5-flash-002", "gemini-1.5-flash", "gemini-pro"]
                for fallback in fallback_models:
                    try:
                        print(f"Trying fallback model: {fallback}")
                        self.model = GenerativeModel(fallback)
                        self.model_name = fallback
                        print(f"Successfully initialized model: {fallback}")
                        break
                    except Exception as fe:
                        print(f"Fallback {fallback} also failed: {fe}")
                        continue
                
                if self.model is None:
                    raise ValueError(
                        "Could not initialize any Gemini model. "
                        "Set GEMINI_API_KEY for API key mode or enable Generative AI API in your project."
                    )

    def answer(self, question: str, context_blocks: str) -> str:
        if self.api_key:
            return self._answer_via_api_key(question, context_blocks)

        if self.model is None:
            return "Error: Gemini model not available. Please check your GCP project settings and enable the Generative AI API."
        
        prompt = f"""
You are a helpful assistant. Answer using ONLY the provided context.
If the answer is not in the context, say you don't know.
Include brief citations by chunk id in brackets like [chunk:abc123].

QUESTION:
{question}

CONTEXT:
{context_blocks}
"""
        try:
            resp = self.model.generate_content(prompt)
            return resp.text
        except exceptions.NotFound as e:
            error_msg = str(e)
            if "was not found" in error_msg or "does not have access" in error_msg:
                return f"Error: Gemini model '{self.model_name}' is not available. Please enable the Generative AI API in your GCP project or use a different model. Error: {error_msg}"
            raise
        except Exception as e:
            return f"Error generating answer: {str(e)}"

    def _answer_via_api_key(self, question: str, context_blocks: str) -> str:
        """Call Gemini via public REST endpoint using API key."""
        prompt = f"""
You are a helpful assistant. Answer using ONLY the provided context.
If the answer is not in the context, say you don't know.
Include brief citations by chunk id in brackets like [chunk:abc123].

QUESTION:
{question}

CONTEXT:
{context_blocks}
"""
        url = (
            f"https://aiplatform.googleapis.com/v1/"
            f"publishers/google/models/{self.model_name}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return "I don't know."
            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [p.get("text", "") for p in parts if "text" in p]
            return "\n".join(t for t in texts if t).strip() or "I don't know."
        except requests.HTTPError as http_err:
            return f"Error: {http_err.response.text}"
        except Exception as e:
            return f"Error generating answer: {str(e)}"
