from __future__ import annotations

import json

import saf.ia as ia


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_consultar_sugestao_mapeamento_colunas_por_ia_parses_openai_style(monkeypatch):
    monkeypatch.setenv("SAF_AI_ENDPOINT", "https://ia.local/executar")
    monkeypatch.setenv("SAF_AI_MODEL", "modelo-teste")
    monkeypatch.setenv("SAF_AI_PROVIDER", "openai_compat")

    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "mapeamento_colunas": {
                                "invoice_key": "chave_nfe",
                                "carrier": "transportadora",
                            },
                            "confianca": 0.92,
                            "mensagem": "mapeamento validado",
                        }
                    )
                }
            }
        ]
    }

    def fake_post(*args, **kwargs):
        return _FakeResponse(payload)

    monkeypatch.setattr(ia, "_post_json", fake_post)

    sugestao = ia.consultar_sugestao_mapeamento_colunas_por_ia(["invoice_key", "carrier"], "erp")

    assert sugestao.habilitado is True
    assert sugestao.sucesso is True
    assert sugestao.mapeamento_colunas == {
        "invoice_key": "chave_nfe",
        "carrier": "transportadora",
    }
    assert sugestao.modelo == "modelo-teste"
    assert sugestao.fornecedor == "openai_compat"
    assert sugestao.confianca == 0.92
    assert sugestao.mensagem == "mapeamento validado"


def test_consultar_sugestao_mapeamento_colunas_por_ia_without_endpoint(monkeypatch):
    monkeypatch.delenv("SAF_AI_ENDPOINT", raising=False)

    sugestao = ia.consultar_sugestao_mapeamento_colunas_por_ia(["invoice_key"], "erp")

    assert sugestao.habilitado is False
    assert sugestao.sucesso is False
    assert sugestao.mapeamento_colunas == {}
