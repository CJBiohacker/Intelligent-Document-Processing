variable "aws_region" {
  description = "The AWS region to deploy resources in."
  type        = string
  default     = "us-west-1"
}

variable "project_name" {
  description = "The name of the project for which resources are being deployed."
  type        = string
  default     = "pre_signed_url_generator"
}

variable "bedrock_project_name" {
  description = "The name of the lambda bedrock project for which resources are being deployed."
  type        = string
  default     = "bedrock_processor"
}

variable "bedrock_model_name" {
  description = "The name of the Bedrock model to be used by the Lambda function."
  type        = string
  default     = "us.amazon.nova-2-lite-v1:0"

}
