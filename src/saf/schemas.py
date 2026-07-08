from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TabelaContratual(BaseModel):
    transportadora: str
    uf: str = Field(min_length=2, max_length=2)
    cep_inicial: int
    cep_final: int
    peso_minimo_kg: Decimal
    peso_maximo_kg: Decimal
    frete_peso_base: Decimal
    taxa_despacho: Decimal
    gris_pct: Decimal
    ad_valorem_pct: Decimal
    pedagio_por_100kg: Decimal

    @field_validator("uf")
    @classmethod
    def normalizar_uf(cls, valor: str) -> str:
        return valor.upper()


class BaseERP(BaseModel):
    pedido_id: str
    chave_nfe: str
    numero_nfe: str
    data_saida: date
    transportadora: str
    cidade_destino: str
    uf_destino: str = Field(min_length=2, max_length=2)
    cep_destino: int
    peso_real_kg: Decimal
    peso_cubado_kg: Decimal
    valor_nfe: Decimal
    frete_cotado: Decimal
    ocorrencia_rastreamento: str = ""

    @field_validator("uf_destino")
    @classmethod
    def normalizar_uf_destino(cls, valor: str) -> str:
        return valor.upper()


class FaturaTransportadora(BaseModel):
    id_lote_fatura: str
    id_cte: str
    chave_nfe: str
    transportadora: str
    peso_cobrado_kg: Decimal
    frete_peso_cobrado: Decimal
    taxa_despacho_cobrada: Decimal
    gris_cobrado: Decimal
    ad_valorem_cobrado: Decimal
    pedagio_cobrado: Decimal
    taxa_adicional_cobrada: Decimal
    tipo_taxa_adicional: str = ""
    justificativa_taxa_adicional: str = ""
    valor_total_cobrado: Decimal


class ResultadoAuditoria(BaseModel):
    pedido_id: str
    chave_nfe: str
    id_cte: str
    transportadora: str
    status: Literal["Aprovado", "Atenção", "Rejeitado"]
    gravidade: Literal["Baixa", "Média", "Alta"]
    tipo_divergencia: str
    valor_esperado: Decimal
    valor_cobrado: Decimal
    valor_divergente: Decimal
    justificativa: str
