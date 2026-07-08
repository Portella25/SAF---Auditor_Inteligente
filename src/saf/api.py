from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from saf.audit import AuditConfig, run_audit
from saf.campos import CAMPOS_ESPERADOS, TIPO_CONTRATO, TIPO_ERP, TIPO_FATURA
from saf.database import carregar_banco_demo, gerar_banco_demo_a_partir_de_fixtures, registrar_historico_auditoria
from saf.normalizacao import normalizar_dataframe


app = FastAPI(title="SAF - Sistema de Auditoria de Fretes e Faturas", version="0.2.0")


class BaseNormalizacaoEntrada(BaseModel):
    tipo_base: Literal["contrato", "erp", "fatura"]
    linhas: list[dict[str, Any]]
    usar_ia: bool = True


class AuditoriaEntrada(BaseModel):
    tabela_contratual: list[dict[str, Any]]
    base_erp: list[dict[str, Any]]
    fatura_transportadora: list[dict[str, Any]]
    usar_ia: bool = True
    tolerancia_peso_pct: float = 0.05
    tolerancia_valor_baixa: float = 5.0
    tolerancia_valor_atencao: float = 25.0
    salvar_historico: bool = False
    usuario: str = "api"
    origem: str = "api"
    versao_regra: str = "1.0"


class IntegracaoEntrada(BaseModel):
    origem: str
    tipo_base: Literal["contrato", "erp", "fatura"]
    linhas: list[dict[str, Any]]
    usar_ia: bool = True


def _df(lista: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(lista)


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok", "servico": "SAF"}


@app.get("/campos-esperados")
def campos_esperados() -> dict[str, list[str]]:
    return CAMPOS_ESPERADOS


@app.get("/funcoes")
def funcoes_disponiveis() -> dict[str, list[str]]:
    return {
        "funcoes": [
            "normalizar",
            "executar_auditoria",
            "recarregar_base_de_testes",
            "consultar_base_sql",
            "obter_registros",
        ]
    }


@app.post("/normalizar")
def normalizar(entrada: BaseNormalizacaoEntrada) -> dict[str, Any]:
    tipo = entrada.tipo_base
    df = _df(entrada.linhas)
    normalizado, diagnostico = normalizar_dataframe(df, tipo, usar_ia=entrada.usar_ia)
    return {
        "tipo_base": tipo,
        "diagnostico": diagnostico,
        "linhas": normalizado.fillna("").to_dict(orient="records"),
    }


@app.post("/integracoes/receber")
def receber_integracao(entrada: IntegracaoEntrada) -> dict[str, Any]:
    df = _df(entrada.linhas)
    normalizado, diagnostico = normalizar_dataframe(df, entrada.tipo_base, usar_ia=entrada.usar_ia)
    return {
        "origem": entrada.origem,
        "tipo_base": entrada.tipo_base,
        "diagnostico": diagnostico,
        "linhas": normalizado.fillna("").to_dict(orient="records"),
    }


@app.post("/auditorias/executar")
def executar_auditoria(entrada: AuditoriaEntrada) -> dict[str, Any]:
    contrato = _df(entrada.tabela_contratual)
    erp = _df(entrada.base_erp)
    fatura = _df(entrada.fatura_transportadora)
    audit_df, resumo_df = run_audit(
        erp,
        fatura,
        contrato,
        AuditConfig(
            tolerancia_peso_pct=entrada.tolerancia_peso_pct,
            tolerancia_valor_baixa=entrada.tolerancia_valor_baixa,
            tolerancia_valor_atencao=entrada.tolerancia_valor_atencao,
        ),
    )
    historico = None
    if entrada.salvar_historico:
        historico = registrar_historico_auditoria(
            Path("data/saf.db"),
            audit_df,
            resumo_df,
            usuario=entrada.usuario,
            origem=entrada.origem,
            versao_regra=entrada.versao_regra,
        )
    return {
        "resumo": resumo_df.iloc[0].to_dict(),
        "resultados": audit_df.to_dict(orient="records"),
        "historico": historico,
    }


@app.post("/banco/demonstracao")
def gerar_banco() -> dict[str, str]:
    caminho = gerar_banco_demo_a_partir_de_fixtures()
    return {"banco_sqlite": str(caminho)}


@app.get("/banco/demonstracao")
def consultar_banco_demo() -> dict[str, Any]:
    dados = carregar_banco_demo()
    return {
        "contrato": len(dados[TIPO_CONTRATO]),
        "base_erp": len(dados[TIPO_ERP]),
        "fatura": len(dados[TIPO_FATURA]),
        "auditoria_resultados": len(dados["auditoria_resultados"]),
        "auditoria_historico": len(dados.get("auditoria_historico", [])),
        "auditoria_lotes": len(dados.get("auditoria_lotes", [])),
    }


@app.get("/registros/{nome_tabela}")
def obter_registros(nome_tabela: str) -> dict[str, Any]:
    if nome_tabela not in {TIPO_CONTRATO, TIPO_ERP, TIPO_FATURA, "auditoria_resultados", "auditoria_resumo", "auditoria_historico", "auditoria_lotes"}:
        raise HTTPException(status_code=404, detail="Tabela não encontrada.")
    dados = carregar_banco_demo()
    tabela = dados[nome_tabela]
    return {"nome_tabela": nome_tabela, "linhas": tabela.fillna("").to_dict(orient="records")}
