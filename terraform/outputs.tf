output "lambda_arn" {
  value = aws_lambda_function.processor.arn
}

output "s3_bucket_name" {
  value = aws_s3_bucket.bucket.id
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.db.name
}
