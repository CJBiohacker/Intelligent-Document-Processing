import os
import dotenv
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any
import requests

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DocumentUploader:
    """ Reponsible for local validation and secure upload of artifacts to the cloud."""
    
    def __init__(self, api_endpoint: str, api_key: str):
        self.api_endpoint = api_endpoint
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    @staticmethod
    def _calculate_file_hash(file_path: Path) -> str:
        """Generate a hash SHA-256 to grant integrity and idempotence of the file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def upload_and_trigger_pipeline(self, file_path_str: str) -> Dict[str, Any]:
        file_path = Path(file_path_str)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path_str}")

        file_hash = self._calculate_file_hash(file_path)
        logging.info(f"Starting processing for: {file_path.name} [SHA-256: {file_hash[:8]}...]")

        payload = {
            "filename": file_path.name,
            "checksum": file_hash,
            "metadata": {"client_source": "CLI_Local_V1"}
        }

        response = requests.post(self.api_endpoint, headers=self.headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    endpoint = str(os.getenv("AWS_API_ENDPOINT"))
    key = str(os.getenv("AWS_API_KEY"))
    
    uploader = DocumentUploader(api_endpoint=endpoint, api_key=key)
    # print(uploader.upload_and_trigger_pipeline("./sample_invoice.pdf"))