from __future__ import annotations

from collections.abc import Iterable
import unicodedata

TIPO_CONTRATO = "contrato"
TIPO_ERP = "erp"
TIPO_FATURA = "fatura"

CAMPOS_ESPERADOS = {
    TIPO_CONTRATO: [
        "transportadora",
        "uf",
        "cep_inicial",
        "cep_final",
        "peso_minimo_kg",
        "peso_maximo_kg",
        "frete_peso_base",
        "taxa_despacho",
        "gris_pct",
        "ad_valorem_pct",
        "pedagio_por_100kg",
    ],
    TIPO_ERP: [
        "pedido_id",
        "chave_nfe",
        "numero_nfe",
        "data_saida",
        "transportadora",
        "cidade_destino",
        "uf_destino",
        "cep_destino",
        "peso_real_kg",
        "peso_cubado_kg",
        "valor_nfe",
        "frete_cotado",
        "ocorrencia_rastreamento",
    ],
    TIPO_FATURA: [
        "id_lote_fatura",
        "id_cte",
        "chave_nfe",
        "transportadora",
        "peso_cobrado_kg",
        "frete_peso_cobrado",
        "taxa_despacho_cobrada",
        "gris_cobrado",
        "ad_valorem_cobrado",
        "pedagio_cobrado",
        "taxa_adicional_cobrada",
        "tipo_taxa_adicional",
        "justificativa_taxa_adicional",
        "valor_total_cobrado",
    ],
}

ALIAS_COLUNAS = {
    TIPO_CONTRATO: {
        "transportadora": ["transportadora", "carrier", "transportador", "transportadora_nome"],
        "uf": ["uf", "estado", "state"],
        "cep_inicial": ["cep_inicial", "cep_inicio", "cep_start", "cep de", "faixa_cep_inicio"],
        "cep_final": ["cep_final", "cep_fim", "cep_end", "faixa_cep_fim"],
        "peso_minimo_kg": ["peso_minimo_kg", "peso_minimo", "weight_min_kg", "peso_inicio_kg"],
        "peso_maximo_kg": ["peso_maximo_kg", "peso_maximo", "weight_max_kg", "peso_fim_kg"],
        "frete_peso_base": ["frete_peso_base", "base_freight", "frete_base", "frete_peso"],
        "taxa_despacho": ["taxa_despacho", "dispatch_fee", "despacho"],
        "gris_pct": ["gris_pct", "percentual_gris", "gris", "taxa_gris"],
        "ad_valorem_pct": ["ad_valorem_pct", "percentual_ad_valorem", "advalorem", "taxa_ad_valorem"],
        "pedagio_por_100kg": ["pedagio_por_100kg", "toll_per_100kg", "pedagio", "pedagio_100kg"],
    },
    TIPO_ERP: {
        "pedido_id": ["pedido_id", "order_id", "id_pedido", "pedido"],
        "chave_nfe": ["chave_nfe", "invoice_key", "chave_nf", "nfe_chave"],
        "numero_nfe": ["numero_nfe", "invoice_number", "nfe_numero", "nota_fiscal"],
        "data_saida": ["data_saida", "shipment_date", "data", "data_envio"],
        "transportadora": ["transportadora", "carrier", "transportador"],
        "cidade_destino": ["cidade_destino", "destination_city", "cidade", "municipio"],
        "uf_destino": ["uf_destino", "destination_state", "uf", "estado_destino"],
        "cep_destino": ["cep_destino", "destination_cep", "cep", "cep_final_destino"],
        "peso_real_kg": ["peso_real_kg", "physical_weight_kg", "peso_real", "peso_bruto_kg"],
        "peso_cubado_kg": ["peso_cubado_kg", "cubed_weight_kg", "peso_cubado", "peso_cubagem_kg"],
        "valor_nfe": ["valor_nfe", "invoice_value", "valor_nf", "valor_nota"],
        "frete_cotado": ["frete_cotado", "quoted_freight", "frete_previsto", "frete_estimado"],
        "ocorrencia_rastreamento": ["ocorrencia_rastreamento", "tracking_occurrence", "ocorrencia", "tracking"],
    },
    TIPO_FATURA: {
        "id_lote_fatura": ["id_lote_fatura", "invoice_batch_id", "lote_fatura", "fatura_lote"],
        "id_cte": ["id_cte", "cte_id", "cte", "id_ct"],
        "chave_nfe": ["chave_nfe", "invoice_key", "chave_nf", "nfe_chave"],
        "transportadora": ["transportadora", "carrier", "transportador"],
        "peso_cobrado_kg": ["peso_cobrado_kg", "charged_weight_kg", "peso_cobrado", "peso_faturado_kg"],
        "frete_peso_cobrado": ["frete_peso_cobrado", "charged_base_freight", "frete_base_cobrado"],
        "taxa_despacho_cobrada": ["taxa_despacho_cobrada", "charged_dispatch_fee", "despacho_cobrado"],
        "gris_cobrado": ["gris_cobrado", "charged_gris", "gris_faturado"],
        "ad_valorem_cobrado": ["ad_valorem_cobrado", "charged_ad_valorem", "ad_valorem_faturado"],
        "pedagio_cobrado": ["pedagio_cobrado", "charged_toll", "pedagio_faturado"],
        "taxa_adicional_cobrada": ["taxa_adicional_cobrada", "charged_extra_fee", "taxa_extra", "acrescimo"],
        "tipo_taxa_adicional": ["tipo_taxa_adicional", "extra_fee_type", "tipo_taxa", "tipo_acrescimo"],
        "justificativa_taxa_adicional": [
            "justificativa_taxa_adicional",
            "extra_fee_reason",
            "justificativa",
            "motivo_taxa",
        ],
        "valor_total_cobrado": ["valor_total_cobrado", "total_charged", "total_faturado", "valor_total"],
    },
}


def normalizar_nome_coluna(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.strip().lower()
    return "".join(char if char.isalnum() else "_" for char in texto).strip("_")


def colunas_esperadas(tipo_base: str) -> list[str]:
    return list(CAMPOS_ESPERADOS[tipo_base])


def aliases_normalizados(tipo_base: str) -> dict[str, str]:
    mapa = {}
    for coluna_canonica, aliases in ALIAS_COLUNAS[tipo_base].items():
        for alias in aliases + [coluna_canonica]:
            mapa[normalizar_nome_coluna(alias)] = coluna_canonica
    return mapa


def contar_colunas_validas(colunas: Iterable[str], tipo_base: str) -> int:
    aliases = aliases_normalizados(tipo_base)
    return sum(1 for coluna in colunas if normalizar_nome_coluna(coluna) in aliases)
