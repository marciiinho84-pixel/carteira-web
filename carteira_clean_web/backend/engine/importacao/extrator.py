"""
engine/importacao/extrator.py — Orquestração: arquivo → Claude → lista de eventos.

Fluxo:
  1. Detecta formato do arquivo
  2. Pré-processa (PDF: extrai texto nativo ou usa visão; planilha: converte para texto)
  3. Chama Claude com o prompt correto para o tipo de documento
  4. Parseia JSON de retorno
  5. Calcula hash de cada evento para detecção de duplicatas
"""

import hashlib
import json
import logging
from datetime import date, datetime

from carteira_clean_web.backend.engine.importacao.claude_client import (
    chamar_claude_com_pdf,
    chamar_claude_com_imagem,
    chamar_claude_com_texto,
)
from carteira_clean_web.backend.engine.importacao.detector import detectar_formato, mime_type_de_formato
from carteira_clean_web.backend.engine.importacao.processadores.pdf import (
    extrair_texto_pdf, tem_texto_util, validar_pdf,
)
from carteira_clean_web.backend.engine.importacao.processadores.planilha import (
    xlsx_para_texto, csv_para_texto,
)
from carteira_clean_web.backend.engine.importacao.prompts.prompts import get_prompt

log = logging.getLogger("engine.importacao.extrator")

TIPOS_VALIDOS = {
    "SALDO_INICIAL", "COMPRA", "VENDA", "DIVIDENDO", "JCP",
    "RENDIMENTO", "AMORTIZACAO", "BONIFICACAO", "CONTRIBUICAO",
    "APORTE_EXTERNO", "RESGATE_EXTERNO", "VENCIMENTO",
}


def calcular_hash_evento(data: str, ativo: str, tipo: str, qtd, valor) -> str:
    """SHA-256 de campos-chave para detecção de duplicatas."""
    chave = f"{data}-{ativo}-{tipo}-{qtd or ''}-{round(float(valor or 0), 2)}"
    return hashlib.sha256(chave.encode()).hexdigest()


def _parsear_resposta_claude(texto: str) -> list[dict]:
    """Extrai e valida a lista de eventos do JSON retornado pelo Claude."""
    texto = texto.strip()
    # Remove blocos markdown se existirem
    if texto.startswith("```"):
        linhas = texto.splitlines()
        texto = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        # Tenta extrair JSON embutido em texto
        import re
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if m:
            try:
                dados = json.loads(m.group())
            except Exception:
                raise ValueError(f"Resposta do Claude não é JSON válido: {e}\n\nResposta:\n{texto[:500]}")
        else:
            raise ValueError(f"Resposta do Claude não é JSON válido: {e}\n\nResposta:\n{texto[:500]}")

    eventos_raw = dados.get("eventos", [])
    eventos = []
    for ev in eventos_raw:
        try:
            data_str = ev.get("data", "")
            # Normaliza data para YYYY-MM-DD
            if "/" in str(data_str):
                partes = str(data_str).split("/")
                if len(partes) == 3:
                    if len(partes[2]) == 4:  # DD/MM/YYYY
                        data_str = f"{partes[2]}-{partes[1]:>02}-{partes[0]:>02}"
                    else:  # YYYY/MM/DD
                        data_str = f"{partes[0]}-{partes[1]:>02}-{partes[2]:>02}"

            tipo = str(ev.get("tipo", "")).strip().upper()
            if tipo not in TIPOS_VALIDOS:
                log.warning(f"Tipo desconhecido '{tipo}' — pulando evento {ev}")
                continue

            ativo = str(ev.get("ativo", "")).strip().upper()
            qtd = float(ev["qtd"]) if ev.get("qtd") is not None else None
            preco = float(ev["preco"]) if ev.get("preco") is not None else None
            valor = float(ev.get("valor") or 0)
            obs = str(ev.get("obs") or "")

            evento = {
                "data": data_str,
                "ativo": ativo,
                "tipo": tipo,
                "qtd": qtd,
                "preco": preco,
                "valor": valor,
                "obs": obs,
                "hash": calcular_hash_evento(data_str, ativo, tipo, qtd, valor),
            }
            eventos.append(evento)
        except Exception as e:
            log.warning(f"Evento malformado ignorado: {ev} — {e}")

    obs_gerais = dados.get("observacoes_gerais", "")
    if obs_gerais:
        log.info(f"Observações do Claude: {obs_gerais}")

    return eventos


def extrair_eventos(
    arquivo_bytes: bytes,
    nome_arquivo: str,
    tipo_documento: str,
) -> tuple[list[dict], float]:
    """
    Extrai eventos de um arquivo.

    Returns:
        (lista_de_eventos, custo_usd)
    """
    formato = detectar_formato(nome_arquivo)
    system_prompt, user_prompt = get_prompt(tipo_documento)

    log.info(f"Extraindo eventos: {nome_arquivo} (formato={formato}, tipo={tipo_documento})")

    if formato == "pdf":
        ok, erro = validar_pdf(arquivo_bytes)
        if not ok:
            raise ValueError(f"PDF inválido: {erro}")

        texto_nativo = extrair_texto_pdf(arquivo_bytes)
        if tem_texto_util(texto_nativo):
            log.info("PDF com texto nativo — usando extração por texto")
            texto_resposta, custo = chamar_claude_com_texto(texto_nativo, system_prompt, user_prompt)
        else:
            log.info("PDF escaneado — usando Claude Vision")
            texto_resposta, custo = chamar_claude_com_pdf(arquivo_bytes, system_prompt, user_prompt)

    elif formato in ("jpeg", "png"):
        mime = mime_type_de_formato(formato)
        texto_resposta, custo = chamar_claude_com_imagem(arquivo_bytes, mime, system_prompt, user_prompt)

    elif formato == "xlsx":
        texto = xlsx_para_texto(arquivo_bytes)
        if not texto:
            raise ValueError("Não foi possível extrair dados do XLSX")
        texto_resposta, custo = chamar_claude_com_texto(texto, system_prompt, user_prompt)

    elif formato == "csv":
        texto = csv_para_texto(arquivo_bytes)
        if not texto:
            raise ValueError("Não foi possível extrair dados do CSV")
        texto_resposta, custo = chamar_claude_com_texto(texto, system_prompt, user_prompt)

    else:
        raise ValueError(f"Formato '{formato}' não suportado. Use PDF, JPEG, PNG, XLSX ou CSV.")

    eventos = _parsear_resposta_claude(texto_resposta)
    log.info(f"  → {len(eventos)} eventos extraídos, custo=${custo:.5f}")
    return eventos, custo
