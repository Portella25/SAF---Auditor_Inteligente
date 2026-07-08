from pathlib import Path

import pandas as pd

from saf.audit import run_audit
from saf.database import gerar_banco_demo_a_partir_de_fixtures


def test_run_audit_flags_overcharged_base_freight():
    contrato = pd.DataFrame(
        [
            {
                "transportadora": "TransNorte",
                "uf": "SP",
                "cep_inicial": 1000000,
                "cep_final": 19999999,
                "peso_minimo_kg": 0,
                "peso_maximo_kg": 10,
                "frete_peso_base": 30.0,
                "taxa_despacho": 5.0,
                "gris_pct": 0.001,
                "ad_valorem_pct": 0.002,
                "pedagio_por_100kg": 8.0,
            }
        ]
    )
    erp = pd.DataFrame(
        [
            {
                "pedido_id": "PED000001",
                "chave_nfe": "NFE1",
                "numero_nfe": "100",
                "data_saida": "2026-07-01",
                "transportadora": "TransNorte",
                "cidade_destino": "Campinas",
                "uf_destino": "SP",
                "cep_destino": 13010001,
                "peso_real_kg": 4.0,
                "peso_cubado_kg": 5.0,
                "valor_nfe": 1000.0,
                "frete_cotado": 46.0,
                "ocorrencia_rastreamento": "",
            }
        ]
    )
    fatura = pd.DataFrame(
        [
            {
                "id_lote_fatura": "FAT-TESTE",
                "id_cte": "CTE1",
                "chave_nfe": "NFE1",
                "transportadora": "TransNorte",
                "peso_cobrado_kg": 5.0,
                "frete_peso_cobrado": 70.0,
                "taxa_despacho_cobrada": 5.0,
                "gris_cobrado": 1.0,
                "ad_valorem_cobrado": 2.0,
                "pedagio_cobrado": 8.0,
                "taxa_adicional_cobrada": 0.0,
                "tipo_taxa_adicional": "",
                "justificativa_taxa_adicional": "",
                "valor_total_cobrado": 86.0,
            }
        ]
    )

    auditoria_df, resumo_df = run_audit(erp, fatura, contrato)

    assert auditoria_df.loc[0, "status"] == "Rejeitado"
    assert "Frete peso" in auditoria_df.loc[0, "tipo_divergencia"]
    assert resumo_df.loc[0, "valor_total_divergencias"] == 40.0


def test_gerar_banco_demo_a_partir_de_fixtures(tmp_path: Path):
    banco = tmp_path / "saf_fixtures.db"
    fixtures_dir = Path("data") / "fixtures"
    caminho = gerar_banco_demo_a_partir_de_fixtures(banco, fixtures_dir)

    assert caminho.exists()

    import sqlite3

    with sqlite3.connect(caminho) as conn:
        qtd_contrato = pd.read_sql_query("SELECT COUNT(*) AS total FROM contrato", conn).iloc[0]["total"]
        qtd_erp = pd.read_sql_query("SELECT COUNT(*) AS total FROM erp", conn).iloc[0]["total"]
        qtd_fatura = pd.read_sql_query("SELECT COUNT(*) AS total FROM fatura", conn).iloc[0]["total"]
        qtd_auditoria = pd.read_sql_query("SELECT COUNT(*) AS total FROM auditoria_resultados", conn).iloc[0]["total"]
        qtd_erp_bruto = pd.read_sql_query("SELECT COUNT(*) AS total FROM erp_wms_bruto", conn).iloc[0]["total"]
        qtd_fatura_bruta = pd.read_sql_query("SELECT COUNT(*) AS total FROM fatura_transportadora_bruta", conn).iloc[0]["total"]
        status = pd.read_sql_query("SELECT status, COUNT(*) AS total FROM auditoria_resultados GROUP BY status", conn)

    assert qtd_contrato > 0
    assert qtd_erp > 0
    assert qtd_fatura > 0
    assert qtd_auditoria > 0
    assert qtd_erp_bruto > 0
    assert qtd_fatura_bruta > 0
    assert {"Aprovado", "Atenção", "Rejeitado"}.issubset(set(status["status"]))
