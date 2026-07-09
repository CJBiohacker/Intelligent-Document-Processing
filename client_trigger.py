import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DocumentUploader:
    """Responsável pela validação local e envio seguro de artefatos para a nuvem."""
    
    def __init__(self, api_endpoint: str, api_key: str):
        if not api_endpoint or not api_key:
            raise ValueError("API Endpoint e API Key são obrigatórios para a inicialização.")
            
        self.api_endpoint = api_endpoint
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "IDP-Client/1.0"
        }

    @staticmethod
    def _calculate_file_hash(file_path: Path) -> str:
        """Gera hash SHA-256 para garantir integridade e idempotência do arquivo."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def upload_and_trigger_pipeline(self, file_path: Path) -> Dict[str, Any]:
        """Solicita autorização ao API Gateway e realiza o upload direto para o S3."""
        file_hash = self._calculate_file_hash(file_path)
        logging.info(f"Iniciando negociação de upload para: {file_path.name}")

        payload = {"filename": file_path.name, "checksum": file_hash}

        try:
            # PASSO 1: Negociação de Acesso (API Gateway -> Lambda 1)
            response = requests.post(
                f"{self.api_endpoint}/request-upload", 
                headers=self.headers, 
                json=payload, 
                timeout=10
            )
            response.raise_for_status()
            auth_data = response.json()
            upload_url = auth_data.get("upload_url")
            
            if not upload_url:
                raise ValueError("A resposta da API não continha a URL de upload.")

            logging.info("URL de autorização recebida. Iniciando transferência de dados...")

            # PASSO 2: Transferência Direta de Binário (Cliente -> Amazon S3)
            with open(file_path, 'rb') as file_data:
                s3_response = requests.put(
                    upload_url, 
                    data=file_data, 
                    headers={'Content-Type': 'application/pdf'},
                    timeout=90
                )
            
            s3_response.raise_for_status()
            logging.info("Upload concluído com sucesso. A pipeline assíncrona foi acionada pela AWS.")
            
            return {"status": "success", "object_key": auth_data.get("object_key")}

        except requests.exceptions.RequestException as e:
            logging.error(f"Falha na rede ou na autorização HTTP: {str(e)}")
            sys.exit(1)

def main():
    """Ponto de entrada do CLI com análise rigorosa de argumentos."""
    parser = argparse.ArgumentParser(
        description="Gatilho local para o sistema de Intelligent Document Processing (Agentic IDP).",
        epilog="Exemplo de uso: python3 client_trigger.py /caminho/para/arquivo.pdf"
    )
    
    # Argumento posicional OBRIGATÓRIO
    parser.add_argument(
        "filepath", 
        type=Path, 
        help="Caminho absoluto ou relativo para o arquivo que será processado."
    )

    args = parser.parse_args()
    target_file = args.filepath

    # Validação Fail-Fast do arquivo
    if not target_file.exists() or not target_file.is_file():
        logging.error(f"Arquivo não localizado ou inválido no caminho especificado: {target_file}")
        sys.exit(1)

    api_endpoint = os.getenv("AWS_API_ENDPOINT", "")
    api_key = os.getenv("AWS_API_KEY", "")

    try:
        uploader = DocumentUploader(api_endpoint=api_endpoint, api_key=api_key)
        resultado = uploader.upload_and_trigger_pipeline(target_file)
        logging.info(f"Pipeline acionado com sucesso. Resposta: {json.dumps(resultado, indent=2)}")
    except Exception as e:
        logging.critical(f"Erro fatal durante a execução: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()