
locals {
  required_apis = [
    "aiplatform.googleapis.com",
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ----------------------------
# Storage + Pub/Sub
# ----------------------------
resource "google_storage_bucket" "rag_bucket" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.apis]
}

resource "google_pubsub_topic" "rag_ingest_topic" {
  name       = var.pubsub_topic_name
  depends_on = [google_project_service.apis]
}

# Grant Pub/Sub permissions to GCS service account for notifications
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

resource "google_pubsub_topic_iam_member" "gcs_notification" {
  topic  = google_pubsub_topic.rag_ingest_topic.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_storage_notification" "gcs_to_pubsub" {
  bucket         = google_storage_bucket.rag_bucket.name
  topic          = google_pubsub_topic.rag_ingest_topic.id
  payload_format = "JSON_API_V1"
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [
    google_storage_bucket.rag_bucket,
    google_pubsub_topic.rag_ingest_topic,
    google_pubsub_topic_iam_member.gcs_notification
  ]
}

# ----------------------------
# Artifact Registry
# ----------------------------
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.artifact_repo_name
  format        = "DOCKER"
  description   = "Artifacts for RAG service/function images"
  depends_on    = [google_project_service.apis]
}

# ----------------------------
# Service Accounts + IAM
# ----------------------------
resource "google_service_account" "function_sa" {
  account_id   = "rag-ingest-sa"
  display_name = "SA for RAG ingestion function"
}

resource "google_service_account" "run_sa" {
  account_id   = "rag-run-sa"
  display_name = "SA for RAG Cloud Run service"
}

# Vertex + Storage perms
resource "google_project_iam_member" "function_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_member" "function_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_member" "run_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.run_sa.email}"
}

resource "google_project_iam_member" "run_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.run_sa.email}"
}

# ----------------------------
# (Optional) Vertex Vector Search Index + Endpoint
# ----------------------------
resource "google_vertex_ai_index" "rag_index" {
  count        = var.create_vector_search ? 1 : 0
  display_name = var.vector_index_display_name
  region       = var.region
  index_update_method = "STREAM_UPDATE"  # Enable streaming updates for real-time upserts

  metadata {
    contents_delta_uri = "gs://${var.bucket_name}/vector_index_seed/" # can be empty; you can upsert later
    config {
      dimensions                  = var.vector_dimensions
      approximate_neighbors_count = 100
      distance_measure_type       = "DOT_PRODUCT_DISTANCE"
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 1000
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }

  depends_on = [google_project_service.apis, google_storage_bucket.rag_bucket]
}

resource "google_vertex_ai_index_endpoint" "rag_index_endpoint" {
  count                = var.create_vector_search ? 1 : 0
  display_name         = "rag-index-endpoint"
  region               = var.region
  public_endpoint_enabled = true

  depends_on = [google_project_service.apis]
}

# Note: deploying index to endpoint is supported but can be finicky across provider versions.
# If this resource errors in your environment, deploy via gcloud/UI once and paste endpoint ID into env vars.
resource "google_vertex_ai_index_endpoint_deployed_index" "deployed" {
  count             = var.create_vector_search ? 1 : 0
  index_endpoint    = google_vertex_ai_index_endpoint.rag_index_endpoint[0].id
  deployed_index_id = "rag_chunks"
  index             = google_vertex_ai_index.rag_index[0].id

  depends_on = [
    google_vertex_ai_index.rag_index,
    google_vertex_ai_index_endpoint.rag_index_endpoint
  ]
}

# ----------------------------
# Cloud Function Gen2 (ingestion)
# ----------------------------
# Prepare staging directory with main.py at root and processors/ as sibling
resource "null_resource" "prepare_function" {
  triggers = {
    main_py_hash      = filemd5("${path.module}/../ingestion/function/main.py")
    requirements_hash = filemd5("${path.module}/../ingestion/function/requirements.txt")
    processors_hash   = sha256(join("", [
      for f in fileset("${path.module}/../ingestion/processors", "*.py") : filemd5("${path.module}/../ingestion/processors/${f}")
    ]))
  }

  provisioner "local-exec" {
    command     = <<-EOT
      $staging = "${path.module}/.build/function_staging"
      $functionDir = "${path.module}/../ingestion/function"
      $processorsDir = "${path.module}/../ingestion/processors"
      
      New-Item -ItemType Directory -Force -Path $staging | Out-Null
      Copy-Item "$functionDir/main.py" "$staging/main.py" -Force
      Copy-Item "$functionDir/requirements.txt" "$staging/requirements.txt" -Force
      Copy-Item "$processorsDir" "$staging/processors" -Recurse -Force
    EOT
    interpreter = ["PowerShell", "-Command"]
  }
}

data "archive_file" "function_zip" {
  depends_on = [null_resource.prepare_function]
  type       = "zip"
  source_dir = "${path.module}/.build/function_staging"
  output_path = "${path.module}/.build/ingest.zip"
  excludes   = ["__pycache__", "*.pyc", ".DS_Store"]
}

resource "google_storage_bucket_object" "function_source_zip" {
  name   = "functions/ingest_${data.archive_file.function_zip.output_md5}.zip"
  bucket = google_storage_bucket.rag_bucket.name
  source = data.archive_file.function_zip.output_path
}

resource "google_cloudfunctions2_function" "ingest_func" {
  name     = var.function_name
  location = var.region

  build_config {
    runtime     = "python310"
    entry_point = "ingest_document"

    source {
      storage_source {
        bucket = google_storage_bucket.rag_bucket.name
        object = google_storage_bucket_object.function_source_zip.name
      }
    }
  }

  service_config {
    available_memory      = "1024M"  # Max for default CPU (0.583 vCPU)
    timeout_seconds       = 300      # Increased timeout to 5 minutes
    service_account_email = google_service_account.function_sa.email

    environment_variables = {
      PROJECT_ID       = var.project_id
      REGION           = var.region
      BUCKET_NAME      = google_storage_bucket.rag_bucket.name

      # Vector Search resources (prefer endpoint + deployed index id)
      VECTOR_INDEX_ENDPOINT = var.create_vector_search ? google_vertex_ai_index_endpoint.rag_index_endpoint[0].id : ""
      DEPLOYED_INDEX_ID     = var.create_vector_search ? google_vertex_ai_index_endpoint_deployed_index.deployed[0].deployed_index_id : ""

      EMBEDDING_MODEL  = var.embedding_model

      # Neo4j
      NEO4J_URI        = var.neo4j_uri
      NEO4J_USER       = var.neo4j_user
      NEO4J_PASSWORD   = var.neo4j_password
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.rag_ingest_topic.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  depends_on = [
    google_project_service.apis,
    google_storage_notification.gcs_to_pubsub,
    google_project_iam_member.function_vertex_user,
    google_project_iam_member.function_storage_viewer
  ]
}

# ----------------------------
# Cloud Run (Agent API)
# ----------------------------
resource "google_cloud_run_v2_service" "rag_api" {
  count             = var.cloud_run_image_uri != "" ? 1 : 0
  name              = var.cloud_run_service_name
  location          = var.region
  deletion_protection = false  # Allow Terraform to destroy/replace the service

  template {
    service_account = google_service_account.run_sa.email

    containers {
      image = var.cloud_run_image_uri

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }

      env {
        name  = "VECTOR_INDEX_ENDPOINT"
        value = var.create_vector_search ? google_vertex_ai_index_endpoint.rag_index_endpoint[0].id : ""
      }
      env {
        name  = "DEPLOYED_INDEX_ID"
        value = var.create_vector_search ? google_vertex_ai_index_endpoint_deployed_index.deployed[0].deployed_index_id : ""
      }

      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }
      env {
        name  = "GENERATIVE_MODEL"
        value = var.generative_model
      }
      env {
        name  = "TOP_K"
        value = tostring(var.top_k)
      }

      env {
        name  = "NEO4J_URI"
        value = var.neo4j_uri
      }
      env {
        name  = "NEO4J_USER"
        value = var.neo4j_user
      }
      env {
        name  = "NEO4J_PASSWORD"
        value = var.neo4j_password
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.run_vertex_user,
    google_project_iam_member.run_storage_viewer
  ]
}

# Make service callable (for demo). For production, restrict.
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  count    = var.cloud_run_image_uri != "" ? 1 : 0
  name     = google_cloud_run_v2_service.rag_api[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
