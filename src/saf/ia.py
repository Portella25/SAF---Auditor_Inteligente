from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from urllib import error as urllib_error
from urllib import request as urllib_request

try:  # Optional dependency. The adapter falls back to urllib when requests is unavailable.
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised when requests is not installed
    requests = None


@dataclass(frozen=True)
class SugestaoIA:
    habilitado: bool
    sucesso: bool
    mapeamento_colunas: dict[str, str] = field(default_factory=dict)
    fornecedor: str = ""
    modelo: str = ""
    confianca: float | None = None
    mensagem: str = ""
    resposta_bruta: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "habilitado": self.habilitado,
            "sucesso": self.sucesso,
            "mapeamento_colunas": self.mapeamento_colunas,
            "fornecedor": self.fornecedor,
            "modelo": self.modelo,
            "confianca": self.confianca,
            "mensagem": self.mensagem,
        }


def _extrair_texto_resposta(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        if isinstance(payload.get("content"), str):
            return str(payload["content"]).strip()

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            primeiro = choices[0] or {}
            if isinstance(primeiro, dict):
                mensagem = primeiro.get("message")
                if isinstance(mensagem, dict) and isinstance(mensagem.get("content"), str):
                    return str(mensagem["content"]).strip()
                if isinstance(primeiro.get("text"), str):
                    return str(primeiro["text"]).strip()

        output = payload.get("output")
        if isinstance(output, list) and output:
            primeiro_output = output[0] or {}
            if isinstance(primeiro_output, dict):
                content = primeiro_output.get("content")
                if isinstance(content, list) and content:
                    primeiro_conteudo = content[0] or {}
                    if isinstance(primeiro_conteudo, dict) and isinstance(primeiro_conteudo.get("text"), str):
                        return str(primeiro_conteudo["text"]).strip()

        if isinstance(payload.get("response"), str):
            return str(payload["response"]).strip()

    return ""


def _extrair_json(texto: str) -> dict[str, Any]:
    texto = texto.strip()
    if not texto:
        return {}

    candidatos = [texto]
    fence = re.search(r"```(?:json)?\s*(.*?)```", texto, re.DOTALL | re.IGNORECASE)
    if fence:
        candidatos.insert(0, fence.group(1).strip())

    if "{" in texto and "}" in texto:
        inicio = texto.find("{")
        fim = texto.rfind("}")
        if inicio >= 0 and fim > inicio:
            candidatos.insert(0, texto[inicio : fim + 1])

    for candidato in candidatos:
        try:
            return json.loads(candidato)
        except json.JSONDecodeError:
            continue
    return {}


def _normalizar_mapeamento(mapeamento: Any) -> dict[str, str]:
    if not isinstance(mapeamento, dict):
        return {}

    normalizado: dict[str, str] = {}
    for origem, destino in mapeamento.items():
        if isinstance(origem, str) and isinstance(destino, str):
            normalizado[origem] = destino
    return normalizado


def _post_json(endpoint: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> Any:
    if requests is not None:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text

    requisicao = urllib_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(requisicao, timeout=timeout) as response:  # nosec B310 - endpoint is configured by the operator
            corpo = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:  # pragma: no cover - fallback branch
        corpo = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Erro HTTP ao consultar IA: {exc.code}") from exc

    try:
        return json.loads(corpo)
    except json.JSONDecodeError:
        return corpo


def consultar_sugestao_mapeamento_colunas_por_ia(colunas_originais: Iterable[str], tipo_base: str) -> SugestaoIA:
    """Consulta um endpoint externo de LLM/IA para sugerir mapeamento de colunas.

    O endpoint pode ser um gateway interno, um adaptador OpenAI-compatible ou qualquer
    servico HTTP que devolva JSON com o campo `mapeamento_colunas`.
    """

    endpoint = os.getenv("SAF_AI_ENDPOINT", "").strip()
    if not endpoint:
        return SugestaoIA(habilitado=False, sucesso=False, mensagem="SAF_AI_ENDPOINT nao configurado.")

    timeout = float(os.getenv("SAF_AI_TIMEOUT", "30"))
    modelo = os.getenv("SAF_AI_MODEL", "").strip()
    provedor = os.getenv("SAF_AI_PROVIDER", "endpoint_http").strip() or "endpoint_http"

    payload = {
        "tipo_base": tipo_base,
        "colunas_originais": list(colunas_originais),
        "instrucoes": (
            "Atue como um assistente de normalizacao de dados. "
            "Retorne somente JSON valido com a chave mapeamento_colunas, "
            "onde cada chave original mapeia para um campo canonico do SAF."
        ),
        "saida_esperada": {
            "mapeamento_colunas": {
                "coluna_original": "campo_canonico"
            },
            "confianca": 0.0,
            "mensagem": "texto curto opcional",
        },
    }
    if modelo:
        payload["modelo"] = modelo

    headers = {"Content-Type": "application/json"}
    token = os.getenv("SAF_AI_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resposta_bruta: Any = _post_json(endpoint, payload, headers, timeout)

    texto = _extrair_texto_resposta(resposta_bruta)
    parsed = _extrair_json(texto) if texto else {}

    if not parsed and isinstance(resposta_bruta, dict):
        parsed = resposta_bruta

    if isinstance(parsed.get("mapeamento_colunas"), dict):
        mapeamento = _normalizar_mapeamento(parsed["mapeamento_colunas"])
    elif isinstance(parsed, dict):
        mapeamento = _normalizar_mapeamento(parsed)
    else:
        mapeamento = {}

    confianca = parsed.get("confianca")
    if isinstance(confianca, str):
        try:
            confianca = float(confianca)
        except ValueError:
            confianca = None
    elif not isinstance(confianca, (float, int)):
        confianca = None

    mensagem = str(parsed.get("mensagem") or parsed.get("message") or "").strip()
    sucesso = bool(mapeamento)

    return SugestaoIA(
        habilitado=True,
        sucesso=sucesso,
        mapeamento_colunas=mapeamento,
        fornecedor=provedor,
        modelo=modelo,
        confianca=float(confianca) if isinstance(confianca, (float, int)) else None,
        mensagem=mensagem or ("Mapeamento sugerido com sucesso." if sucesso else "Endpoint respondeu sem mapeamento util."),
        resposta_bruta=resposta_bruta,
    )


def sugerir_mapeamento_colunas_por_ia(colunas_originais: Iterable[str], tipo_base: str) -> dict[str, str]:
    sugestao = consultar_sugestao_mapeamento_colunas_por_ia(colunas_originais, tipo_base)
    return dict(sugestao.mapeamento_colunas)
