import os
from dotenv import load_dotenv
from io import BytesIO
import boto3
import PyPDF2 as pdf

load_dotenv()

api_endpoint = os.getenv("AWS_API_ENDPOINT")
api_key = os.getenv("AWS_API_KEY")
large_file_limit = 1000000000 # 1GB
very_large_file_limit = 10000000000 # 10GB
extra_large_file_limit = 25000000000 # 25GB

s3_client = boto3.client('s3')

def process_massive_file(bucket_name: str, object_key: str):
    # 1. Obter apenas os metadados (Não faz download do corpo)
    head_response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
    file_size = head_response['ContentLength']

    # 2. Ao invés de carregar na RAM, fazemos o streaming em blocos para o disco do Lambda (/tmp)
    # O Lambda possui até 10GB de armazenamento efêmero no /tmp
    local_path = f"/tmp/{object_key.split('/')[-1]}"

    # O método download_file gerencia multipart downloads eficientemente sem sobrecarregar a RAM
    s3_client.download_file(bucket_name, object_key, local_path)

    # 3. O processamento agora ocorre mapeando o disco (Menos pressão na RAM)
    
    pdf_reader = pdf.PdfReader(local_path)

    total_pages = len(pdf_reader.pages)

    if file_size >= extra_large_file_limit:
        chunk_size = 25
    elif file_size >= very_large_file_limit:
        chunk_size = 10
    elif file_size >= large_file_limit:
        chunk_size = 5        
    else:
        chunk_size = 1

    for i in range(0, total_pages, chunk_size):
        pdf_writer = pdf.PdfWriter()
        for j in range(i, min(i + chunk_size, total_pages)):
            pdf_writer.add_page(pdf_reader.pages[j])
        
        # Salva o chunk intermediário no disco antes de subir pro S3
        chunk_path = f"/tmp/chunk_{i}.pdf"
        with open(chunk_path, "wb") as f_out:
            pdf_writer.write(f_out)
            
        # Upload para o S3 e limpeza do disco
        s3_client.upload_file(chunk_path, bucket_name, f"processed/chunk_{i}.pdf")
        os.remove(chunk_path)
    
    os.remove(local_path)

    

process_massive_file("pre-signed-url-generator-bucket-2766834a", "inbox/1bc62724_Carlos-de-Lima-Junior-FlowCV-Resume-en-US.pdf")