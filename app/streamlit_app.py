from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from saf.audit import AuditConfig, run_audit
from saf.campos import CAMPOS_ESPERADOS, TIPO_CONTRATO, TIPO_ERP, TIPO_FATURA
from saf.database import carregar_banco_demo, gerar_banco_demo_a_partir_de_fixtures, registrar_historico_auditoria
from saf.exporter import exportar_relatorio_contestacao
from saf.normalizacao import normalizar_dataframe


st.set_page_config(page_title="SAF - Auditoria de Fretes", page_icon="SAF", layout="wide")

DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "saf.db"
EXPORTS_DIR = ROOT / "exports"
FIXTURES_PATH = DATA_DIR / "fixtures"


def _ler_arquivo(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    if uploaded_file.name.lower().endswith(".xlsx"):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def _normalizar_acento(texto: object) -> str:
    valor = str(texto or "").strip()
    return {"Atencao": "Atenção", "Media": "Média", "Nao": "Não"}.get(valor, valor)


def _formatar_moeda(valor: object) -> str:
    if pd.isna(valor):
        return "-"
    numero = float(valor)
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_percentual(valor: object) -> str:
    if pd.isna(valor):
        return "0,00%"
    return f"{float(valor):.2f}%".replace(".", ",")


def _rotular_campo(nome: str) -> str:
    mapa = {
        "contrato": "Contrato",
        "erp": "ERP/WMS",
        "fatura": "Fatura",
        "pedido_id": "Pedido",
        "chave_nfe": "Chave NF-e",
        "numero_nfe": "Número NF-e",
        "data_saida": "Data de saída",
        "transportadora": "Transportadora",
        "cidade_destino": "Cidade de destino",
        "uf_destino": "UF de destino",
        "cep_destino": "CEP de destino",
        "peso_real_kg": "Peso real (kg)",
        "peso_cubado_kg": "Peso cubado (kg)",
        "valor_nfe": "Valor NF-e",
        "frete_cotado": "Frete cotado",
        "ocorrencia_rastreamento": "Ocorrência de rastreamento",
        "id_lote_fatura": "ID do lote da fatura",
        "id_cte": "ID do CT-e",
        "peso_cobrado_kg": "Peso cobrado (kg)",
        "frete_peso_cobrado": "Frete peso cobrado",
        "taxa_despacho_cobrada": "Taxa de despacho cobrada",
        "gris_cobrado": "GRIS cobrado",
        "ad_valorem_cobrado": "Ad valorem cobrado",
        "pedagio_cobrado": "Pedágio cobrado",
        "taxa_adicional_cobrada": "Taxa adicional cobrada",
        "tipo_taxa_adicional": "Tipo da taxa adicional",
        "justificativa_taxa_adicional": "Justificativa da taxa adicional",
        "valor_total_cobrado": "Valor total cobrado",
        "uf": "UF",
        "cep_inicial": "CEP inicial",
        "cep_final": "CEP final",
        "peso_minimo_kg": "Peso mínimo (kg)",
        "peso_maximo_kg": "Peso máximo (kg)",
        "frete_peso_base": "Frete peso base",
        "taxa_despacho": "Taxa de despacho",
        "gris_pct": "GRIS (%)",
        "ad_valorem_pct": "Ad valorem (%)",
        "pedagio_por_100kg": "Pedágio por 100 kg",
        "status": "Status",
        "gravidade": "Gravidade",
        "tipo_divergencia": "Tipo de divergência",
        "valor_esperado": "Valor esperado",
        "valor_cobrado": "Valor cobrado",
        "valor_divergente": "Valor divergente",
        "valor_a_contestar": "Valor a contestar",
        "motivo": "Motivo",
        "justificativa": "Justificativa",
        "evidencia": "Evidência",
        "status_contestacao": "Status da contestação",
        "peso_faturavel_kg": "Peso faturável considerado (kg)",
        "tarifa_contratual_frete_peso": "Tarifa contratual do frete peso",
        "frete_peso_esperado": "Frete peso esperado",
        "taxa_despacho_esperada": "Taxa de despacho esperada",
        "gris_esperado": "GRIS esperado",
        "ad_valorem_esperado": "Ad valorem esperado",
        "pedagio_esperado": "Pedágio esperado",
        "explicacao_regra_aplicada": "Explicação da regra aplicada",
        "transacoes": "Transações",
    }
    return mapa.get(nome, nome.replace("_", " ").title())


def _estilo_status(valor: object) -> str:
    status = _normalizar_acento(valor)
    if status == "Aprovado":
        return "background-color: #d7f0dc; color: #174a23; font-weight: 700;"
    if status == "Atenção":
        return "background-color: #fff2bf; color: #5c4700; font-weight: 700;"
    if status == "Rejeitado":
        return "background-color: #ffd8d8; color: #6b1111; font-weight: 700;"
    return ""


def _normalizar_status_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalizado = df.copy()
    if "status" in normalizado.columns:
        normalizado["status"] = normalizado["status"].map(_normalizar_acento)
    if "gravidade" in normalizado.columns:
        normalizado["gravidade"] = normalizado["gravidade"].map(_normalizar_acento)
    return normalizado


def _gerar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            [
                {
                    "valor_total_faturado": 0.0,
                    "valor_total_auditado": 0.0,
                    "valor_total_divergencias": 0.0,
                    "total_registros": 0,
                    "registros_divergentes": 0,
                    "eficiencia_transportadora_pct": 0.0,
                }
            ]
        )
    return pd.DataFrame(
        [
            {
                "valor_total_faturado": round(float(df["valor_cobrado"].sum()), 2),
                "valor_total_auditado": round(float(df["valor_esperado"].sum()), 2),
                "valor_total_divergencias": round(float(df.loc[df["valor_divergente"] > 0, "valor_divergente"].sum()), 2),
                "total_registros": int(len(df)),
                "registros_divergentes": int((df["status"] == "Rejeitado").sum()),
                "eficiencia_transportadora_pct": round(float((df["status"].eq("Aprovado").mean() if len(df) else 0) * 100), 2),
            }
        ]
    )


def _preparar_display(df: pd.DataFrame, ordem: list[str]) -> pd.DataFrame:
    colunas = [coluna for coluna in ordem if coluna in df.columns]
    return df.loc[:, colunas].rename(columns={coluna: _rotular_campo(coluna) for coluna in colunas})


def _formatar_colunas_moeda(df: pd.DataFrame, colunas_moeda: set[str]) -> pd.DataFrame:
    display = df.copy()
    for coluna in colunas_moeda:
        if coluna in display.columns:
            display[coluna] = display[coluna].map(_formatar_moeda)
    return display


def _estilizar_tabela(df: pd.DataFrame):
    styler = df.style
    if "Status" in df.columns:
        styler = styler.map(_estilo_status, subset=["Status"])
    return styler


def _config_colunas_auditoria() -> dict[str, object]:
    return {
        "Pedido": st.column_config.TextColumn("Pedido", width="small"),
        "Chave NF-e": st.column_config.TextColumn("Chave NF-e", width="large"),
        "ID do CT-e": st.column_config.TextColumn("ID do CT-e", width="small"),
        "Transportadora": st.column_config.TextColumn("Transportadora", width="medium"),
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Gravidade": st.column_config.TextColumn("Gravidade", width="small"),
        "Tipo de divergência": st.column_config.TextColumn("Tipo de divergência", width="medium"),
        "Valor esperado": st.column_config.TextColumn("Valor esperado", width="small"),
        "Valor cobrado": st.column_config.TextColumn("Valor cobrado", width="small"),
        "Valor divergente": st.column_config.TextColumn("Valor divergente", width="small"),
        "Justificativa": st.column_config.TextColumn("Justificativa", width="large"),
    }


def _preparar_contestacao(df: pd.DataFrame) -> pd.DataFrame:
    colunas = [
        "pedido_id",
        "id_cte",
        "transportadora",
        "valor_a_contestar",
        "motivo",
        "justificativa",
        "evidencia",
        "explicacao_regra_aplicada",
        "peso_faturavel_kg",
        "tarifa_contratual_frete_peso",
        "frete_peso_esperado",
        "taxa_despacho_esperada",
        "gris_esperado",
        "ad_valorem_esperado",
        "pedagio_esperado",
        "status_contestacao",
    ]
    contestacao = df[df["status"] == "Rejeitado"].copy()
    if "valor_a_contestar" not in contestacao.columns:
        contestacao["valor_a_contestar"] = contestacao["valor_divergente"].clip(lower=0)
    if "motivo" not in contestacao.columns:
        contestacao["motivo"] = contestacao["tipo_divergencia"]
    if "evidencia" not in contestacao.columns:
        contestacao["evidencia"] = contestacao["justificativa"]
    if "explicacao_regra_aplicada" not in contestacao.columns:
        contestacao["explicacao_regra_aplicada"] = contestacao["justificativa"]
    for coluna in [
        "peso_faturavel_kg",
        "tarifa_contratual_frete_peso",
        "frete_peso_esperado",
        "taxa_despacho_esperada",
        "gris_esperado",
        "ad_valorem_esperado",
        "pedagio_esperado",
    ]:
        if coluna not in contestacao.columns:
            contestacao[coluna] = 0.0
    contestacao["status_contestacao"] = "Pendente"
    contestacao = contestacao.loc[:, [coluna for coluna in colunas if coluna in contestacao.columns]]
    return contestacao.rename(columns={coluna: _rotular_campo(coluna) for coluna in contestacao.columns})


def _preparar_resumo_transportadora(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Transportadora",
                "Total faturado",
                "Valor esperado pelo contrato",
                "Valor potencial de contestação",
                "% de cobranças aprovadas",
                "Quantidade de rejeições",
                "Principal causa",
            ]
        )

    resumo_transportadora = (
        df.groupby("transportadora", as_index=False)
        .agg(
            total_faturado=("valor_cobrado", "sum"),
            valor_esperado_contrato=("valor_esperado", "sum"),
            valor_potencial_contestacao=("valor_a_contestar", "sum"),
            total_transacoes=("chave_nfe", "count"),
            aprovacoes=("status", lambda serie: int((serie == "Aprovado").sum())),
            quantidade_rejeicoes=("status", lambda serie: int((serie == "Rejeitado").sum())),
        )
    )
    resumo_transportadora["eficiencia_pct"] = (
        resumo_transportadora["aprovacoes"] / resumo_transportadora["total_transacoes"].replace(0, pd.NA) * 100
    ).fillna(0)
    rejeitados = df[df["status"] == "Rejeitado"].copy()
    if rejeitados.empty:
        causas = resumo_transportadora[["transportadora"]].copy()
        causas["principal_causa"] = "Sem causa crítica"
    else:
        causas = (
            rejeitados.assign(tipo_divergencia=rejeitados["tipo_divergencia"].fillna("Não classificado").astype(str))
            .groupby(["transportadora", "tipo_divergencia"], as_index=False)
            .size()
            .sort_values(["transportadora", "size"], ascending=[True, False])
            .drop_duplicates("transportadora")
            .rename(columns={"tipo_divergencia": "principal_causa"})[["transportadora", "principal_causa"]]
        )
    resumo_transportadora = resumo_transportadora.merge(causas, on="transportadora", how="left")
    resumo_transportadora["principal_causa"] = resumo_transportadora["principal_causa"].fillna("Sem causa crítica")
    resumo_transportadora = resumo_transportadora.sort_values(
        ["valor_potencial_contestacao", "quantidade_rejeicoes"],
        ascending=[False, False],
    )
    resumo_transportadora = resumo_transportadora.rename(
        columns={
            "transportadora": "Transportadora",
            "total_faturado": "Total faturado",
            "valor_esperado_contrato": "Valor esperado pelo contrato",
            "valor_potencial_contestacao": "Valor potencial de contestação",
            "eficiencia_pct": "% de cobranças aprovadas",
            "quantidade_rejeicoes": "Quantidade de rejeições",
            "principal_causa": "Principal causa",
        }
    )
    return resumo_transportadora[
        [
            "Transportadora",
            "Total faturado",
            "Valor esperado pelo contrato",
            "Valor potencial de contestação",
            "% de cobranças aprovadas",
            "Quantidade de rejeições",
            "Principal causa",
        ]
    ]


def _excel_em_memoria(planilhas: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nome, df in planilhas.items():
            df.to_excel(writer, index=False, sheet_name=nome[:31])
    return buffer.getvalue()


def _explicar_linha(registro: pd.Series) -> pd.DataFrame:
    campos = [
        ("Pedido", registro.get("pedido_id", "")),
        ("Chave NF-e", registro.get("chave_nfe", "")),
        ("ID do CT-e", registro.get("id_cte", "")),
        ("Transportadora", registro.get("transportadora", "")),
        ("Status", registro.get("status", "")),
        ("Gravidade", registro.get("gravidade", "")),
        ("Tipo de divergência", registro.get("tipo_divergencia", "")),
        ("Valor cobrado", _formatar_moeda(registro.get("valor_cobrado", 0.0))),
        ("Valor esperado", _formatar_moeda(registro.get("valor_esperado", 0.0))),
        ("Valor divergente", _formatar_moeda(registro.get("valor_divergente", 0.0))),
        ("Valor a contestar", _formatar_moeda(registro.get("valor_a_contestar", 0.0))),
    ]
    return pd.DataFrame(campos, columns=["Campo", "Valor"])


def _formatar_data_historico(valor: object) -> str:
    texto = str(valor or "")
    if not texto:
        return "-"
    try:
        return pd.to_datetime(texto).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return texto


def _preparar_historico_lotes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "ID do lote",
                "Data da auditoria",
                "Usuário",
                "Origem",
                "Versão da regra",
                "Status do processamento",
                "Transportadoras",
                "Total de registros",
                "Aprovados",
                "Atenção",
                "Rejeitados",
                "Valor faturado",
                "Valor esperado",
                "Valor divergente",
            ]
        )
    lotes = df.copy()
    colunas = [
        "id_lote",
        "data_auditoria",
        "usuario",
        "origem",
        "versao_regra",
        "status_processamento",
        "transportadoras",
        "total_registros",
        "aprovados",
        "atencao",
        "rejeitados",
        "valor_faturado",
        "valor_esperado",
        "valor_divergente",
    ]
    lotes = lotes.loc[:, [c for c in colunas if c in lotes.columns]].rename(
        columns={
            "id_lote": "ID do lote",
            "data_auditoria": "Data da auditoria",
            "usuario": "Usuário",
            "origem": "Origem",
            "versao_regra": "Versão da regra",
            "status_processamento": "Status do processamento",
            "transportadoras": "Transportadoras",
            "total_registros": "Total de registros",
            "aprovados": "Aprovados",
            "atencao": "Atenção",
            "rejeitados": "Rejeitados",
            "valor_faturado": "Valor faturado",
            "valor_esperado": "Valor esperado",
            "valor_divergente": "Valor divergente",
        }
    )
    for coluna in ["Data da auditoria"]:
        if coluna in lotes.columns:
            lotes[coluna] = lotes[coluna].map(_formatar_data_historico)
    return _formatar_colunas_moeda(lotes, {"Valor faturado", "Valor esperado", "Valor divergente"})


def _arquivos_fixtures() -> list[Path]:
    nomes = [
        "01_contrato_transportadora.csv",
        "02_erp_wms.csv",
        "03_fatura_transportadora.csv",
        "04_rastreamento.csv",
        "05_erp_wms_BRUTO.csv",
        "06_fatura_transportadora_BRUTA.csv",
        "07_SAF_massa_consolidada.xlsx",
        "99_gabarito_cenarios_fatura.csv",
    ]
    return [FIXTURES_PATH / nome for nome in nomes]


def _fixtures_mais_novos_que_banco() -> bool:
    if not DB_PATH.exists():
        return True
    banco_mtime = DB_PATH.stat().st_mtime
    arquivos = [arquivo for arquivo in _arquivos_fixtures() if arquivo.exists()]
    return bool(arquivos) and any(arquivo.stat().st_mtime > banco_mtime for arquivo in arquivos)


for chave, valor in [
    ("tolerancia_peso_percentual", 5),
    ("tolerancia_valor_baixa", 5.0),
    ("tolerancia_valor_atencao", 25.0),
]:
    st.session_state.setdefault(chave, valor)

tolerancia_peso = float(st.session_state["tolerancia_peso_percentual"]) / 100
tolerancia_baixa = float(st.session_state["tolerancia_valor_baixa"])
tolerancia_atencao = float(st.session_state["tolerancia_valor_atencao"])

if FIXTURES_PATH.exists() and _fixtures_mais_novos_que_banco():
    gerar_banco_demo_a_partir_de_fixtures(DB_PATH, FIXTURES_PATH)
elif not DB_PATH.exists():
    st.error("Base de dados não encontrada. Inclua os arquivos em data/fixtures ou forneça data/saf.db.")
    st.stop()

dados = carregar_banco_demo(DB_PATH)
contrato_df = dados[TIPO_CONTRATO]
erp_df = dados[TIPO_ERP]
fatura_df = dados[TIPO_FATURA]
historico_historico_df = dados.get("auditoria_historico", pd.DataFrame())
historico_lotes_df = dados.get("auditoria_lotes", pd.DataFrame())

auditoria_df, resumo_df = run_audit(
    erp_df,
    fatura_df,
    contrato_df,
    AuditConfig(
        tolerancia_peso_pct=tolerancia_peso,
        tolerancia_valor_baixa=tolerancia_baixa,
        tolerancia_valor_atencao=tolerancia_atencao,
    ),
)
auditoria_df = _normalizar_status_dataframe(auditoria_df)
resumo = resumo_df.iloc[0]

st.title("SAF - Sistema de Auditoria de Fretes e Faturas")
st.caption("Conferência automatizada de fretes com persistência em SQLite, importação assistida e API pronta para integração.")

with st.sidebar:
    st.header("Painel")
    st.caption("Base ativa carregada a partir de `data/fixtures`.")
    st.metric("Registros auditados", len(auditoria_df))
    st.metric("Aprovados", int((auditoria_df["status"] == "Aprovado").sum()))
    st.metric("Atenção", int((auditoria_df["status"] == "Atenção").sum()))
    st.metric("Rejeitados", int((auditoria_df["status"] == "Rejeitado").sum()))

metricas = st.columns(4)
metricas[0].metric("Valor total faturado", _formatar_moeda(resumo["valor_total_faturado"]))
metricas[1].metric("Valor esperado pelo contrato", _formatar_moeda(resumo["valor_total_auditado"]))
metricas[2].metric("Valor potencial de contestação", _formatar_moeda(resumo["valor_total_divergencias"]))
metricas[3].metric("% de cobranças aprovadas", _formatar_percentual(resumo["eficiencia_transportadora_pct"]))

filtros = st.columns(3)
transportadoras = sorted(auditoria_df["transportadora"].dropna().astype(str).unique()) if not auditoria_df.empty else []
status_opcoes = ["Aprovado", "Atenção", "Rejeitado"]
gravidade_opcoes = ["Baixa", "Média", "Alta"]
transportadoras_selecionadas = filtros[0].multiselect("Transportadora", transportadoras, default=transportadoras)
status_selecionados = filtros[1].multiselect("Status", status_opcoes, default=status_opcoes)
gravidades_selecionadas = filtros[2].multiselect("Gravidade", gravidade_opcoes, default=gravidade_opcoes)

if not auditoria_df.empty:
    auditado_filtrado = auditoria_df[
        auditoria_df["transportadora"].isin(transportadoras_selecionadas)
        & auditoria_df["status"].isin(status_selecionados)
        & auditoria_df["gravidade"].isin(gravidades_selecionadas)
    ].copy()
else:
    auditado_filtrado = auditoria_df.copy()

aba_resumo, aba_auditoria, aba_contestacao, aba_historico, aba_configuracoes, aba_importacao, aba_api = st.tabs(
    ["Resumo executivo", "Auditoria SQL", "Contestação", "Histórico", "Configurações", "Importação assistida", "API e integrações"]
)

with aba_resumo:
    resumo_transportadora = _preparar_resumo_transportadora(auditado_filtrado)
    resumo_transportadora_display = _formatar_colunas_moeda(
        resumo_transportadora,
        {"Total faturado", "Valor esperado pelo contrato", "Valor potencial de contestação"},
    )
    if "% de cobranças aprovadas" in resumo_transportadora_display.columns:
        resumo_transportadora_display["% de cobranças aprovadas"] = resumo_transportadora["% de cobranças aprovadas"].map(_formatar_percentual)

    st.subheader("Resumo por transportadora")
    st.dataframe(
        resumo_transportadora_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Transportadora": st.column_config.TextColumn("Transportadora", width="medium"),
            "Total faturado": st.column_config.TextColumn("Total faturado", width="small"),
            "Valor esperado pelo contrato": st.column_config.TextColumn("Valor esperado pelo contrato", width="small"),
            "Valor potencial de contestação": st.column_config.TextColumn("Valor potencial de contestação", width="small"),
            "% de cobranças aprovadas": st.column_config.TextColumn("% de cobranças aprovadas", width="small"),
            "Quantidade de rejeições": st.column_config.NumberColumn("Quantidade de rejeições", width="small"),
            "Principal causa": st.column_config.TextColumn("Principal causa", width="large"),
        },
    )

    if not resumo_transportadora.empty:
        grafico_transportadora = resumo_transportadora.copy()
        grafico_transportadora["Valor potencial formatado"] = grafico_transportadora["Valor potencial de contestação"].map(_formatar_moeda)
        grafico_transportadora["Eficiência formatada"] = grafico_transportadora["% de cobranças aprovadas"].map(_formatar_percentual)
        ordem_transportadoras = grafico_transportadora.sort_values("Valor potencial de contestação", ascending=False)["Transportadora"].tolist()

        col_grafico_valor, col_grafico_eficiencia = st.columns([1.2, 1])
        with col_grafico_valor:
            st.caption("Valor potencial de contestação por transportadora")
            st.vega_lite_chart(
                grafico_transportadora,
                {
                    "mark": {"type": "bar", "cornerRadiusEnd": 3},
                    "encoding": {
                        "y": {
                            "field": "Transportadora",
                            "type": "nominal",
                            "sort": ordem_transportadoras,
                            "title": "",
                            "axis": {"labelLimit": 180},
                        },
                        "x": {
                            "field": "Valor potencial de contestação",
                            "type": "quantitative",
                            "title": "Valor a contestar",
                        },
                        "color": {"value": "#EF5350"},
                        "tooltip": [
                            {"field": "Transportadora", "type": "nominal"},
                            {"field": "Valor potencial formatado", "type": "nominal", "title": "Valor potencial"},
                            {"field": "Quantidade de rejeições", "type": "quantitative", "title": "Rejeições"},
                            {"field": "Principal causa", "type": "nominal"},
                        ],
                    },
                    "height": 260,
                },
                use_container_width=True,
            )
        with col_grafico_eficiencia:
            st.caption("Percentual de cobranças aprovadas")
            st.vega_lite_chart(
                grafico_transportadora,
                {
                    "mark": {"type": "bar", "cornerRadiusEnd": 3},
                    "encoding": {
                        "y": {
                            "field": "Transportadora",
                            "type": "nominal",
                            "sort": ordem_transportadoras,
                            "title": "",
                            "axis": {"labelLimit": 180},
                        },
                        "x": {
                            "field": "% de cobranças aprovadas",
                            "type": "quantitative",
                            "title": "% aprovado",
                            "scale": {"domain": [0, 100]},
                        },
                        "color": {"value": "#4CAF50"},
                        "tooltip": [
                            {"field": "Transportadora", "type": "nominal"},
                            {"field": "Eficiência formatada", "type": "nominal", "title": "% aprovado"},
                            {"field": "Quantidade de rejeições", "type": "quantitative", "title": "Rejeições"},
                        ],
                    },
                    "height": 260,
                },
                use_container_width=True,
            )

with aba_configuracoes:
    st.subheader("Base carregada")
    base_cards = st.columns(3)
    base_cards[0].metric("Contratos", len(contrato_df))
    base_cards[1].metric("Pedidos ERP/WMS", len(erp_df))
    base_cards[2].metric("Faturas", len(fatura_df))

    st.subheader("Tolerâncias")
    st.write("As tolerâncias abaixo são aplicadas na auditoria antes da classificação final.")
    tolerancia_colunas = st.columns(3)
    tolerancia_colunas[0].slider("Peso/cubagem (%)", min_value=0, max_value=20, key="tolerancia_peso_percentual")
    tolerancia_colunas[1].number_input("Limite de valor baixo (R$)", min_value=0.0, value=tolerancia_baixa, step=1.0, key="tolerancia_valor_baixa")
    tolerancia_colunas[2].number_input("Limite de atenção (R$)", min_value=0.0, value=tolerancia_atencao, step=5.0, key="tolerancia_valor_atencao")

    if st.button("Recarregar banco de testes", use_container_width=True):
        gerar_banco_demo_a_partir_de_fixtures(DB_PATH, FIXTURES_PATH)
        st.success("Banco SQLite atualizado com a base de testes fornecida.")
        st.rerun()

    with st.expander("Campos esperados", expanded=False):
        for tipo_base, campos in CAMPOS_ESPERADOS.items():
            st.write(f"**{_rotular_campo(tipo_base)}**")
            st.write(", ".join(_rotular_campo(campo) for campo in campos))

with aba_auditoria:
    auditoria_base = auditado_filtrado.reset_index(drop=True)
    colunas_auditoria = [
        "pedido_id",
        "chave_nfe",
        "id_cte",
        "transportadora",
        "status",
        "gravidade",
        "tipo_divergencia",
        "valor_esperado",
        "valor_cobrado",
        "valor_divergente",
        "justificativa",
    ]
    auditoria_display = _preparar_display(auditoria_base, colunas_auditoria)
    auditoria_display = _formatar_colunas_moeda(auditoria_display, {"Valor esperado", "Valor cobrado", "Valor divergente"})
    evento_tabela = st.dataframe(
        _estilizar_tabela(auditoria_display),
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config=_config_colunas_auditoria(),
        on_select="rerun",
        selection_mode="single-row",
        key="auditoria_tabela",
    )

    linhas_selecionadas = []
    if hasattr(evento_tabela, "selection") and hasattr(evento_tabela.selection, "rows"):
        linhas_selecionadas = list(evento_tabela.selection.rows)
    elif isinstance(evento_tabela, dict):
        selecao = evento_tabela.get("selection", {})
        linhas_selecionadas = list(selecao.get("rows", [])) if isinstance(selecao, dict) else []

    indice_selecionado = linhas_selecionadas[0] if linhas_selecionadas else 0
    if not auditoria_base.empty:
        indice_selecionado = max(0, min(indice_selecionado, len(auditoria_base) - 1))
        registro = auditoria_base.iloc[indice_selecionado]
        st.divider()
        st.subheader("Explicação da regra aplicada")
        detalhes = st.columns(4)
        detalhes[0].metric("Peso faturável", _formatar_moeda(registro.get("peso_faturavel_kg", 0.0)))
        detalhes[1].metric("Tarifa contratual", _formatar_moeda(registro.get("tarifa_contratual_frete_peso", 0.0)))
        detalhes[2].metric("Valor esperado", _formatar_moeda(registro.get("valor_esperado", 0.0)))
        detalhes[3].metric("Valor divergente", _formatar_moeda(registro.get("valor_divergente", 0.0)))
        complemento = st.columns(3)
        complemento[0].metric("GRIS esperado", _formatar_moeda(registro.get("gris_esperado", 0.0)))
        complemento[1].metric("Ad valorem esperado", _formatar_moeda(registro.get("ad_valorem_esperado", 0.0)))
        complemento[2].metric("Pedágio esperado", _formatar_moeda(registro.get("pedagio_esperado", 0.0)))
        st.dataframe(_explicar_linha(registro), use_container_width=True, hide_index=True)
        st.info(str(registro.get("explicacao_regra_aplicada", "")))

    resumo_por_tipo = (
        auditado_filtrado.groupby(["tipo_divergencia", "status"], as_index=False)
        .agg(transacoes=("chave_nfe", "count"), valor_divergente=("valor_divergente", "sum"))
        .sort_values("valor_divergente", ascending=False)
    )
    resumo_por_tipo_display = resumo_por_tipo.rename(
        columns={
            "tipo_divergencia": "Tipo de divergência",
            "status": "Status",
            "transacoes": "Transações",
            "valor_divergente": "Valor divergente",
        }
    )
    resumo_por_tipo_display = _formatar_colunas_moeda(resumo_por_tipo_display, {"Valor divergente"})
    st.dataframe(
        _estilizar_tabela(resumo_por_tipo_display),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tipo de divergência": st.column_config.TextColumn("Tipo de divergência", width="large"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Transações": st.column_config.NumberColumn("Transações", width="small"),
            "Valor divergente": st.column_config.TextColumn("Valor divergente", width="small"),
        },
    )

    if not resumo_por_tipo.empty:
        chart_df = resumo_por_tipo.copy()
        chart_df["Valor divergente formatado"] = chart_df["valor_divergente"].map(_formatar_moeda)
        ordem_tipos = chart_df.groupby("tipo_divergencia")["transacoes"].sum().sort_values(ascending=False).index.tolist()
        chart_spec = {
            "mark": {"type": "bar"},
            "encoding": {
                "x": {
                    "field": "tipo_divergencia",
                    "type": "nominal",
                    "title": "Tipo de divergência",
                    "sort": ordem_tipos,
                    "axis": {"labelAngle": -30, "labelLimit": 180},
                },
                "y": {
                    "field": "transacoes",
                    "type": "quantitative",
                    "title": "Proporção das transações",
                    "stack": "normalize",
                    "axis": {"format": "%"},
                },
                "color": {
                    "field": "status",
                    "type": "nominal",
                    "title": "Status",
                    "scale": {
                        "domain": ["Aprovado", "Atenção", "Rejeitado"],
                        "range": ["#4CAF50", "#F4C14C", "#EF5350"],
                    },
                },
                "tooltip": [
                    {"field": "tipo_divergencia", "type": "nominal", "title": "Tipo de divergência"},
                    {"field": "status", "type": "nominal", "title": "Status"},
                    {"field": "transacoes", "type": "quantitative", "title": "Transações"},
                    {"field": "Valor divergente formatado", "type": "nominal", "title": "Valor divergente"},
                ],
            },
            "height": 360,
        }
        st.vega_lite_chart(chart_df, chart_spec, use_container_width=True)

    caminho_saida = EXPORTS_DIR / "contestacao_frete.xlsx"
    resumo_filtrado = _gerar_resumo(auditado_filtrado)
    exportar_relatorio_contestacao(auditado_filtrado, resumo_filtrado, caminho_saida)
    with caminho_saida.open("rb") as arquivo:
        st.download_button(
            "Baixar planilha de contestação",
            data=arquivo,
            file_name="contestacao_frete.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

with aba_contestacao:
    contestacao_display = _preparar_contestacao(auditado_filtrado)
    total_contestar = 0.0
    if "Valor a contestar" in contestacao_display.columns and not contestacao_display.empty:
        total_contestar = float(contestacao_display["Valor a contestar"].sum())

    st.subheader("Casos prontos para revisão financeira")
    cards_contestacao = st.columns(4)
    cards_contestacao[0].metric("Casos rejeitados", len(contestacao_display))
    cards_contestacao[1].metric("Valor a contestar", _formatar_moeda(total_contestar))
    cards_contestacao[2].metric("Transportadoras envolvidas", contestacao_display["Transportadora"].nunique() if "Transportadora" in contestacao_display.columns else 0)
    cards_contestacao[3].metric("Status inicial", "Pendente")

    if contestacao_display.empty:
        st.info("Não há casos rejeitados nos filtros atuais.")
    else:
        contestacao_editada = st.data_editor(
            _formatar_colunas_moeda(contestacao_display, {"Valor a contestar"}),
            use_container_width=True,
            hide_index=True,
            height=520,
            column_config={
                "Pedido": st.column_config.TextColumn("Pedido", width="small", disabled=True),
                "ID do CT-e": st.column_config.TextColumn("ID do CT-e", width="small", disabled=True),
                "Transportadora": st.column_config.TextColumn("Transportadora", width="medium", disabled=True),
                "Valor a contestar": st.column_config.TextColumn("Valor a contestar", width="small", disabled=True),
                "Motivo": st.column_config.TextColumn("Motivo", width="medium", disabled=True),
                "Justificativa": st.column_config.TextColumn("Justificativa", width="large", disabled=True),
                "Evidência": st.column_config.TextColumn("Evidência", width="large", disabled=True),
                "Status da contestação": st.column_config.SelectboxColumn(
                    "Status da contestação",
                    options=["Pendente", "Enviado", "Aceito", "Recusado"],
                    required=True,
                    width="small",
                ),
            },
            key="editor_contestacao",
        )

        planilha = _excel_em_memoria({"Contestação": contestacao_editada})
        st.download_button(
            "Exportar casos rejeitados para contestação",
            data=planilha,
            file_name="contestacao_rejeitados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.divider()
        st.subheader("Detalhe da contestação")
        contestacao_reset = contestacao_editada.reset_index(drop=True)
        contestacao_base = contestacao_display.reset_index(drop=True)
        opcoes_casos = {
            idx: f"{linha['Pedido']} | {linha['Transportadora']} | {linha['ID do CT-e']}"
            for idx, linha in contestacao_base.iterrows()
        }
        indice_caso = st.selectbox(
            "Selecionar caso rejeitado",
            options=list(opcoes_casos.keys()),
            format_func=lambda idx: opcoes_casos[idx],
        )
        caso = contestacao_reset.iloc[indice_caso]
        caso_base = contestacao_base.iloc[indice_caso]

        metricas_caso = st.columns(4)
        metricas_caso[0].metric("Valor a contestar", caso.get("Valor a contestar", "-"))
        metricas_caso[1].metric("Status da contestação", caso.get("Status da contestação", "-"))
        metricas_caso[2].metric("Motivo", caso.get("Motivo", "-"))
        metricas_caso[3].metric("Transportadora", caso.get("Transportadora", "-"))

        resumo_caso = st.columns(3)
        resumo_caso[0].metric("Peso faturável", _formatar_moeda(caso_base.get("Peso faturável considerado (kg)", 0.0)))
        resumo_caso[1].metric("Tarifa contratual", _formatar_moeda(caso_base.get("Tarifa contratual do frete peso", 0.0)))
        resumo_caso[2].metric("Diferença", _formatar_moeda(caso_base.get("Valor a contestar", 0.0)))

        detalhe_contestacao = pd.DataFrame(
            [
                ("Pedido", caso.get("Pedido", "")),
                ("Chave NF-e", caso.get("Chave NF-e", "")),
                ("ID do CT-e", caso.get("ID do CT-e", "")),
                ("Justificativa", caso.get("Justificativa", "")),
                ("Evidência", caso.get("Evidência", "")),
                ("Explicação da regra aplicada", caso.get("Explicação da regra aplicada", "")),
                ("GRIS esperado", _formatar_moeda(caso_base.get("GRIS esperado", 0.0))),
                ("Ad valorem esperado", _formatar_moeda(caso_base.get("Ad valorem esperado", 0.0))),
                ("Pedágio esperado", _formatar_moeda(caso_base.get("Pedágio esperado", 0.0))),
                ("Frete peso esperado", _formatar_moeda(caso_base.get("Frete peso esperado", 0.0))),
                ("Taxa de despacho esperada", _formatar_moeda(caso_base.get("Taxa de despacho esperada", 0.0))),
            ],
            columns=["Campo", "Valor"],
        )
        st.dataframe(detalhe_contestacao, use_container_width=True, hide_index=True)
        st.info(str(caso.get("Explicação da regra aplicada", "")))

with aba_historico:
    lotes_base = historico_lotes_df.copy()
    if not lotes_base.empty and "data_auditoria" in lotes_base.columns:
        lotes_base = lotes_base.sort_values("data_auditoria", ascending=False)
    lotes_display = _preparar_historico_lotes(lotes_base)
    st.subheader("Histórico de execuções")
    cards_hist = st.columns(4)
    cards_hist[0].metric("Lotes", len(lotes_display))
    cards_hist[1].metric("Registros históricos", len(historico_historico_df))
    cards_hist[2].metric("Última execução", _formatar_data_historico(lotes_display["Data da auditoria"].iloc[0]) if not lotes_display.empty else "-")
    cards_hist[3].metric("Status da base", "Consolidado")

    if st.button("Registrar execução atual no histórico", use_container_width=True):
        lote_id, data_execucao = registrar_historico_auditoria(
            DB_PATH,
            auditoria_df,
            resumo_df,
            usuario="analista.demo",
            origem="streamlit",
            versao_regra="1.0.0",
        )
        st.success(f"Execução registrada no lote {lote_id} em {data_execucao}.")
        st.rerun()

    if lotes_display.empty:
        st.info("Ainda não há histórico salvo no banco.")
    else:
        id_lote_selecionado = st.selectbox(
            "Selecionar lote",
            lotes_display["ID do lote"].tolist(),
            index=0,
        )
        lote_atual = lotes_display[lotes_display["ID do lote"] == id_lote_selecionado].head(1)
        if not lote_atual.empty:
            linha_lote = lote_atual.iloc[0]
            resumo_cards = st.columns(4)
            resumo_cards[0].metric("Total de registros", int(linha_lote["Total de registros"]))
            resumo_cards[1].metric("Rejeitados", int(linha_lote["Rejeitados"]))
            resumo_cards[2].metric("Valor faturado", linha_lote["Valor faturado"])
            resumo_cards[3].metric("Valor divergente", linha_lote["Valor divergente"])
            st.dataframe(lote_atual, use_container_width=True, hide_index=True)

            if not historico_historico_df.empty and "id_lote" in historico_historico_df.columns:
                detalhes_lote = historico_historico_df[historico_historico_df["id_lote"] == id_lote_selecionado].copy()
                if not detalhes_lote.empty:
                    detalhes_lote = _normalizar_status_dataframe(detalhes_lote)
                    colunas_detalhe = [
                        "pedido_id",
                        "chave_nfe",
                        "id_cte",
                        "transportadora",
                        "status",
                        "gravidade",
                        "tipo_divergencia",
                        "valor_esperado",
                        "valor_cobrado",
                        "valor_divergente",
                        "justificativa",
                    ]
                    detalhes_display = _preparar_display(detalhes_lote, colunas_detalhe)
                    detalhes_display = _formatar_colunas_moeda(detalhes_display, {"Valor esperado", "Valor cobrado", "Valor divergente"})
                    st.subheader("Detalhamento do lote selecionado")
                    st.dataframe(_estilizar_tabela(detalhes_display), use_container_width=True, hide_index=True, height=420, column_config=_config_colunas_auditoria())

with aba_importacao:
    st.write("Envie arquivos no formato bruto e o SAF ajustará os nomes das colunas para o padrão esperado do sistema.")
    usar_ia = st.toggle("Usar assistente de IA para sugerir mapeamento", value=True)

    arquivo_contrato = st.file_uploader("Arquivo da tabela contratual", type=["csv", "xlsx"], key="contrato")
    arquivo_erp = st.file_uploader("Arquivo da base ERP/WMS", type=["csv", "xlsx"], key="erp")
    arquivo_fatura = st.file_uploader("Arquivo da fatura da transportadora", type=["csv", "xlsx"], key="fatura")

    contrato_input = _ler_arquivo(arquivo_contrato)
    erp_input = _ler_arquivo(arquivo_erp)
    fatura_input = _ler_arquivo(arquivo_fatura)

    if st.button("Normalizar e executar auditoria", use_container_width=True):
        if contrato_input.empty or erp_input.empty or fatura_input.empty:
            st.error("Envie os três arquivos para executar a normalização e a auditoria.")
        else:
            contrato_normalizado, diag_contrato = normalizar_dataframe(contrato_input, TIPO_CONTRATO, usar_ia=usar_ia)
            erp_normalizado, diag_erp = normalizar_dataframe(erp_input, TIPO_ERP, usar_ia=usar_ia)
            fatura_normalizada, diag_fatura = normalizar_dataframe(fatura_input, TIPO_FATURA, usar_ia=usar_ia)

            auditado, resumo_custom = run_audit(
                erp_normalizado,
                fatura_normalizada,
                contrato_normalizado,
                AuditConfig(
                    tolerancia_peso_pct=float(st.session_state["tolerancia_peso_percentual"]) / 100,
                    tolerancia_valor_baixa=float(st.session_state["tolerancia_valor_baixa"]),
                    tolerancia_valor_atencao=float(st.session_state["tolerancia_valor_atencao"]),
                ),
            )
            auditado = _normalizar_status_dataframe(auditado)

            st.success("Arquivos normalizados com sucesso.")
            st.subheader("Diagnóstico da normalização")
            st.json({"contrato": diag_contrato, "erp": diag_erp, "fatura": diag_fatura})
            st.subheader("Colunas normalizadas")
            st.write("Contrato:", ", ".join(_rotular_campo(col) for col in contrato_normalizado.columns))
            st.write("ERP:", ", ".join(_rotular_campo(col) for col in erp_normalizado.columns))
            st.write("Fatura:", ", ".join(_rotular_campo(col) for col in fatura_normalizada.columns))
            st.subheader("Prévia da auditoria")

            auditado_display = _preparar_display(
                auditado,
                ["pedido_id", "chave_nfe", "id_cte", "transportadora", "status", "gravidade", "tipo_divergencia", "valor_esperado", "valor_cobrado", "valor_divergente", "justificativa"],
            )
            auditado_display = _formatar_colunas_moeda(auditado_display, {"Valor esperado", "Valor cobrado", "Valor divergente"})
            st.dataframe(
                _estilizar_tabela(auditado_display),
                use_container_width=True,
                hide_index=True,
                height=420,
                column_config=_config_colunas_auditoria(),
            )

            resumo_custom_display = resumo_custom.rename(
                columns={
                    "valor_total_faturado": "Valor total faturado",
                    "valor_total_auditado": "Valor total auditado",
                    "valor_total_divergencias": "Valor total divergências",
                    "total_registros": "Total de registros",
                    "registros_divergentes": "Registros divergentes",
                    "eficiencia_transportadora_pct": "Eficiência da transportadora (%)",
                }
            )
            resumo_custom_display = _formatar_colunas_moeda(
                resumo_custom_display,
                {"Valor total faturado", "Valor total auditado", "Valor total divergências"},
            )
            st.dataframe(_estilizar_tabela(resumo_custom_display), use_container_width=True, hide_index=True)

with aba_api:
    st.markdown(
        """
        **Integrações prontas para consumo**

        - `GET /saude`
        - `GET /campos-esperados`
        - `POST /normalizar`
        - `POST /auditorias/executar`
        - `POST /banco/demonstracao`
        - `GET /registros/{nome_tabela}`

        A API foi desenhada para receber payloads de ERP, portal interno, Google Drive ou rotinas ETL próprias da empresa.
        """
    )
