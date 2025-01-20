variable "project_id" {
  description = "The ID of the project in which to create the bucket."
  type        = string
}

variable "region" {
  description = "The region where the bucket will be created."
  type        = string
  default     = "US"
}

variable "bucket_name" {
  description = "The name of the bucket to create."
  type        = string
}
