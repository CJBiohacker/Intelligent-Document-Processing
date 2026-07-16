# Processamento Inteligente de Documentos (IDP)

## Descrição Geral

Este projeto apresenta um sistema nativo em nuvem de Processamento Inteligente de Documentos (IDP) construído na Amazon Web Services (AWS). Ele possui um pipeline automatizado integrado ao Amazon Bedrock para processar documentos PDF enviados através de um script de cliente local. O sistema utiliza IA Generativa para extrair metadados importantes desses documentos e armazena os resultados estruturados no Amazon DynamoDB para posterior análise de dados (Data Analytics).

## Tecnologias e Especificações

- **Provedor de Nuvem:** Amazon Web Services (AWS)
- **Infraestrutura como Código (IaC):** Terraform
- **IA Generativa:** Amazon Bedrock
- **Computação:** AWS Lambda
- **Armazenamento:** Amazon S3 (Armazenamento de Objetos), Amazon DynamoDB (Banco de Dados NoSQL)
- **Gerenciamento de API:** Amazon API Gateway
- **Aplicação Cliente:** Python (`client_trigger.py`)

## Arquitetura do Projeto e Diagramas

![Arquitetura do Projeto](assets/Architecture_Diagram_hires.png)

### Visão Geral da Arquitetura

O objetivo principal deste projeto é automatizar a extração de insights e metadados de documentos PDF não estruturados utilizando inteligência artificial. Isso elimina a entrada manual de dados e prepara os dados para análises escaláveis.

A arquitetura do sistema segue um padrão serverless (sem servidor) e orientado a eventos (event-driven), projetada para alta disponibilidade, segurança e eficiência de custos.

**Fluxo de Trabalho do Sistema:**

1. **Inicialização de Upload Seguro:** Um script de cliente local (`client_trigger.py`) solicita uma autorização de upload através do API Gateway.
2. **Geração de URL Pré-Assinada (Pre-Signed URL):** Uma função AWS Lambda autentica a solicitação e gera uma Pre-Signed URL segura e com tempo limitado.
3. **Upload Direto para o S3:** O script cliente usa a URL gerada para fazer o upload do PDF diretamente para um bucket Amazon S3.
4. **Processamento de IA Orientado a Eventos:** O upload bem-sucedido no S3 aciona automaticamente uma segunda função Lambda. Esta função invoca o Amazon Bedrock, utilizando prompts pré-definidos e guardrails para processar o PDF e extrair metadados usando um modelo de IA Generativa.
5. **Persistência de Dados:** Os insights extraídos pela IA são formatados como um payload JSON detalhado e armazenados em uma tabela do Amazon DynamoDB para recuperação rápida e análises posteriores.

**Por que essa Arquitetura?**

Essa abordagem serverless foi escolhida para desacoplar o processo de upload de arquivos da carga pesada de processamento de IA. Ao aproveitar Pre-Signed URLs, o sistema transfere o peso de upload de grandes arquivos diretamente para o S3, evitando lentidão (timeouts) e gargalos nas camadas do API Gateway e do Lambda. Além disso, o design orientado a eventos garante que o modelo de IA (e os custos de computação associados) seja invocado precisamente apenas quando novos dados chegam, otimizando o uso de recursos.

### Passos de Configuração da Infraestrutura

- **AWS CLI:** Configure o AWS CLI com credenciais que permitam o acesso aos recursos necessários da nuvem, permitindo a implantação local e o acesso autorizado de terceiros (ex: Terraform).
- **Implantação de IaC:** Use o Terraform para provisionar a infraestrutura AWS, configurando provedores e variáveis necessárias. Isso inclui os buckets S3 e as funções Lambda.
- **API Gateway:** Implante o API Gateway, garantindo que um Plano de Uso (Usage Plan) seja criado e vinculado a uma AWS API Key para acesso seguro do cliente.
- **Configuração do Bedrock:** Provisione a infraestrutura do Amazon Bedrock, definindo os prompts específicos, guardrails e os parâmetros do modelo necessários para o processamento de IA Generativa.

## Endpoints

### `/request-upload`

- **Método:** `POST`
- **Descrição:** Inicia o processo de upload do documento. Ele autentica o cliente usando uma Chave de API (API Key) e retorna uma URL Pré-Assinada (Pre-Signed URL) do AWS S3, o que permite que o cliente faça o upload seguro do PDF diretamente para o bucket S3.
- **Integração com Cliente:** Este endpoint é configurado e acionado pelo script local `client_trigger.py`.
- **Cabeçalhos Necessários (Headers):**
  - `x-api-key`: Sua chave do AWS API Gateway.
  - `Content-Type`: `application/json`

## FAQ

**Como configuro minhas variáveis de ambiente locais?**

Use o arquivo `.env.example` no diretório raiz como modelo. Copie-o para criar o seu próprio arquivo `.env` local e preencha suas credenciais e configurações específicas.

**Quais versões do Python e Terraform são exigidas?**

Este projeto requer **Python 3** e a versão mais recente com Suporte de Longo Prazo (**LTS**) do **Terraform**.

**Como configuro a região da AWS e o LLM do Bedrock?**

Você deve definir sua região alvo da AWS e selecionar o modelo fundacional específico do Amazon Bedrock (LLM) dentro do arquivo `terraform/variables.tf`.

**Como a Lambda da Pre-Signed URL é acionada?**

A função Lambda inicial (`terraform/presigned_url_lambda/lambda_function.py`) é acionada pelo endpoint do API Gateway. Para estabelecer essa conexão segura, você deve criar um Plano de Uso (Usage Plan), vinculá-lo à sua AWS API Key e associá-lo ao API Gateway implantado.

**Quais são os limites de taxa (rate limits) recomendados para o API Gateway?**

Embora você tenha a liberdade de definir seus próprios rate limits, sugerimos fortemente a seguinte configuração baseada em FinOps para evitar picos inesperados de cobrança:

- **Rate (Taxa):** 10 requisições por segundo
- **Burst (Pico):** 20 requisições
- **Quota (Cota):** 5000 requisições por mês

**Este sistema consegue processar PDFs maiores que 500MB?**

Por padrão, o projeto é otimizado para PDFs menores que 500MB. Se você precisar processar arquivos maiores (ex: > 1GB), você deve:

1. Aumentar o tamanho do armazenamento `/tmp` da função Lambda do Bedrock até um máximo de 10GB (limite do AWS Lambda).
2. Modificar o código em `terraform/bedrock_lambda/bedrock_lambda_function.py` (em torno das linhas 29 e 30) para lidar com requisitos maiores de memória e prevenir erros de Falta de Memória (Out-Of-Memory - OOM).
3. Implementar processamento em lotes (Batch processing). O arquivo `helpers/pdf_processing.py` fornece uma estrutura lógica para essa adaptação: ele lê o cabeçalho (head) do arquivo para determinar o tamanho e, caso exceda o limite, aciona a lógica de Batch Processing para dividir o documento em fragmentos (chunks).

**O processamento em lotes (Batch processing) de PDFs grandes reduz custos?**

O processamento em lotes é essencial para prevenir congestionamento e timeouts tanto na função Lambda quanto no LLM do Bedrock. No entanto, **ele não reduz os custos de tokens de forma significativa**. Como o sistema fragmenta o PDF gigantesco em grupos menores de páginas e faz múltiplas requisições sequenciais para o Bedrock, o consumo total de tokens será similar. Consequentemente, ele também irá salvar múltiplos registros de metadados no DynamoDB para um único PDF grande.

**Como posso estimar o custo de tokens para o Amazon Bedrock?**

Os custos de tokens variam dependendo do modelo escolhido e da região AWS. Observe que algumas regiões possuem uma seleção limitada de modelos disponíveis. É altamente recomendável simular os custos esperados usando a [Calculadora de Preços da AWS (AWS Pricing Calculator)](https://calculator.aws/) e revisar os [Preços do Amazon Bedrock](https://aws.amazon.com/bedrock/pricing/) oficiais.

**Todas as permissões necessárias são gerenciadas automaticamente?**

O Terraform provisiona as permissões operacionais principais necessárias para que o pipeline funcione. No entanto, funcionalidades específicas de monitoramento e logs podem exigir que você crie manualmente permissões adicionais para o CloudWatch ou habilite configurações a nível de conta. A AWS tipicamente notifica sobre esses requisitos dentro do console, portanto, fique alerta a quaisquer notificações do sistema ou alertas de log.
