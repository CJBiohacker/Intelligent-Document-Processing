variable "aws_region" {
  description = "The AWS region to deploy resources in."
  type        = string
  default     = "us-west-1"
}

variable "project_name" {
  description = "The name of the project for which resources are being deployed."
  type        = string
  default     = "pre-signed-url-generator"
}
