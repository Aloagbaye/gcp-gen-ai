variable "project_id" { 
  type = string 
}

variable "region" { 
  type    = string
  default = "us-central1"
}

variable "bucket_name" {
  type        = string
  description = "GCS bucket for document uploads + function source zips"
}

variable "pubsub_topic_name" {
  type    = string
  default = "rag-ingest"
}

variable "artifact_repo_name" {
  type    = string
  default = "rag-artifacts"
}

variable "function_name" {
  type    = string
  default = "rag-ingest-doc"
}

variable "cloud_run_service_name" {
  type    = string
  default = "rag-agent-api"
}

variable "cloud_run_image_uri" {
  type        = string
  default     = ""
  description = "Cloud Run container image URI (build/push separately). Leave empty to skip Cloud Run creation initially."
}

# Neo4j (Aura or self-hosted)
variable "neo4j_uri" { type = string }
variable "neo4j_user" { type = string }
variable "neo4j_password" {
  type      = string
  sensitive = true
}

# Vertex Vector Search settings
variable "create_vector_search" {
  type    = bool
  default = true
}

variable "vector_index_display_name" {
  type    = string
  default = "rag-chunks-index"
}

variable "vector_dimensions" {
  type    = number
  default = 768
}

# Runtime configs
variable "embedding_model" {
  type    = string
  default = "text-embedding-004"
}

variable "generative_model" {
  type    = string
  default = "gemini-2.5-flash"
  description = "Gemini model name. Options: gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-flash-002"
}

variable "top_k" {
  type    = number
  default = 8
}
