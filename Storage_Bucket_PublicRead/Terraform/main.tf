resource "google_storage_bucket" "public_bucket" {
  name                        = var.bucket_name
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 365
    }
  }
}

resource "google_storage_bucket_iam_binding" "public_read" {
  bucket = google_storage_bucket.public_bucket.name

  role = "roles/storage.objectViewer"

  members = [
    "allUsers",
  ]
}

output "bucket_url" {
  value = "https://storage.googleapis.com/${google_storage_bucket.public_bucket.name}/"
}