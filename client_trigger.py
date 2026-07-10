import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()
class DocumentUploader:
    """Responsible by local validation and secure upload of artifacts to the cloud."""
    
    def __init__(self, api_endpoint: str | None, api_key: str | None):
        if not api_endpoint or not api_key:
            raise ValueError("API Endpoint and API Key are required for initialization.")
            
        self.api_endpoint = api_endpoint
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "IDP-Client/1.0"
        }

    @staticmethod
    def _calculate_file_hash(file_path: Path) -> str:
        """Generates a SHA-256 hash to ensure file integrity and idempotency."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def upload_and_trigger_pipeline(self, file_path: Path) -> Dict[str, Any]:
        """Requests authorization from the API Gateway and performs direct upload to S3."""
        file_hash = self._calculate_file_hash(file_path)
        logging.info(f"Starting upload negotiation for: {file_path.name}")

        payload = {"filename": file_path.name, "checksum": file_hash}

        try:
            response = requests.post(
                f"{self.api_endpoint}/request-upload", 
                headers=self.headers, 
                json=payload,
                timeout=25
            )
            response.raise_for_status()
            auth_data = response.json()

            upload_url = auth_data.get("upload_url")
            
            if not upload_url:
                raise ValueError("The API response did not contain the upload URL.")

            logging.info("Authorization URL received. Starting data transfer...")

            
            with open(file_path, 'rb') as file_data:
                s3_response = requests.put(
                    upload_url, 
                    data=file_data, 
                    headers={'Content-Type': 'application/pdf'},
                    timeout=90
                )
            
            s3_response.raise_for_status()
            logging.info("Upload completed successfully. The asynchronous pipeline was triggered by AWS.")
            
            return {"status": "success", "object_key": auth_data.get("object_key")}

        except requests.exceptions.RequestException as e:
            logging.error(f"Network failure or HTTP authorization error: {str(e)}")
            sys.exit(1)

def main():
    """CLI Entrypoint with rigorous argument validation."""
    parser = argparse.ArgumentParser(
        description="Local Trigger to the Agentic IDP System",
        epilog="Use case example: python3 client_trigger.py /path/to/file.pdf"
    )
    
    parser.add_argument(
        "filepath", 
        type=Path, 
        help="Path to the file that will be processed."
    )

    args = parser.parse_args()
    target_file = args.filepath

    if not target_file.exists() or not target_file.is_file():
        logging.error(f"File not found or invalid path specified: {target_file}")
        sys.exit(1)

    api_endpoint = os.getenv("AWS_API_ENDPOINT")
    api_key = os.getenv("AWS_API_KEY")

    try:
        uploader = DocumentUploader(api_endpoint=api_endpoint, api_key=api_key)
        resultado = uploader.upload_and_trigger_pipeline(target_file)
        logging.info(f"Pipeline successfully triggered. Response: {json.dumps(resultado, indent=2)}")
    except Exception as e:
        logging.critical(f"Fatal error during execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()