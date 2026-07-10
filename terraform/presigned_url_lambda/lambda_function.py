import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        filename = body.get('filename')
        checksum = body.get('checksum')
        
        if not filename:
            return {"statusCode": 400, "body": json.dumps({"error": "Filename is required"})}

        object_key = f"inbox/{checksum[:8]}_{filename}"

        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key,
                'ContentType': 'application/pdf'
            },
            ExpiresIn=300
        )
        
        logger.info(f"URL generated successfully for: {object_key}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "upload_url": presigned_url,
                "object_key": object_key,
                "expires_in": 300
            })
        }
        
    except ClientError as e:
        logger.error(f"Error in Boto3 client: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}