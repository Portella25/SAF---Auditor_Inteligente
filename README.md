# SAF - Sistema de Auditoria de Fretes e Faturas

O SAF é uma solução para auditoria, conciliação e contestação de fretes em operações de e-commerce e distribuição. O sistema foi estruturado para reduzir perdas com cobranças indevidas, acelerar a análise financeira e dar rastreabilidade ao processo de revisão de faturas de transportadoras.

A proposta é tratar o frete como um fluxo operacional e financeiro único, conectando contrato, ERP/WMS, rastreamento, fatura da transportadora, auditoria automatizada, contestação e histórico de execuções.

## Visão Geral

Em operações de alto volume, a conferência manual de fretes costuma depender de planilhas, regras espalhadas em documentos diferentes, consultas no ERP e validações feitas por amostragem. Isso torna a análise lenta, sujeita a erro e difícil de auditar depois.

O SAF organiza esse fluxo em uma cadeia clara:

1. Recebe a tabela contratual, a base ERP/WMS e a fatura da transportadora.
2. Normaliza colunas vindas de fontes diferentes.
3. Persiste os dados em SQLite para demonstração e consultas locais.
4. Recalcula o valor esperado por regra contratual.
5. Classifica cada caso como Aprovado, Atenção ou Rejeitado.
6. Exibe um resumo executivo por transportadora.
7. Explica a regra aplicada linha a linha.
8. Organiza os rejeitados em uma tela de contestação.
9. Registra lotes de auditoria e histórico de execuções.
10. Expõe API para integrações e consumo por outros sistemas.

## Problema Que a Solução Resolve

Na rotina de transporte, o time financeiro recebe faturas consolidadas com dezenas ou centenas de CT-es. Entre a contratação do frete e a cobrança efetiva, surgem divergências como:

- peso cubado acima do esperado;
- frete peso fora da tabela;
- GRIS e Ad Valorem acima da alíquota;
- taxa de despacho fora do contrato;
- pedágio divergente;
- taxa adicional sem evidência operacional;
- duplicidade de cobrança por NF-e ou CT-e;
- cobrança sem correspondência na base interna.

O SAF foi desenhado para transformar essa análise em um processo replicável, rápido e rastreável.

## O Que o SAF Entrega

- auditoria automatizada de fretes;
- painel executivo por transportadora;
- visão detalhada da regra aplicada em cada linha;
- tela de contestação pronta para o financeiro;
- exportação Excel para negociação com a transportadora;
- histórico de lotes e execuções;
- normalização assistida de arquivos com colunas fora do padrão;
- API para integração com ERP, Google Drive, sistemas internos e rotinas ETL;
- gancho pronto para integração com LLM e serviços de IA externos.

## Stack Técnica

- Python 3.11+
- Pandas para conciliação tabular e regras de negócio
- SQLite para persistência local
- Streamlit para a interface operacional
- FastAPI para integração por API
- Pydantic para contratos de entrada e saída
- OpenPyXL para exportação Excel
- Requests para integração com serviços externos de IA
- Pytest para testes automatizados

## Estrutura do Projeto

```text
SAF/
|-- app/
|   `-- streamlit_app.py          # Interface operacional
|-- data/
|   |-- fixtures/                 # Bases de teste e demonstração
|   `-- saf.db                    # Banco SQLite local
|-- exports/
|   `-- contestacao_frete.xlsx    # Exportação gerada pela aplicação
|-- src/
|   `-- saf/
|       |-- api.py                # API FastAPI
|       |-- audit.py              # Motor de auditoria
|       |-- campos.py             # Campos canônicos em PT-BR
|       |-- cli.py                # CLI do projeto
|       |-- database.py           # Persistência SQLite
|       |-- exporter.py           # Exportação de contestação
|       |-- ia.py                 # Integração com IA/LLM via endpoint externo
|       |-- normalizacao.py       # Normalização de colunas e tipos
|       `-- schemas.py            # Modelos Pydantic
|-- tests/
|   `-- test_audit.py
|-- pyproject.toml
|-- requirements.txt
`-- README.md
```

## Fases de Construção

### Fase 1 - Modelagem do Domínio

A estrutura foi separada em três blocos centrais:

- tabela contratual da transportadora;
- base interna do ERP/WMS;
- fatura consolidada da transportadora.

Essa modelagem deixa claro o que foi contratado, o que foi movimentado e o que foi cobrado.

### Fase 2 - Motor de Auditoria

O módulo `src/saf/audit.py` cruza a fatura com o ERP pela `chave_nfe` e pela `transportadora`, encontra a faixa contratual correta por UF, CEP e peso faturável e recalcula o valor esperado.

Regras aplicadas:

- divergência de peso/cubagem acima da tolerância;
- frete peso acima da tabela contratual;
- taxa de despacho divergente;
- GRIS e Ad Valorem divergentes;
- pedágio divergente;
- taxa adicional sem evidência operacional;
- cobrança duplicada;
- cobrança sem correspondência no ERP.

### Fase 3 - Persistência em SQLite

O projeto passou a usar um banco SQLite local em `data/saf.db` como base demonstrativa. Isso permite:

- testar a solução sem depender de planilhas soltas;
- executar consultas SQL reais;
- manter a interface alimentada por dados persistidos;
- facilitar a evolução para bancos corporativos no futuro.

### Fase 3.1 - Massa de Teste Fornecida

Os arquivos recebidos foram incorporados em `data/fixtures/`:

- `01_contrato_transportadora.csv`
- `02_erp_wms.csv`
- `03_fatura_transportadora.csv`
- `04_rastreamento.csv`
- `05_erp_wms_BRUTO.csv`
- `06_fatura_transportadora_BRUTA.csv`
- `07_SAF_massa_consolidada.xlsx`
- `99_gabarito_cenarios_fatura.csv`
- `saf_massa_teste.db`

Esses arquivos servem para validar importação, normalização, auditoria, comparação de gabarito e carga de um banco consolidado.

### Fase 4 - Importação Assistida

A camada de normalização trata arquivos com nomes de colunas diferentes do padrão esperado. O mapeamento cobre formatos como:

- `order_id` para `pedido_id`;
- `invoice_key` para `chave_nfe`;
- `carrier` para `transportadora`;
- `shipment_date` para `data_saida`;
- `charged_base_freight` para `frete_peso_cobrado`.

### Fase 4.1 - Camada de IA e LLM

O sistema possui um gancho de integração por IA em `src/saf/ia.py`. Quando a variável `SAF_AI_ENDPOINT` está configurada, o SAF envia ao serviço externo a lista de colunas originais e recebe de volta um mapeamento para os nomes canônicos do sistema. O adaptador foi desenhado para funcionar mesmo em ambientes enxutos, com fallback para a biblioteca padrão de HTTP quando `requests` não estiver disponível.

Isso permite conectar o SAF a:

- um gateway interno de IA;
- um endpoint compatível com LLM via HTTP;
- um serviço baseado em OpenAI, Azure OpenAI, Ollama, Anthropic ou outro provedor que responda via API JSON.

Hoje o uso principal da camada de IA é apoiar a normalização de arquivos heterogêneos. A arquitetura foi deixada pronta para evoluir para:

- classificação semântica de justificativas;
- extração de informações de anexos PDF ou XML;
- sumarização automática de lotes para o financeiro;
- assistente conversacional para consulta da auditoria;
- priorização inteligente de casos para contestação.

### Fase 5 - API de Integração

O arquivo `src/saf/api.py` expõe endpoints para:

- normalizar bases recebidas;
- executar auditoria sob demanda;
- recarregar o banco SQLite a partir da massa fornecida;
- consultar tabelas e funções disponíveis;
- integrar ERP, portal interno, Google Drive ou pipelines internos.

### Fase 6 - Gestão de Contestação

A interface ganhou uma aba específica para o fluxo financeiro. Em vez de misturar todos os resultados na mesma tabela, a tela de contestação mostra apenas casos rejeitados e organiza os campos que normalmente sustentam a cobrança:

- valor a contestar;
- motivo da contestação;
- justificativa detalhada;
- evidência operacional;
- explicação da regra aplicada;
- componentes esperados do frete;
- status da contestação: Pendente, Enviado, Aceito ou Recusado.

O motor de auditoria passou a devolver campos adicionais que sustentam essa leitura, como `valor_a_contestar`, `motivo`, `evidencia`, `peso_faturavel_kg`, `tarifa_contratual_frete_peso`, `gris_esperado`, `ad_valorem_esperado`, `pedagio_esperado` e `explicacao_regra_aplicada`.

### Fase 7 - Resumo Executivo por Transportadora

A interface passou a consolidar os dados por transportadora para leitura gerencial. A visão destaca:

- transportadora;
- total faturado;
- valor esperado pelo contrato;
- valor potencial de contestação;
- percentual de cobranças aprovadas;
- quantidade de rejeições;
- principal causa das rejeições.

Essa camada responde rapidamente perguntas como:

- qual transportadora concentra mais risco financeiro;
- onde estão as maiores divergências;
- qual causa deve ser negociada primeiro.

### Fase 8 - Explicação da Regra Aplicada

Ao selecionar uma linha da auditoria, o sistema exibe a composição do cálculo:

- peso faturável considerado;
- tarifa contratual aplicada;
- GRIS esperado;
- Ad valorem esperado;
- pedágio esperado;
- diferença encontrada.

Esse detalhe aumenta a confiança na análise porque mostra a lógica de negócio por trás do resultado.

### Fase 9 - Histórico de Auditorias e Lotes

O banco local registra execuções de auditoria como lotes identificáveis, com:

- id do lote;
- data da auditoria;
- usuário;
- origem;
- versão da regra;
- status do processamento;
- transportadoras envolvidas;
- total de registros;
- aprovados, atenção e rejeitados;
- valor faturado, valor esperado e valor divergente.

Isso facilita auditoria interna, revisão posterior e trilha de execução.

### Fase 10 - Contestação Explicada por Item

A tela de contestação permite selecionar um caso rejeitado e enxergar os campos que sustentam a cobrança em linguagem executiva:

- peso faturável considerado;
- tarifa contratual do frete peso;
- valor a contestar;
- GRIS esperado;
- Ad valorem esperado;
- pedágio esperado;
- explicação textual consolidada da regra aplicada.

## Campos Esperados

### Tabela Contratual

- `transportadora`
- `uf`
- `cep_inicial`
- `cep_final`
- `peso_minimo_kg`
- `peso_maximo_kg`
- `frete_peso_base`
- `taxa_despacho`
- `gris_pct`
- `ad_valorem_pct`
- `pedagio_por_100kg`

### Base ERP/WMS

- `pedido_id`
- `chave_nfe`
- `numero_nfe`
- `data_saida`
- `transportadora`
- `cidade_destino`
- `uf_destino`
- `cep_destino`
- `peso_real_kg`
- `peso_cubado_kg`
- `valor_nfe`
- `frete_cotado`
- `ocorrencia_rastreamento`

### Fatura da Transportadora

- `id_lote_fatura`
- `id_cte`
- `chave_nfe`
- `transportadora`
- `peso_cobrado_kg`
- `frete_peso_cobrado`
- `taxa_despacho_cobrada`
- `gris_cobrado`
- `ad_valorem_cobrado`
- `pedagio_cobrado`
- `taxa_adicional_cobrada`
- `tipo_taxa_adicional`
- `justificativa_taxa_adicional`
- `valor_total_cobrado`

## Como Executar

### 1. Criar ambiente virtual

```bash
python -m venv .venv
```

No Windows:

```bash
.venv\Scripts\activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
pip install -e .
```

### 3. Gerar o banco SQLite

```bash
python -m saf.cli seed
```

Isso cria `data/saf.db` com as tabelas prontas para a demonstração:

- `contrato`
- `erp`
- `fatura`
- `auditoria_resultados`
- `auditoria_resumo`
- `auditoria_historico`
- `auditoria_lotes`

### 4. Rodar a auditoria

```bash
python -m saf.cli audit
```

O relatório Excel é gerado em:

```text
exports/contestacao_frete.xlsx
```

### 5. Abrir o dashboard

```bash
streamlit run app/streamlit_app.py
```

### 6. Subir a API

```bash
python -m saf.cli api
```

## Como Usar a Interface

Na tela principal o usuário encontra:

- indicadores executivos de faturado, esperado, contestação potencial e aprovação;
- filtros por transportadora, status e gravidade;
- resumo executivo por transportadora;
- auditoria detalhada com cores por status;
- explicação da regra aplicada para a linha selecionada;
- tela de contestação apenas com casos rejeitados;
- histórico de lotes e execuções;
- exportação de planilha de contestação.

Na aba de importação assistida, o sistema recebe arquivos CSV ou XLSX com colunas fora do padrão e tenta mapear automaticamente para o formato esperado.

Na lateral, a base demonstrativa pode ser recarregada diretamente a partir de `data/fixtures/`.

## Integrações e API

### Endpoints Principais

- `GET /saude`
- `GET /campos-esperados`
- `GET /funcoes`
- `POST /normalizar`
- `POST /integracoes/receber`
- `POST /auditorias/executar`
- `POST /banco/demonstracao`
- `GET /banco/demonstracao`
- `GET /registros/{nome_tabela}`

### Exemplo de Payload

```json
{
  "tipo_base": "erp",
  "linhas": [
    {
      "pedido_id": "PED001",
      "chave_nfe": "NFE123",
      "numero_nfe": "1001",
      "data_saida": "2026-07-01",
      "transportadora": "TransNorte",
      "cidade_destino": "Campinas",
      "uf_destino": "SP",
      "cep_destino": 13010001,
      "peso_real_kg": 12.5,
      "peso_cubado_kg": 13.0,
      "valor_nfe": 2450.0,
      "frete_cotado": 68.4,
      "ocorrencia_rastreamento": ""
    }
  ]
}
```

## Integração com IA

O SAF pode operar sem IA, mas a arquitetura já está preparada para integração com um serviço externo de normalização e análise semântica.

### Variáveis de Ambiente

```bash
SAF_AI_ENDPOINT=https://seu-servico-de-ia/executar
SAF_AI_TOKEN=seu-token
```

### Onde a IA Entra Hoje

- mapeamento assistido de colunas;
- apoio quando o arquivo da transportadora, ERP ou faturamento vem com nomes fora do padrão.

### Onde a IA Pode Evoluir

- leitura e classificação de PDFs, XMLs e anexos;
- resumo de lotes por linguagem natural;
- classificação de justificativas e ocorrências;
- busca semântica sobre histórico e contestações;
- copiloto interno para analista financeiro;
- extração estruturada de documentos com LLM.

## Decisões Técnicas

- SQLite foi mantido para demonstração local simples e replicável.
- Pandas continua no centro da conciliação por ser direto para regras tabulares.
- FastAPI abre a solução para consumo por outros sistemas.
- Streamlit foi adotado para a operação analítica e revisão rápida.
- O exportador Excel foi mantido porque a contestação ainda precisa conversar com o processo real da área financeira.
- A camada de IA foi separada em um adaptador HTTP simples para permitir troca de provedor sem refatorar a regra principal.

## Segurança e Governança

- os dados podem ser persistidos localmente para demonstração controlada;
- os lotes de auditoria ficam rastreados por data, usuário e versão de regra;
- a interface destaca o motivo e a evidência de cada rejeição;
- a API pode ser integrada a um gateway interno com autenticação antes de exposição externa;
- a camada de IA pode ser conectada a um endpoint corporativo com políticas de segurança e auditoria.

## Testes

```bash
pytest
```

Os testes cobrem:

- identificação de frete peso acima da tabela;
- persistência do banco SQLite;
- comportamento de regras principais de auditoria.

## Roadmap

- autenticação e perfis de acesso na API;
- salvamento persistente de contestações como entidade própria;
- leitura automática de XML de CT-e;
- ingestão de PDFs e anexos com OCR/LLM;
- classificação inteligente de ocorrências com embeddings;
- busca semântica em contratos, faturas e lotes históricos;
- integração direta com ERP e Google Drive via conectores dedicados;
- notificações automáticas para casos críticos;
- observabilidade de execuções, latência e qualidade de mapeamento de IA.

## Resultado Esperado em Operação

Em uma rotina real, a solução deve permitir que um analista:

- identifique rapidamente quais transportadoras concentram risco financeiro;
- abra o detalhe do caso e entenda o motivo da divergência;
- transforme rejeições em contestação sem reconstruir planilhas manualmente;
- mantenha histórico por lote para auditoria interna;
- integre novas fontes de dados sem reescrever o motor de negócio;
- amplie o uso com IA sem comprometer a regra principal.
