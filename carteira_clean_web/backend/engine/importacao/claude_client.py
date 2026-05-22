"""
engine/importacao/claude_client.py — Cliente Claude API para extração de eventos financeiros.

Usa prompt caching para reduzir custo em ~90% em chamadas repetidas do mesmo tipo de documento.
"""

import base64
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

log = logging.getLogger("engine.importacao.claude")

MODELO = "claude-sonnet-4-6"
MAX_TOKENS = 16000

# Preços Sonnet 4.6 (USD por 1M tokens)
_PRECO_INPUT = 3.0
_PRECO_OUTPUT = 15.0
_PRECO_CACHE_READ = 0.30
_PRECO_CACHE_WRITE = 3.75


def _get_client():
    try:
        import anthropic
    except ImportError:
        raise ImportError("Instale o pacote anthropic: pip install anthropic")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("Configure ANTHROPIC_API_KEY no arquivo .env")
    return anthropic.Anthropic(api_key=key, max_retries=3)


def _calcular_custo_usd(usage) -> float:
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (
        input_tokens * _PRECO_INPUT / 1_000_000
        + output_tokens * _PRECO_OUTPUT / 1_000_000
        + cache_read * _PRECO_CACHE_READ / 1_000_000
        + cache_write * _PRECO_CACHE_WRITE / 1_000_000
    )


def _verificar_truncamento(response) -> None:
    """Lança ValueError se a resposta foi cortada por limite de tokens."""
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        raise ValueError(
            "Documento muito extenso — a resposta foi truncada antes de completar o JSON. "
            "Tente dividir em partes menores ou selecionar um período específico."
        )


def _log_uso(label: str, response, custo: float) -> None:
    u = response.usage
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
    log.info(
        f"Claude {label}: {u.input_tokens}in/{u.output_tokens}out "
        f"cache_read={cache_read} cache_write={cache_write} "
        f"stop={response.stop_reason} ${custo:.5f}"
    )


def chamar_claude_com_pdf(pdf_bytes: bytes, system_prompt: str, user_prompt: str) -> tuple[str, float]:
    """
    Envia PDF nativo (base64) ao Claude Vision.
    Retorna (texto_resposta, custo_usd).
    Lança ValueError se truncado ou JSON inválido.
    """
    client = _get_client()
    dados_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    response = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": dados_b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
    )
    _verificar_truncamento(response)
    texto = response.content[0].text if response.content else ""
    custo = _calcular_custo_usd(response.usage)
    _log_uso("PDF", response, custo)
    return texto, custo


def chamar_claude_com_imagem(image_bytes: bytes, mime_type: str, system_prompt: str, user_prompt: str) -> tuple[str, float]:
    """
    Envia imagem (JPEG/PNG) ao Claude Vision.
    Retorna (texto_resposta, custo_usd).
    """
    client = _get_client()
    dados_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": dados_b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
    )
    _verificar_truncamento(response)
    texto = response.content[0].text if response.content else ""
    custo = _calcular_custo_usd(response.usage)
    _log_uso("Imagem", response, custo)
    return texto, custo


def chamar_claude_com_texto(texto_documento: str, system_prompt: str, user_prompt: str) -> tuple[str, float]:
    """
    Envia texto extraído (XLSX/CSV/PDF nativo) ao Claude.
    Retorna (texto_resposta, custo_usd).
    """
    client = _get_client()
    response = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"CONTEÚDO DO DOCUMENTO:\n\n{texto_documento}\n\n{user_prompt}",
                    }
                ],
            }
        ],
    )
    _verificar_truncamento(response)
    texto = response.content[0].text if response.content else ""
    custo = _calcular_custo_usd(response.usage)
    _log_uso("Texto", response, custo)
    return texto, custo
