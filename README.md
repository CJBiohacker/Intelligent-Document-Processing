# Intelligent-Document-Processing

### General Description

### Technologies and Specs

- Configurar AWS CLI e adicionar as credenciais básicas que permitem acesso aos recursos e infraestrutura da nuvem local e via terceiros autorizados (Terraform).
- Ao criar o API Gateway, criar um Plano de Uso/Gastos e vincular à chave de API da AWS.

### Project Architecture and Diagrams

- Usar IaC via Terraform para configurar os providers e variaveis necessárias da AWS para gerar a infraestrutura:

  - Lambda Function que gera uma Pre-Signed URL para envio do PDF para o Bucket S3.
  - Bucket S3 para armazenamento dos documentos em PDF
  - Criar uma segunda Lambda Function que serve como gatilho para o AWS Bedrock que irá processar os PDFs via IA. Esse processo ocorrerá toda vez que um PDF é armazenado no bucket.
- Criar a infraestrutura do Bedrock, definindo prompt, guardrails e regras para o modelo de IA Generativa quer irá processá-lo.
- O resultado devolvido pela IA é armazenado num banco NoSQL via AWS DynamoDB contendo um JSON detalhado com metadados sobre o documento.

### Endpoints

### FAQ
