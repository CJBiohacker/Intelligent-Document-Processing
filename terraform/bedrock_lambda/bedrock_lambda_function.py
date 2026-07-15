import os
import json
import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')
dynamo_client = boto3.resource('dynamodb')

MODEL_ID = os.getenv('AWS_BEDROCK_MODEL_ID')
DYNAMO_TABLE_NAME = os.getenv('AWS_DYNAMO_TABLE')
table = dynamo_client.Table(DYNAMO_TABLE_NAME)

def lambda_handler(event, context):
    logger.info(f"Starting processing. Event received: {json.dumps(event)}")
    
    try:
        record = event['Records'][0]
        source_bucket = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        
        logger.info(f"Searching for file {object_key} in bucket {source_bucket}")
        
        s3_response = s3_client.get_object(Bucket=source_bucket, Key=object_key)
        pdf_bytes = s3_response['Body'].read()
        
        prompt_text = f"""Analyze the provided PDF document completely and extract its key information.
            You MUST output your response STRICTLY as a valid JSON object. Do not include any conversational text, explanations, or markdown formatting (do not use ```json blocks). All extracted information must be written in English (en-US).
            If you cannot identify the document's original title, use this S3 reference as the filename: {object_key}
            Follow this EXACT JSON structure:
            {{
              "filename": "Extracted document title or the provided S3 reference",
              "pages": "Total number of pages identified in the document (integer or string)",
              "main_topics": [
                "Topic 1", 
                "Topic 2"
              ], // Maximum of 10 items. Use short, concise keywords or phrases to summarize the core subjects and minimize tokens.
              "subject": "Specify the document classification (e.g., Contract, Financial Report, Resume, Legal Notice, Invoice, etc.)"
            }}"""

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "name": "Uploaded PDF Document",
                            "format": "pdf",
                            "source": {
                                "bytes": pdf_bytes
                            }
                        }
                    },
                    {
                        "text": prompt_text
                    }
                ]
            }
        ]

        logger.info(f"Invoking LLM Model {MODEL_ID} in Amazon Bedrock...")
        
        bedrock_response = bedrock_client.converse(
            modelId=MODEL_ID,
            messages=messages,
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.7
            }
        )
        
        ia_text_response = bedrock_response['output']['message']['content'][0]['text']
        input_tokens = bedrock_response['usage']['inputTokens']
        output_tokens = bedrock_response['usage']['outputTokens']

        ia_text_response = ia_text_response.strip()
        if ia_text_response.startswith('```json'):
            ia_text_response = ia_text_response[7:-3].strip()
        elif ia_text_response.startswith('```'):
            ia_text_response = ia_text_response[3:-3].strip()
        
        try:
            ia_json_data = json.loads(ia_text_response)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode AI JSON. Original output: {ia_text_response}")
            ia_json_data = {"error": "Invalid JSON output from LLM", "raw_output": ia_text_response}

        logger.info("Processing completed successfully.")

        item_db = {
            'id': object_key,
            'status': 'PROCESSED',
            'model_used': MODEL_ID,
            'document_metadata': ia_json_data,
            'tokens_input': input_tokens,
            'tokens_output': output_tokens,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }
        
        table.put_item(Item=item_db)
        logger.info("Record saved in DynamoDB.")
        
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Processing completed successfully", "document_id": object_key})
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code in ['ValidationException', 'ModelNotFoundException', 'ThrottlingException']:
            logger.error(f"Error in communication with Amazon Bedrock: {error_msg}")
            return {"statusCode": 502, "body": json.dumps({"error": "Failure in IA inference", "details": error_msg})}
            
        elif error_code in ['ProvisionedThroughputExceededException', 'ResourceNotFoundException']:
            logger.error(f"Error saving to DynamoDB: {error_msg}")
            return {"statusCode": 500, "body": json.dumps({"error": "Database failure", "details": error_msg})}
            
        elif error_code == 'NoSuchKey':
            logger.error(f"File not found in S3: {error_msg}")
            return {"statusCode": 404, "body": json.dumps({"error": "Base file not found", "details": error_msg})}
            
        else:
            logger.error(f"Generic error in Boto3: {error_msg}")
            return {"statusCode": 500, "body": json.dumps({"error": "Internal provider error", "details": error_msg})}
            
    except Exception as e:
        logger.critical(f"Generic error in Lambda execution: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Catastrophic failure in processor", "details": str(e)})
        }