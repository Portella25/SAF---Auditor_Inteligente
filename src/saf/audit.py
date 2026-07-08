from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AuditConfig:
    tolerancia_peso_pct: float = 0.05
    tolerancia_valor_baixa: float = 5.0
    tolerancia_valor_atencao: float = 25.0


def _moeda(valor: float | int) -> float:
    return round(float(valor), 2)


def _peso_faturavel(registro: pd.Series) -> float:
    return max(float(registro["peso_real_kg"]), float(registro["peso_cubado_kg"]))


def _encontrar_faixa_contratual(registro: pd.Series, tabela_contratual: pd.DataFrame) -> pd.Series | None:
    peso_faturavel = _peso_faturavel(registro)
    base = tabela_contratual[tabela_contratual["transportadora"] == registro["transportadora"]].copy()
    candidatos_uf_cep = base[
        (base["uf"] == registro["uf_destino"])
        & (base["cep_inicial"] <= registro["cep_destino"])
        & (base["cep_final"] >= registro["cep_destino"])
    ]
    candidatos_uf = base[base["uf"] == registro["uf_destino"]]
    candidatos_cep = base[
        (base["cep_inicial"] <= registro["cep_destino"])
        & (base["cep_final"] >= registro["cep_destino"])
    ]

    for candidatos in (candidatos_uf_cep, candidatos_uf, candidatos_cep):
        if candidatos.empty:
            continue
        faixas = candidatos[
            (candidatos["peso_minimo_kg"] <= peso_faturavel)
            & (candidatos["peso_maximo_kg"] >= peso_faturavel)
        ]
        if not faixas.empty:
            return faixas.iloc[0]
        return candidatos.sort_values("peso_maximo_kg", ascending=False).iloc[0]

    return None


def _calcular_valor_esperado(registro: pd.Series, faixa: pd.Series) -> dict[str, float]:
    peso_faturavel = _peso_faturavel(registro)
    valor_nfe = float(registro["valor_nfe"])
    frete_peso = float(faixa["frete_peso_base"]) * peso_faturavel
    taxa_despacho = float(faixa["taxa_despacho"])
    gris = valor_nfe * (float(faixa["gris_pct"]) / 100)
    ad_valorem = valor_nfe * (float(faixa["ad_valorem_pct"]) / 100)
    pedagio = float(faixa["pedagio_por_100kg"]) * (peso_faturavel / 100)

    return {
        "peso_faturavel_kg": _moeda(peso_faturavel),
        "tarifa_contratual_frete_peso": _moeda(float(faixa["frete_peso_base"])),
        "frete_peso_esperado": _moeda(frete_peso),
        "taxa_despacho_esperada": _moeda(taxa_despacho),
        "gris_esperado": _moeda(gris),
        "ad_valorem_esperado": _moeda(ad_valorem),
        "pedagio_esperado": _moeda(pedagio),
        "valor_esperado": _moeda(frete_peso + taxa_despacho + gris + ad_valorem + pedagio),
    }


def _explicacao_regra_aplicada(esperado: dict[str, float], divergencia_valor: float) -> str:
    return (
        f"Peso faturável considerado: {esperado['peso_faturavel_kg']:.2f} kg. "
        f"Tarifa contratual aplicada no frete peso: R$ {esperado['tarifa_contratual_frete_peso']:.2f}. "
        f"GRIS esperado: R$ {esperado['gris_esperado']:.2f}. "
        f"Ad valorem esperado: R$ {esperado['ad_valorem_esperado']:.2f}. "
        f"Pedágio esperado: R$ {esperado['pedagio_esperado']:.2f}. "
        f"Diferença encontrada: R$ {divergencia_valor:.2f}."
    )


def _evidencia_operacional(registro: pd.Series) -> str:
    evidencias = []
    ocorrencia = str(registro.get("ocorrencia_rastreamento", "") or "").strip()
    taxa = str(registro.get("tipo_taxa_adicional", "") or "").strip()
    justificativa_taxa = str(registro.get("justificativa_taxa_adicional", "") or "").strip()

    if ocorrencia:
        evidencias.append(f"Rastreamento: {ocorrencia}")
    if taxa:
        evidencias.append(f"Taxa adicional informada: {taxa}")
    if justificativa_taxa:
        evidencias.append(f"Justificativa da transportadora: {justificativa_taxa}")
    return " | ".join(evidencias) if evidencias else "Sem evidência operacional anexada na base."


def _classificar(divergencia_valor: float, config: AuditConfig) -> tuple[str, str]:
    absoluto = abs(divergencia_valor)
    if absoluto <= config.tolerancia_valor_baixa:
        return "Aprovado", "Baixa"
    if absoluto <= config.tolerancia_valor_atencao:
        return "Atenção", "Média"
    return "Rejeitado", "Alta"


def _taxa_adicional_valida(registro: pd.Series) -> bool:
    tipo = str(registro.get("tipo_taxa_adicional", "")).strip().lower()
    ocorrencia = str(registro.get("ocorrencia_rastreamento", "")).strip().lower()
    justificativa = str(registro.get("justificativa_taxa_adicional", "")).strip().lower()

    if not tipo:
        return True

    evidencias = f"{ocorrencia} {justificativa}"
    termos_aceitos = {
        "reentrega": ["reentrega", "cliente ausente", "segunda tentativa"],
        "tde": ["area restrita", "dificuldade de entrega", "zona especial"],
        "trt": ["risco", "restricao de transito"],
    }
    return any(termo in evidencias for termo in termos_aceitos.get(tipo, []))


def run_audit(
    base_erp: pd.DataFrame,
    fatura_transportadora: pd.DataFrame,
    tabela_contratual: pd.DataFrame,
    config: AuditConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or AuditConfig()

    base_erp = base_erp.copy()
    fatura_transportadora = fatura_transportadora.copy()
    tabela_contratual = tabela_contratual.copy()

    for frame in (base_erp, fatura_transportadora, tabela_contratual):
        for coluna in frame.columns:
            if coluna.endswith("_kg") or coluna.endswith("_pct") or coluna.startswith("cep_") or coluna in {"valor_nfe", "frete_cotado", "frete_peso_base", "taxa_despacho", "pedagio_por_100kg", "frete_peso_cobrado", "taxa_despacho_cobrada", "gris_cobrado", "ad_valorem_cobrado", "pedagio_cobrado", "taxa_adicional_cobrada", "valor_total_cobrado"}:
                frame[coluna] = pd.to_numeric(frame[coluna], errors="coerce")

    fatura_transportadora["_duplicidade_cobranca"] = (
        fatura_transportadora.duplicated(subset=["chave_nfe"], keep="first")
        | fatura_transportadora.duplicated(subset=["id_cte"], keep="first")
    )

    merged = fatura_transportadora.merge(
        base_erp,
        on=["chave_nfe", "transportadora"],
        how="left",
        suffixes=("_fatura", "_erp"),
        indicator=True,
    )

    resultados: list[dict[str, object]] = []

    for _, registro in merged.iterrows():
        chave_nfe = str(registro.get("chave_nfe", ""))
        id_cte = str(registro.get("id_cte", ""))
        transportadora = str(registro.get("transportadora", ""))

        if registro["_merge"] != "both":
            resultados.append(
                {
                    "pedido_id": "",
                    "chave_nfe": chave_nfe,
                    "id_cte": id_cte,
                    "transportadora": transportadora,
                    "status": "Rejeitado",
                    "gravidade": "Alta",
                    "tipo_divergencia": "Sem correspondência no ERP",
                    "valor_esperado": 0.0,
                    "valor_cobrado": _moeda(registro.get("valor_total_cobrado", 0.0)),
                    "valor_divergente": _moeda(registro.get("valor_total_cobrado", 0.0)),
                    "justificativa": "Cobrança recebida da transportadora sem registro interno equivalente.",
                    "valor_a_contestar": _moeda(registro.get("valor_total_cobrado", 0.0)),
                    "motivo": "Sem correspondência no ERP",
                    "evidencia": f"CT-e {id_cte} e NF-e {chave_nfe} constam na fatura, mas não foram encontrados na base ERP/WMS.",
                    "peso_faturavel_kg": 0.0,
                    "tarifa_contratual_frete_peso": 0.0,
                    "frete_peso_esperado": 0.0,
                    "taxa_despacho_esperada": 0.0,
                    "gris_esperado": 0.0,
                    "ad_valorem_esperado": 0.0,
                    "pedagio_esperado": 0.0,
                    "explicacao_regra_aplicada": "Cobrança recebida da transportadora sem correspondência na base ERP/WMS.",
                }
            )
            continue

        faixa = _encontrar_faixa_contratual(registro, tabela_contratual)
        if faixa is None:
            resultados.append(
                {
                    "pedido_id": registro["pedido_id"],
                    "chave_nfe": chave_nfe,
                    "id_cte": id_cte,
                    "transportadora": transportadora,
                    "status": "Rejeitado",
                    "gravidade": "Alta",
                    "tipo_divergencia": "Tarifário ausente",
                    "valor_esperado": 0.0,
                    "valor_cobrado": _moeda(registro["valor_total_cobrado"]),
                    "valor_divergente": _moeda(registro["valor_total_cobrado"]),
                    "justificativa": "Não foi encontrada faixa contratual compatível com CEP, UF e peso auditado.",
                    "valor_a_contestar": _moeda(registro["valor_total_cobrado"]),
                    "motivo": "Tarifário ausente",
                    "evidencia": _evidencia_operacional(registro),
                    "peso_faturavel_kg": _moeda(_peso_faturavel(registro)),
                    "tarifa_contratual_frete_peso": 0.0,
                    "frete_peso_esperado": 0.0,
                    "taxa_despacho_esperada": 0.0,
                    "gris_esperado": 0.0,
                    "ad_valorem_esperado": 0.0,
                    "pedagio_esperado": 0.0,
                    "explicacao_regra_aplicada": _evidencia_operacional(registro),
                }
            )
            continue

        esperado = _calcular_valor_esperado(registro, faixa)
        valor_cobrado = _moeda(registro["valor_total_cobrado"])
        divergencia_valor = _moeda(valor_cobrado - esperado["valor_esperado"])

        motivos: list[str] = []
        tipos_divergencia: list[str] = []

        peso_limite = esperado["peso_faturavel_kg"] * (1 + config.tolerancia_peso_pct)
        if float(registro["peso_cobrado_kg"]) > peso_limite:
            tipos_divergencia.append("Peso/Cubagem")
            motivos.append(
                f"Peso cobrado de {float(registro['peso_cobrado_kg']):.2f} kg acima da tolerância sobre {esperado['peso_faturavel_kg']:.2f} kg."
            )

        comparacoes = {
            "frete_peso_esperado": ("Frete peso", "frete_peso_cobrado"),
            "taxa_despacho_esperada": ("Taxa de despacho", "taxa_despacho_cobrada"),
            "gris_esperado": ("GRIS", "gris_cobrado"),
            "ad_valorem_esperado": ("Ad valorem", "ad_valorem_cobrado"),
            "pedagio_esperado": ("Pedágio", "pedagio_cobrado"),
        }

        for chave_esperada, (nome_item, chave_cobrada) in comparacoes.items():
            diferenca_item = float(registro[chave_cobrada]) - esperado[chave_esperada]
            if abs(diferenca_item) > config.tolerancia_valor_baixa:
                tipos_divergencia.append(nome_item)
                motivos.append(
                    f"{nome_item} cobrado em R$ {float(registro[chave_cobrada]):.2f}; valor contratual esperado R$ {esperado[chave_esperada]:.2f}."
                )

        if float(registro["taxa_adicional_cobrada"]) > 0 and not _taxa_adicional_valida(registro):
            tipos_divergencia.append("Taxa adicional")
            motivos.append("Taxa acessória cobrada sem evidência operacional compatível no rastreamento.")

        if bool(registro.get("_duplicidade_cobranca", False)):
            tipos_divergencia.append("Duplicidade")
            motivos.append("Mesma NF-e ou mesmo CT-e aparece mais de uma vez na base de cobrança analisada.")

        if not tipos_divergencia:
            tipos_divergencia.append("Sem divergência")
            motivos.append("Cobrança dentro das regras contratuais e margens de tolerância configuradas.")

        status, gravidade = _classificar(divergencia_valor, config)
        if "Duplicidade" in tipos_divergencia or "Taxa adicional" in tipos_divergencia:
            status = "Rejeitado"
            gravidade = "Alta"

        resultados.append(
            {
                "pedido_id": registro["pedido_id"],
                "chave_nfe": chave_nfe,
                "id_cte": id_cte,
                "transportadora": transportadora,
                "status": status,
                "gravidade": gravidade,
                "tipo_divergencia": ", ".join(dict.fromkeys(tipos_divergencia)),
                "valor_esperado": esperado["valor_esperado"],
                "valor_cobrado": valor_cobrado,
                "valor_divergente": divergencia_valor,
                "justificativa": " ".join(motivos),
                "valor_a_contestar": _moeda(max(divergencia_valor, 0.0)) if status == "Rejeitado" else 0.0,
                "motivo": ", ".join(dict.fromkeys(tipos_divergencia)),
                "evidencia": _evidencia_operacional(registro),
                "peso_faturavel_kg": esperado["peso_faturavel_kg"],
                "tarifa_contratual_frete_peso": esperado["tarifa_contratual_frete_peso"],
                "frete_peso_esperado": esperado["frete_peso_esperado"],
                "taxa_despacho_esperada": esperado["taxa_despacho_esperada"],
                "gris_esperado": esperado["gris_esperado"],
                "ad_valorem_esperado": esperado["ad_valorem_esperado"],
                "pedagio_esperado": esperado["pedagio_esperado"],
                "explicacao_regra_aplicada": _explicacao_regra_aplicada(esperado, divergencia_valor),
            }
        )

    auditoria_df = pd.DataFrame(resultados)
    resumo_df = pd.DataFrame(
        [
            {
                "valor_total_faturado": _moeda(auditoria_df["valor_cobrado"].sum()) if not auditoria_df.empty else 0.0,
                "valor_total_auditado": _moeda(auditoria_df["valor_esperado"].sum()) if not auditoria_df.empty else 0.0,
                "valor_total_divergencias": _moeda(auditoria_df.loc[auditoria_df["valor_divergente"] > 0, "valor_divergente"].sum()) if not auditoria_df.empty else 0.0,
                "total_registros": int(len(auditoria_df)),
                "registros_divergentes": int((auditoria_df["status"] == "Rejeitado").sum()) if not auditoria_df.empty else 0,
                "eficiencia_transportadora_pct": _moeda((auditoria_df["status"].eq("Aprovado").mean() if len(auditoria_df) else 0) * 100),
            }
        ]
    )
    return auditoria_df, resumo_df
