from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from saf.campos import ALIAS_COLUNAS, CAMPOS_ESPERADOS, aliases_normalizados, normalizar_nome_coluna
from saf.ia import consultar_sugestao_mapeamento_colunas_por_ia


def _limpar_valor(coluna: str, serie: pd.Series) -> pd.Series:
    if "data" in coluna:
        return pd.to_datetime(serie, errors="coerce")
    if coluna.endswith("_kg") or coluna.endswith("_pct") or coluna.startswith("cep_") or coluna in {"cep_destino", "cep_inicial", "cep_final"}:
        return pd.to_numeric(serie, errors="coerce")
    return serie.astype("string").fillna("")


def mapear_colunas(df: pd.DataFrame, tipo_base: str, usar_ia: bool = False) -> tuple[dict[str, str], dict[str, object]]:
    aliases = aliases_normalizados(tipo_base)
    mapeamento: dict[str, str] = {}
    diagnostico_ia: dict[str, object] = {
        "habilitado": False,
        "sucesso": False,
        "mapeamento_colunas": {},
        "fornecedor": "",
        "modelo": "",
        "confianca": None,
        "mensagem": "",
    }

    if usar_ia:
        sugestao_ia = consultar_sugestao_mapeamento_colunas_por_ia(df.columns, tipo_base)
        diagnostico_ia = sugestao_ia.to_dict()
        mapeamento.update(sugestao_ia.mapeamento_colunas)

    for coluna in df.columns:
        chave = normalizar_nome_coluna(coluna)
        if coluna in mapeamento:
            continue
        if chave in aliases:
            mapeamento[coluna] = aliases[chave]

    return mapeamento, diagnostico_ia


def normalizar_dataframe(df: pd.DataFrame, tipo_base: str, usar_ia: bool = False) -> tuple[pd.DataFrame, dict[str, list[str] | dict[str, str]]]:
    mapeamento, diagnostico_ia = mapear_colunas(df, tipo_base, usar_ia=usar_ia)
    normalizado = df.rename(columns=mapeamento).copy()

    esperados = CAMPOS_ESPERADOS[tipo_base]
    faltantes = [campo for campo in esperados if campo not in normalizado.columns]
    extras = [coluna for coluna in normalizado.columns if coluna not in esperados]

    for coluna in esperados:
        if coluna not in normalizado.columns:
            normalizado[coluna] = pd.NA
        normalizado[coluna] = _limpar_valor(coluna, normalizado[coluna])

    normalizado = normalizado[esperados]
    diagnostico = {
        "mapeamento_colunas": mapeamento,
        "colunas_faltantes": faltantes,
        "colunas_extras": extras,
        "diagnostico_ia": diagnostico_ia,
    }
    return normalizado, diagnostico


def inferir_tipo_base(df: pd.DataFrame) -> str | None:
    melhor_tipo = None
    maior_pontuacao = -1
    for tipo_base in CAMPOS_ESPERADOS:
        pontuacao = sum(1 for coluna in df.columns if normalizar_nome_coluna(coluna) in aliases_normalizados(tipo_base))
        if pontuacao > maior_pontuacao:
            melhor_tipo = tipo_base
            maior_pontuacao = pontuacao
    return melhor_tipo
