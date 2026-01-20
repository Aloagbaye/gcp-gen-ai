output "rag_bucket" {
  value = google_storage_bucket.rag_bucket.name
}

output "pubsub_topic" {
  value = google_pubsub_topic.rag_ingest_topic.name
}

output "cloud_function_name" {
  value = google_cloudfunctions2_function.ingest_func.name
}

output "cloud_run_url" {
  value = var.cloud_run_image_uri != "" ? google_cloud_run_v2_service.rag_api[0].uri : ""
}

output "vector_index_endpoint" {
  value = var.create_vector_search ? google_vertex_ai_index_endpoint.rag_index_endpoint[0].id : ""
}
