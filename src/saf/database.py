from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from saf.audit import AuditConfig, run_audit
from saf.campos import TIPO_CONTRATO, TIPO_ERP, TIPO_FATURA


def caminho_banco_padrao() -> Path:
    return Path("data") / "saf.db"


def caminho_fixtures_padrao() -> Path:
    return Path("data") / "fixtures"


def conectar_banco(caminho_banco: str | Path) -> sqlite3.Connection:
    caminho = Path(caminho_banco)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(caminho)


def salvar_dataframe_sql(df: pd.DataFrame, nome_tabela: str, caminho_banco: str | Path) -> None:
    with conectar_banco(caminho_banco) as conn:
        df.to_sql(nome_tabela, conn, if_exists="replace", index=False)


def carregar_dataframe_sql(caminho_banco: str | Path, nome_tabela: str) -> pd.DataFrame:
    with conectar_banco(caminho_banco) as conn:
        return pd.read_sql_query(f"SELECT * FROM {nome_tabela}", conn)


def _carregar_csv_fixtures(pasta_fixtures: Path) -> dict[str, pd.DataFrame]:
    arquivos = {
        TIPO_CONTRATO: pasta_fixtures / "01_contrato_transportadora.csv",
        TIPO_ERP: pasta_fixtures / "02_erp_wms.csv",
        TIPO_FATURA: pasta_fixtures / "03_fatura_transportadora.csv",
        "rastreamento": pasta_fixtures / "04_rastreamento.csv",
        "erp_bruto": pasta_fixtures / "05_erp_wms_BRUTO.csv",
        "fatura_bruta": pasta_fixtures / "06_fatura_transportadora_BRUTA.csv",
        "gabarito": pasta_fixtures / "99_gabarito_cenarios_fatura.csv",
    }
    dados = {nome: pd.read_csv(caminho) for nome, caminho in arquivos.items() if caminho.exists()}
    for nome in [TIPO_ERP, TIPO_FATURA, "gabarito", "rastreamento"]:
        if nome in dados:
            for coluna in dados[nome].columns:
                if coluna in {"pedido_id", "chave_nfe", "numero_nfe", "id_cte", "id_lote_fatura", "cenario_intencional"}:
                    dados[nome][coluna] = dados[nome][coluna].astype("string")
    return dados


def _validar_fixtures_obrigatorias(dados: dict[str, pd.DataFrame], pasta_fixtures: Path) -> None:
    faltantes = [nome for nome in [TIPO_CONTRATO, TIPO_ERP, TIPO_FATURA] if nome not in dados]
    if faltantes:
        nomes = ", ".join(faltantes)
        raise FileNotFoundError(f"Arquivos obrigatórios ausentes em {pasta_fixtures}: {nomes}")


def _carregar_xlsx_fixtures(pasta_fixtures: Path) -> dict[str, pd.DataFrame]:
    arquivo = pasta_fixtures / "07_SAF_massa_consolidada.xlsx"
    if not arquivo.exists():
        return {}
    planilhas = pd.ExcelFile(arquivo)
    dados: dict[str, pd.DataFrame] = {}
    for sheet in planilhas.sheet_names:
        df = pd.read_excel(arquivo, sheet_name=sheet)
        for coluna in df.columns:
            if coluna in {"pedido_id", "chave_nfe", "numero_nfe", "id_cte", "id_lote_fatura", "cenario_intencional"}:
                df[coluna] = df[coluna].astype("string")
        dados[f"xlsx_{sheet.lower()}"] = df
    return dados


def _forcar_texto(df: pd.DataFrame) -> pd.DataFrame:
    bruto = df.copy()
    for coluna in bruto.columns:
        bruto[coluna] = bruto[coluna].astype("string")
    return bruto


def _agora_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalizar_historico(audit_df: pd.DataFrame, resumo_df: pd.DataFrame, usuario: str, origem: str, versao_regra: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if audit_df.empty:
        lotes = pd.DataFrame(
            [
                {
                    "id_lote": f"LOT-{uuid.uuid4().hex[:8].upper()}",
                    "data_auditoria": _agora_iso(),
                    "usuario": usuario,
                    "origem": origem,
                    "versao_regra": versao_regra,
                    "status_processamento": "Concluido",
                    "transportadoras": "",
                    "total_registros": 0,
                    "aprovados": 0,
                    "atencao": 0,
                    "rejeitados": 0,
                    "valor_faturado": 0.0,
                    "valor_esperado": 0.0,
                    "valor_divergente": 0.0,
                }
            ]
        )
        historico = audit_df.head(0).copy()
        historico["id_lote"] = pd.Series(dtype="string")
        historico["data_auditoria"] = pd.Series(dtype="string")
        historico["usuario"] = pd.Series(dtype="string")
        historico["origem"] = pd.Series(dtype="string")
        historico["versao_regra"] = pd.Series(dtype="string")
        historico["status_processamento"] = pd.Series(dtype="string")
        return historico, lotes

    id_lote = f"LOT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    data_auditoria = _agora_iso()
    transportadoras = ", ".join(sorted(audit_df["transportadora"].dropna().astype(str).unique()))
    lotes = pd.DataFrame(
        [
            {
                "id_lote": id_lote,
                "data_auditoria": data_auditoria,
                "usuario": usuario,
                "origem": origem,
                "versao_regra": versao_regra,
                "status_processamento": "Concluido",
                "transportadoras": transportadoras,
                "total_registros": int(len(audit_df)),
                "aprovados": int((audit_df["status"] == "Aprovado").sum()),
                "atencao": int((audit_df["status"] == "Atenção").sum()),
                "rejeitados": int((audit_df["status"] == "Rejeitado").sum()),
                "valor_faturado": float(resumo_df.iloc[0]["valor_total_faturado"]) if not resumo_df.empty else 0.0,
                "valor_esperado": float(resumo_df.iloc[0]["valor_total_auditado"]) if not resumo_df.empty else 0.0,
                "valor_divergente": float(resumo_df.iloc[0]["valor_total_divergencias"]) if not resumo_df.empty else 0.0,
            }
        ]
    )
    historico = audit_df.copy()
    historico.insert(0, "id_lote", id_lote)
    historico.insert(1, "data_auditoria", data_auditoria)
    historico.insert(2, "usuario", usuario)
    historico.insert(3, "origem", origem)
    historico.insert(4, "versao_regra", versao_regra)
    historico.insert(5, "status_processamento", "Concluido")
    return historico, lotes


def registrar_historico_auditoria(
    caminho_banco: str | Path,
    audit_df: pd.DataFrame,
    resumo_df: pd.DataFrame,
    usuario: str = "sistema",
    origem: str = "fixtures",
    versao_regra: str = "1.0",
) -> tuple[str, str]:
    historico, lotes = _normalizar_historico(audit_df, resumo_df, usuario, origem, versao_regra)
    id_lote = str(lotes.iloc[0]["id_lote"])
    with conectar_banco(caminho_banco) as conn:
        historico.to_sql("auditoria_historico", conn, if_exists="append", index=False)
        lotes.to_sql("auditoria_lotes", conn, if_exists="append", index=False)
    return id_lote, str(lotes.iloc[0]["data_auditoria"])


def gerar_banco_demo_a_partir_de_fixtures(
    caminho_banco: str | Path = caminho_banco_padrao(),
    pasta_fixtures: str | Path = caminho_fixtures_padrao(),
) -> Path:
    pasta = Path(pasta_fixtures)
    if not pasta.exists():
        raise FileNotFoundError(f"Pasta de fixtures nao encontrada: {pasta}")

    dados = _carregar_csv_fixtures(pasta)
    _validar_fixtures_obrigatorias(dados, pasta)
    dados.update(_carregar_xlsx_fixtures(pasta))
    contrato = dados[TIPO_CONTRATO]
    erp = dados[TIPO_ERP]
    fatura = dados[TIPO_FATURA]
    rastreamento = dados.get("rastreamento", pd.DataFrame())
    gabarito = dados.get("gabarito", pd.DataFrame())
    erp_bruto = dados.get("erp_bruto", pd.DataFrame())
    fatura_bruta = dados.get("fatura_bruta", pd.DataFrame())

    audit_df, resumo_df = run_audit(
        erp,
        fatura,
        contrato,
        AuditConfig(),
    )
    historico, lotes = _normalizar_historico(audit_df, resumo_df, usuario="seed", origem="fixtures", versao_regra="1.0")

    caminho = Path(caminho_banco)
    with conectar_banco(caminho) as conn:
        contrato.to_sql(TIPO_CONTRATO, conn, if_exists="replace", index=False)
        erp.to_sql(TIPO_ERP, conn, if_exists="replace", index=False)
        fatura.to_sql(TIPO_FATURA, conn, if_exists="replace", index=False)
        if not rastreamento.empty:
            _forcar_texto(rastreamento).to_sql("rastreamento", conn, if_exists="replace", index=False)
        if not gabarito.empty:
            gabarito.to_sql("gabarito_cenarios_fatura", conn, if_exists="replace", index=False)
        if not erp_bruto.empty:
            _forcar_texto(erp_bruto).to_sql("erp_wms_bruto", conn, if_exists="replace", index=False)
        if not fatura_bruta.empty:
            _forcar_texto(fatura_bruta).to_sql("fatura_transportadora_bruta", conn, if_exists="replace", index=False)
        for nome_tabela, df in dados.items():
            if nome_tabela.startswith("xlsx_"):
                _forcar_texto(df).to_sql(nome_tabela, conn, if_exists="replace", index=False)
        audit_df.to_sql("auditoria_resultados", conn, if_exists="replace", index=False)
        resumo_df.to_sql("auditoria_resumo", conn, if_exists="replace", index=False)
        historico.to_sql("auditoria_historico", conn, if_exists="replace", index=False)
        lotes.to_sql("auditoria_lotes", conn, if_exists="replace", index=False)
    return caminho


def gerar_banco_demo(
    caminho_banco: str | Path = caminho_banco_padrao(),
    quantidade_registros: int | None = None,
    semente: int | None = None,
) -> Path:
    return gerar_banco_demo_a_partir_de_fixtures(caminho_banco, caminho_fixtures_padrao())


def carregar_banco_demo(caminho_banco: str | Path = caminho_banco_padrao()) -> dict[str, pd.DataFrame]:
    caminho = Path(caminho_banco)
    if not caminho.exists():
        gerar_banco_demo_a_partir_de_fixtures(caminho, caminho_fixtures_padrao())
    tabelas = {}
    for nome_tabela in [TIPO_CONTRATO, TIPO_ERP, TIPO_FATURA, "auditoria_resultados", "auditoria_resumo", "auditoria_historico", "auditoria_lotes"]:
        try:
            tabelas[nome_tabela] = carregar_dataframe_sql(caminho, nome_tabela)
        except Exception:
            tabelas[nome_tabela] = pd.DataFrame()
    return tabelas
