# Database NoSQL DynamoDB
resource "aws_dynamodb_table" "db" {
  name         = "${var.bedrock_project_name}-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Storage S3 random ID
resource "random_id" "bucket_id" {
  byte_length = 4
}

resource "aws_s3_bucket" "bucket" {
  bucket        = "${var.project_name}-bucket-${random_id.bucket_id.hex}"
  force_destroy = true
}

# IAM Security Policies to access the cloud services (Lambda, DynamoDB, S3, CloudWatch)
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${var.project_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "${var.project_name}-lambda-permissions"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Scan", "dynamodb:Query"]
        Effect   = "Allow"
        Resource = aws_dynamodb_table.db.arn
      },
      {
        Action   = ["s3:GetObject", "s3:PutObject"]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.bucket.arn}/*"
      },
      {
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Automatic Packaging the Python Code to a ZIP file for Lambda
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/presigned_url_lambda"
  output_path = "${path.module}/presigned_url_lambda.zip"
}

# The presigned URL Lambda Function
resource "aws_lambda_function" "generator" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.project_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      AWS_S3_BUCKET_NAME = aws_s3_bucket.bucket.id
      AWS_DYNAMO_TABLE   = aws_dynamodb_table.db.name
    }
  }
}

# New IAM Role and Policy for Lambda to access Bedrock LLMs
resource "aws_iam_role" "lambda_bedrock_role" {
  name               = "${var.bedrock_project_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "lambda_bedrock_permissions" {
  name = "${var.bedrock_project_name}-lambda-permissions"
  role = aws_iam_role.lambda_bedrock_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["bedrock:InvokeModel"]
        Effect   = "Allow"
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
      },
      {
        Action   = ["s3:GetObject"]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.bucket.arn}/*"
      },
      {
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Effect   = "Allow"
        Resource = aws_dynamodb_table.db.arn
      },
      {
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

data "archive_file" "lambda_bedrock_zip" {
  type        = "zip"
  source_dir  = "${path.module}/bedrock_lambda"
  output_path = "${path.module}/bedrock_lambda.zip"
}

resource "aws_lambda_function" "bedrock_processor" {
  filename         = data.archive_file.lambda_bedrock_zip.output_path
  function_name    = var.bedrock_project_name
  role             = aws_iam_role.lambda_bedrock_role.arn
  handler          = "bedrock_lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 120
  source_code_hash = data.archive_file.lambda_bedrock_zip.output_base64sha256

  environment {
    variables = {
      AWS_S3_BUCKET_NAME   = aws_s3_bucket.bucket.id
      AWS_DYNAMO_TABLE     = aws_dynamodb_table.db.name
      AWS_BEDROCK_MODEL_ID = var.bedrock_model_name
    }
  }
}

# IAM permission to allow S3 to invoke the Lambda function
resource "aws_lambda_permission" "allow_s3_invoke_bedrock" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bedrock_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.bucket.arn
}

# S3 Bucket Notification to trigger the Lambda function when a new PDF is uploaded to the "inbox/" folder
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.bucket.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.bedrock_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "inbox/"
    filter_suffix       = ".pdf"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke_bedrock]
}
