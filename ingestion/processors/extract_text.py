import io
import os
from typing import Dict
from google.cloud import storage
from pypdf import PdfReader

# Import schema - handle both relative and absolute imports
try:
    from .schema import DocumentMetadata
except ImportError:
    from schema import DocumentMetadata

def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    """Parse GCS URI into bucket and blob name."""
    # Format: gs://bucket/path/to/file
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    
    parts = gcs_uri[5:].split("/", 1)
    bucket_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ""
    
    return bucket_name, blob_name

def detect_file_type(filename: str) -> str:
    """Detect file type from filename extension."""
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    
    if ext == "pdf":
        return "pdf"
    elif ext in ["txt", "text"]:
        return "txt"
    elif ext in ["md", "markdown"]:
        return "md"
    elif ext in ["png", "jpg", "jpeg"]:
        return "image"
    else:
        return "unknown"

def extract_pdf(gcs_uri: str) -> Dict:
    """Extract text from PDF file in GCS."""
    client = storage.Client()
    bucket_name, blob_name = parse_gcs_uri(gcs_uri)
    
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Get file metadata
    blob.reload()
    file_size = blob.size
    
    # Download to memory
    pdf_bytes = blob.download_as_bytes()
    
    # Extract text
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text_parts = []
    
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        if page_text.strip():
            text_parts.append(page_text)
    
    full_text = "\n\n".join(text_parts)
    
    # Extract metadata
    metadata = reader.metadata if reader.metadata else {}
    title = metadata.get("/Title", "") or metadata.get("Title", "")
    if not title:
        # Use filename as title
        title = blob_name.split("/")[-1].replace(".pdf", "")
    
    return {
        "text": full_text,
        "metadata": {
            "file_type": "pdf",
            "page_count": len(reader.pages),
            "title": title,
            "file_size": file_size
        }
    }

def extract_text_file(gcs_uri: str, file_type: str) -> Dict:
    """Extract text from TXT or MD file in GCS."""
    client = storage.Client()
    bucket_name, blob_name = parse_gcs_uri(gcs_uri)
    
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Get file metadata
    blob.reload()
    file_size = blob.size
    
    # Download text
    text = blob.download_as_text()
    
    # Extract title from filename
    title = blob_name.split("/")[-1].replace(f".{file_type}", "")
    
    return {
        "text": text,
        "metadata": {
            "file_type": file_type,
            "page_count": None,
            "title": title,
            "file_size": file_size
        }
    }

def extract_text(gcs_uri: str) -> Dict:
    """
    Extract text from document in GCS.
    
    Supported formats: PDF, TXT, MD
    
    Returns:
    {
        "text": "full document text",
        "metadata": {
            "file_type": "pdf",
            "page_count": 10,
            "title": "extracted title",
            "file_size": 1024000
        }
    }
    """
    # Detect file type
    file_type = detect_file_type(gcs_uri)
    
    if file_type == "pdf":
        return extract_pdf(gcs_uri)
    elif file_type == "txt":
        return extract_text_file(gcs_uri, "txt")
    elif file_type == "md":
        return extract_text_file(gcs_uri, "md")
    else:
        raise ValueError(f"Unsupported file type: {file_type}. Supported: pdf, txt, md")
