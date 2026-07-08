# SAF - Sistema de Auditoria de Fretes e Faturas

O SAF e uma solucao para auditoria, conciliacao e contestacao de fretes em operacoes de e-commerce e distribuicao. O sistema foi estruturado para reduzir perdas com cobrancas indevidas, acelerar a analise financeira e dar rastreabilidade ao processo de revisao de faturas de transportadoras.

A proposta e tratar o frete como um fluxo operacional e financeiro unico, conectando contrato, ERP/WMS, rastreamento, fatura da transportadora, auditoria automatizada, contestacao e historico de execucoes.

## Visao Geral

Em operacoes de alto volume, a conferncia manual de fretes costuma depender de planilhas, regras espalhadas em documentos diferentes, consultas no ERP e validacoes feitas por amostragem. Isso torna a analise lenta, sujeita a erro e dificil de auditar depois.

O SAF organiza esse fluxo em uma cadeia clara:

1. Recebe a tabela contratual, a base ERP/WMS e a fatura da transportadora.
2. Normaliza colunas vindas de fontes diferentes.
3. Persiste os dados em SQLite para demonstracao e consultas locais.
4. Recalcula o valor esperado por regra contratual.
5. Classifica cada caso como Aprovado, Atenção ou Rejeitado.
6. Exibe um resumo executivo por transportadora.
7. Explica a regra aplicada linha a linha.
8. Organiza os rejeitados em uma tela de contestacao.
9. Registra lotes de auditoria e historico de execucoes.
10. Expõe API para integracoes e consumo por outros sistemas.

## Problema Que a Solucao Resolve

Na rotina de transporte, o time financeiro recebe faturas consolidadas com dezenas ou centenas de CT-es. Entre a contratacao do frete e a cobranca efetiva, surgem divergencias como:

- peso cubado acima do esperado;
- frete peso fora da tabela;
- GRIS e Ad Valorem acima da aliquota;
- taxa de despacho fora do contrato;
- pedagio divergente;
- taxa adicional sem evidencia operacional;
- duplicidade de cobranca por NF-e ou CT-e;
- cobranca sem correspondencia na base interna.

O SAF foi desenhado para transformar essa analise em um processo replicavel, rapido e rastreavel.

## O Que o SAF Entrega

- auditoria automatizada de fretes;
- painel executivo por transportadora;
- visao detalhada da regra aplicada em cada linha;
- tela de contestacao pronta para o financeiro;
- exportacao Excel para negociacao com a transportadora;
- historico de lotes e execucoes;
- normalizacao assistida de arquivos com colunas fora do padrao;
- API para integracao com ERP, Google Drive, sistemas internos e rotinas ETL;
- gancho pronto para integracao com LLM e servicos de IA externos.

## Stack Tecnica

- Python 3.11+
- Pandas para conciliacao tabular e regras de negocio
- SQLite para persistencia local
- Streamlit para a interface operacional
- FastAPI para integracao por API
- Pydantic para contratos de entrada e saida
- OpenPyXL para exportacao Excel
- Requests para integracao com servicos externos de IA
- Pytest para testes automatizados

## Estrutura do Projeto

```text
SAF/
|-- app/
|   `-- streamlit_app.py          # Interface operacional
|-- data/
|   |-- fixtures/                 # Bases de teste e demonstracao
|   `-- saf.db                    # Banco SQLite local
|-- exports/
|   `-- contestacao_frete.xlsx    # Exportacao gerada pela aplicacao
|-- src/
|   `-- saf/
|       |-- api.py                # API FastAPI
|       |-- audit.py              # Motor de auditoria
|       |-- campos.py             # Campos canonicos em PT-BR
|       |-- cli.py                # CLI do projeto
|       |-- database.py           # Persistencia SQLite
|       |-- exporter.py           # Exportacao de contestacao
|       |-- ia.py                 # Integração com IA/LLM via endpoint externo
|       |-- normalizacao.py       # Normalizacao de colunas e tipos
|       `-- schemas.py            # Modelos Pydantic
|-- tests/
|   `-- test_audit.py
|-- pyproject.toml
|-- requirements.txt
`-- README.md
```

## Fases de Construção

### Fase 1 - Modelagem do Domínio

A estrutura foi separada em tres blocos centrais:

- tabela contratual da transportadora;
- base interna do ERP/WMS;
- fatura consolidada da transportadora.

Essa modelagem deixa claro o que foi contratado, o que foi movimentado e o que foi cobrado.

### Fase 2 - Motor de Auditoria

O modulo `src/saf/audit.py` cruza a fatura com o ERP pela `chave_nfe` e pela `transportadora`, encontra a faixa contratual correta por UF, CEP e peso faturavel e recalcula o valor esperado.

Regras aplicadas:

- divergencia de peso/cubagem acima da tolerancia;
- frete peso acima da tabela contratual;
- taxa de despacho divergente;
- GRIS e Ad Valorem divergentes;
- pedagio divergente;
- taxa adicional sem evidencia operacional;
- cobranca duplicada;
- cobranca sem correspondencia no ERP.

### Fase 3 - Persistencia em SQLite

O projeto passou a usar um banco SQLite local em `data/saf.db` como base demonstrativa. Isso permite:

- testar a solucao sem depender de planilhas soltas;
- executar consultas SQL reais;
- manter a interface alimentada por dados persistidos;
- facilitar a evolucao para bancos corporativos no futuro.

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

Esses arquivos servem para validar importacao, normalizacao, auditoria, comparacao de gabarito e carga de um banco consolidado.

### Fase 4 - Importacao Assistida

A camada de normalizacao trata arquivos com nomes de colunas diferentes do padrao esperado. O mapeamento cobre formatos como:

- `order_id` para `pedido_id`;
- `invoice_key` para `chave_nfe`;
- `carrier` para `transportadora`;
- `shipment_date` para `data_saida`;
- `charged_base_freight` para `frete_peso_cobrado`.

### Fase 4.1 - Camada de IA e LLM

O sistema possui um gancho de integracao por IA em `src/saf/ia.py`. Quando a variavel `SAF_AI_ENDPOINT` esta configurada, o SAF envia ao servico externo a lista de colunas originais e recebe de volta um mapeamento para os nomes canonicos do sistema. O adaptador foi desenhado para funcionar mesmo em ambientes enxutos, com fallback para a biblioteca padrao de HTTP quando `requests` nao estiver disponivel.

Isso permite conectar o SAF a:

- um gateway interno de IA;
- um endpoint compatível com LLM via HTTP;
- um serviço baseado em OpenAI, Azure OpenAI, Ollama, Anthropic ou outro provedor que responda via API JSON.

Hoje o uso principal da camada de IA e apoiar a normalizacao de arquivos heterogeneos. A arquitetura foi deixada pronta para evoluir para:

- classificacao semantica de justificativas;
- extracao de informacoes de anexos PDF ou XML;
- sumarizacao automatica de lotes para o financeiro;
- assistente conversacional para consulta da auditoria;
- priorizacao inteligente de casos para contestacao.

### Fase 5 - API de Integracao

O arquivo `src/saf/api.py` expõe endpoints para:

- normalizar bases recebidas;
- executar auditoria sob demanda;
- recarregar o banco SQLite a partir da massa fornecida;
- consultar tabelas e funcoes disponiveis;
- integrar ERP, portal interno, Google Drive ou pipelines internos.

### Fase 6 - Gestao de Contestacao

A interface ganhou uma aba especifica para o fluxo financeiro. Em vez de misturar todos os resultados na mesma tabela, a tela de contestacao mostra apenas casos rejeitados e organiza os campos que normalmente sustentam a cobrança:

- valor a contestar;
- motivo da contestacao;
- justificativa detalhada;
- evidencia operacional;
- explicacao da regra aplicada;
- componentes esperados do frete;
- status da contestacao: Pendente, Enviado, Aceito ou Recusado.

O motor de auditoria passou a devolver campos adicionais que sustentam essa leitura, como `valor_a_contestar`, `motivo`, `evidencia`, `peso_faturavel_kg`, `tarifa_contratual_frete_peso`, `gris_esperado`, `ad_valorem_esperado`, `pedagio_esperado` e `explicacao_regra_aplicada`.

### Fase 7 - Resumo Executivo por Transportadora

A interface passou a consolidar os dados por transportadora para leitura gerencial. A visao destaca:

- transportadora;
- total faturado;
- valor esperado pelo contrato;
- valor potencial de contestacao;
- percentual de cobrancas aprovadas;
- quantidade de rejeicoes;
- principal causa das rejeicoes.

Essa camada responde rapidamente perguntas como:

- qual transportadora concentra mais risco financeiro;
- onde estao as maiores divergencias;
- qual causa deve ser negociada primeiro.

### Fase 8 - Explicacao da Regra Aplicada

Ao selecionar uma linha da auditoria, o sistema exibe a composicao do calculo:

- peso faturavel considerado;
- tarifa contratual aplicada;
- GRIS esperado;
- Ad valorem esperado;
- pedágio esperado;
- diferenca encontrada.

Esse detalhe aumenta a confianca na analise porque mostra a logica de negocio por tras do resultado.

### Fase 9 - Historico de Auditorias e Lotes

O banco local registra execucoes de auditoria como lotes identificaveis, com:

- id do lote;
- data da auditoria;
- usuario;
- origem;
- versao da regra;
- status do processamento;
- transportadoras envolvidas;
- total de registros;
- aprovados, atencao e rejeitados;
- valor faturado, valor esperado e valor divergente.

Isso facilita auditoria interna, revisao posterior e trilha de execucao.

### Fase 10 - Contestacao Explicada por Item

A tela de contestacao permite selecionar um caso rejeitado e enxergar os campos que sustentam a cobranca em linguagem executiva:

- peso faturavel considerado;
- tarifa contratual do frete peso;
- valor a contestar;
- GRIS esperado;
- Ad valorem esperado;
- pedágio esperado;
- explicacao textual consolidada da regra aplicada.

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

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -e .
```

### 3. Gerar o banco SQLite

```bash
python -m saf.cli seed
```

Isso cria `data/saf.db` com as tabelas prontas para a demonstracao:

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

O relatorio Excel e gerado em:

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

Na tela principal o usuario encontra:

- indicadores executivos de faturado, esperado, contestacao potencial e aprovacao;
- filtros por transportadora, status e gravidade;
- resumo executivo por transportadora;
- auditoria detalhada com cores por status;
- explicacao da regra aplicada para a linha selecionada;
- tela de contestacao apenas com casos rejeitados;
- historico de lotes e execucoes;
- exportacao de planilha de contestacao.

Na aba de importacao assistida, o sistema recebe arquivos CSV ou XLSX com colunas fora do padrao e tenta mapear automaticamente para o formato esperado.

Na lateral, a base demonstrativa pode ser recarregada diretamente a partir de `data/fixtures/`.

## Integracoes e API

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

O SAF pode operar sem IA, mas a arquitetura ja esta preparada para integracao com um servico externo de normalizacao e analise semantica.

### Variaveis de Ambiente

```bash
SAF_AI_ENDPOINT=https://seu-servico-de-ia/executar
SAF_AI_TOKEN=seu-token
```

### Onde a IA Entra Hoje

- mapeamento assistido de colunas;
- apoio quando o arquivo da transportadora, ERP ou faturamento vem com nomes fora do padrao.

### Onde a IA Pode Evoluir

- leitura e classificacao de PDFs, XMLs e anexos;
- resumo de lotes por linguagem natural;
- classificacao de justificativas e ocorrencias;
- busca semantica sobre historico e contestacoes;
- copiloto interno para analista financeiro;
- extração estruturada de documentos com LLM.

## Decisoes Tecnicas

- SQLite foi mantido para demonstracao local simples e replicavel.
- Pandas continua no centro da conciliacao por ser direto para regras tabulares.
- FastAPI abre a solucao para consumo por outros sistemas.
- Streamlit foi adotado para a operacao analitica e revisao rapida.
- O exportador Excel foi mantido porque a contestacao ainda precisa conversar com o processo real da area financeira.
- A camada de IA foi separada em um adaptador HTTP simples para permitir troca de provedor sem refatorar a regra principal.

## Seguranca e Governanca

- os dados podem ser persistidos localmente para demonstracao controlada;
- os lotes de auditoria ficam rastreados por data, usuario e versao de regra;
- a interface destaca o motivo e a evidencia de cada rejeicao;
- a API pode ser integrada a um gateway interno com autenticacao antes de exposição externa;
- a camada de IA pode ser conectada a um endpoint corporativo com politicas de seguranca e auditoria.

## Testes

```bash
pytest
```

Os testes cobrem:

- identificacao de frete peso acima da tabela;
- persistencia do banco SQLite;
- comportamento de regras principais de auditoria.

## Roadmap

- autenticacao e perfis de acesso na API;
- salvamento persistente de contestacoes como entidade propria;
- leitura automatica de XML de CT-e;
- ingestao de PDFs e anexos com OCR/LLM;
- classificacao inteligente de ocorrencias com embeddings;
- busca semantica em contratos, faturas e lotes historicos;
- integracao direta com ERP e Google Drive via conectores dedicados;
- notificacoes automáticas para casos críticos;
- observabilidade de execucoes, latencia e qualidade de mapeamento de IA.

## Resultado Esperado em Operacao

Em uma rotina real, a solucao deve permitir que um analista:

- identifique rapidamente quais transportadoras concentram risco financeiro;
- abra o detalhe do caso e entenda o motivo da divergencia;
- transforme rejeicoes em contestacao sem reconstruir planilhas manualmente;
- mantenha historico por lote para auditoria interna;
- integre novas fontes de dados sem reescrever o motor de negocio;
- amplie o uso com IA sem comprometer a regra principal.
