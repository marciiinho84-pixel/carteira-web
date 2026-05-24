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


def _reparar_json_truncado(texto: str) -> dict:
    """
    Tenta recuperar JSON parcialmente truncado cortando na última entrada válida.
    Retorna dict com os dados parciais que conseguiu recuperar.
    """
    import re
    # Encontra a posição do último objeto completo dentro de "eventos": [...]
    # Estratégia: corta no último ',' ou '{' antes do truncamento e fecha os arrays/objetos
    pos_eventos = texto.find('"eventos"')
    if pos_eventos == -1:
        raise ValueError("JSON truncado e sem campo 'eventos' identificável")

    # Tenta fechar o JSON progressivamente removendo a entrada incompleta do final
    # Procura pela última chave fechada }
    ultimo_fechamento = texto.rfind("},")
    if ultimo_fechamento == -1:
        ultimo_fechamento = texto.rfind("}")

    if ultimo_fechamento > pos_eventos:
        tentativa = texto[: ultimo_fechamento + 1] + "]}"
        # Remove trailing comma antes do ]
        tentativa = re.sub(r",\s*\]", "]", tentativa)
        try:
            dados = json.loads(tentativa)
            n_perdidos = -1  # desconhecido
            log.warning(
                f"JSON truncado — recuperação parcial bem-sucedida "
                f"({len(dados.get('eventos', []))} eventos parciais)"
            )
            return dados
        except Exception:
            pass

    raise ValueError(
        f"JSON inválido e não foi possível recuperar parcialmente. "
        f"Trecho final recebido: ...{texto[-200:]}"
    )


def _parsear_resposta_claude(texto: str) -> list[dict]:
    """Extrai e valida a lista de eventos do JSON retornado pelo Claude."""
    texto = texto.strip()
    # Remove blocos markdown se existirem
    if texto.startswith("```"):
        linhas = texto.splitlines()
        texto = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])

    # Tenta parse direto
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e_orig:
        # Tenta extrair JSON embutido em texto livre
        import re
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if m:
            try:
                dados = json.loads(m.group())
            except Exception:
                pass
            else:
                log.debug("JSON extraído de texto com conteúdo extra")
                # segue com dados
                return _processar_eventos(dados)

        # Fallback: tenta reparar JSON truncado
        log.warning(f"JSON inválido ({e_orig}) — tentando repair de truncamento")
        try:
            dados = _reparar_json_truncado(texto)
        except ValueError as e_repair:
            raise ValueError(
                f"Resposta do Claude não é JSON válido: {e_orig}\n"
                f"Repair também falhou: {e_repair}\n\n"
                f"Primeiros 300 chars: {texto[:300]}"
            )

    return _processar_eventos(dados)


def _processar_eventos(dados: dict) -> list[dict]:
    """Valida e normaliza a lista de eventos extraída do JSON do Claude."""
    eventos_raw = dados.get("eventos", [])
    eventos = []
    for ev in eventos_raw:
        try:
            data_str = _normalizar_data(ev.get("data", ""))

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


def _normalizar_data(data_str: str) -> str:
    """Converte DD/MM/YYYY ou YYYY/MM/DD para YYYY-MM-DD."""
    if "/" in str(data_str):
        partes = str(data_str).split("/")
        if len(partes) == 3:
            if len(partes[2]) == 4:
                return f"{partes[2]}-{partes[1]:>02}-{partes[0]:>02}"
            return f"{partes[0]}-{partes[1]:>02}-{partes[2]:>02}"
    return str(data_str)


def _parsear_resposta_auto(texto: str) -> tuple[list[dict], dict]:
    """
    Interpreta a resposta do prompt mestre de auto-detecção.
    Retorna (eventos, meta) onde meta = {tipo_identificado, confianca, justificativa}.
    """
    texto = texto.strip()
    if texto.startswith("```"):
        linhas = texto.splitlines()
        texto = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        try:
            dados = _reparar_json_truncado(texto)
        except ValueError:
            raise ValueError(f"Resposta auto-detecção não é JSON válido: {e}\n\nResposta:\n{texto[:400]}")

    tipo = dados.get("tipo_identificado", "desconhecido")
    meta = {
        "tipo_identificado": tipo,
        "confianca": dados.get("confianca", "baixa"),
        "justificativa": dados.get("justificativa", ""),
    }

    if tipo == "funcef":
        # FUNCEF via auto-detect: soma linhas_competencia no Python (nunca confia em totais da IA)
        dados_extras = dados.get("dados_extras", {})
        funcef_meta = dados_extras.get("funcef", {}) if isinstance(dados_extras, dict) else {}
        validacao_auto = funcef_meta.get("validacao", {})

        # Busca linhas_competencia em múltiplos locais
        linhas_auto = (
            funcef_meta.get("linhas_competencia")
            or dados.get("linhas_competencia")
        )

        if linhas_auto:
            try:
                valor_liquido = round(sum(float(l.get("credito_subconta", 0)) for l in linhas_auto), 2)
                qtd_cotas = round(sum(float(l.get("cotas", 0)) for l in linhas_auto), 2)
                valor_bruto_auto = round(sum(float(l.get("valor_contribuicao", 0)) for l in linhas_auto), 2)
                preco_cota = round(valor_liquido / qtd_cotas, 10) if qtd_cotas > 0 else None

                # Data: tenta ler do primeiro evento ou da competencia_referencia
                ev_raw = (dados.get("eventos") or [{}])[0]
                data_str = _normalizar_data(ev_raw.get("data", ""))
                if not data_str or data_str == "None":
                    comp = dados.get("documento", {}).get("competencia_referencia", "")
                    if comp and len(comp) == 7:
                        import calendar
                        ano, mes = int(comp[:4]), int(comp[5:7])
                        data_str = f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]:02d}"

                historico_cotas = funcef_meta.get("historico_cotas_mensais", [])
                saldo = funcef_meta.get("saldo_atual")
                obs = ev_raw.get("obs") or "Contribuição FUNCEF (auto)"

                log.info(f"FUNCEF auto: soma Python — valor={valor_liquido} qtd={qtd_cotas} ({len(linhas_auto)} linhas)")
                eventos = [{
                    "data": data_str,
                    "ativo": "FUNCEF",
                    "tipo": "CONTRIBUICAO",
                    "qtd": qtd_cotas,
                    "preco": preco_cota,
                    "valor": valor_liquido,
                    "obs": obs,
                    "hash": calcular_hash_evento(data_str, "FUNCEF", "CONTRIBUICAO", qtd_cotas, valor_liquido),
                    "_funcef_historico_cotas": historico_cotas,
                    "_funcef_saldo": saldo,
                    "_funcef_validacao": validacao_auto,
                    "_funcef_valor_bruto": valor_bruto_auto,
                }]
            except Exception as e:
                log.error(f"FUNCEF auto: erro ao somar linhas: {e}")
                eventos = []
        else:
            log.warning("FUNCEF auto: linhas_competencia ausente — sem eventos gerados")
            eventos = []
    else:
        eventos = _processar_eventos(dados)

    obs = dados.get("observacoes", "")
    if obs:
        log.info(f"Auto-detecção [{tipo}]: {obs}")

    return eventos, meta


def _parsear_resposta_funcef(texto: str) -> list[dict]:
    """
    Interpreta o schema do prompt FUNCEF v3 (linhas_competencia individuais).

    Schema esperado:
      contribuicao_mes_corrente.linhas_competencia: [{historico, valor_contribuicao, credito_subconta, cotas}]
      historico_cotas_mensais: [{competencia, data, valor_cota}]
      saldo_atual: {valor_real, quantidade_cotas, data_referencia}
      validacao: {cota_historico, ok, mensagem}

    O parser soma credito_subconta e cotas em Python — nunca confia nos totais da IA.
    Produz 1 evento CONTRIBUICAO + metadados _funcef_*.
    """
    # LOG DE DEBUG — imprime o JSON bruto antes de qualquer parse
    log.info("=== FUNCEF RAW RESPONSE (primeiros 2000 chars) ===")
    log.info(texto[:2000])
    log.info("=== FIM RAW RESPONSE ===")

    texto = texto.strip()
    if texto.startswith("```"):
        linhas = texto.splitlines()
        texto = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"Resposta FUNCEF não é JSON válido: {e}\n\nResposta:\n{texto[:400]}")

    # DEBUG — mostra estrutura do JSON recebido antes de qualquer processamento
    print("DEBUG FUNCEF SCHEMA KEYS:", list(dados.keys()))
    print("DEBUG CONTRIBUICAO_MES_CORRENTE:", dados.get("contribuicao_mes_corrente"))
    print("DEBUG CONTRIBUICAO_MES (schema antigo):", dados.get("contribuicao_mes"))
    print("DEBUG HISTORICO_COTAS (primeiros 2):", dados.get("historico_cotas_mensais", [])[:2])
    print("DEBUG SALDO_ATUAL:", dados.get("saldo_atual"))
    print("DEBUG VALIDACAO:", dados.get("validacao"))
    print("DEBUG DOCUMENTO:", dados.get("documento"))

    obs_gerais = dados.get("observacoes", "")
    if obs_gerais:
        log.info(f"Observações FUNCEF: {obs_gerais}")

    # Verificar resultado da validação interna do Claude
    validacao = dados.get("validacao", {})
    if validacao and validacao.get("ok") is False:
        msg = validacao.get("mensagem", "Divergência de cota detectada")
        diferenca = validacao.get("diferenca_pct", 0)
        raise ValueError(
            f"FUNCEF: validação interna falhou — {msg} "
            f"(divergência: {diferenca:.2f}%). "
            f"Verifique o documento e reprocesse."
        )

    # Extrair subestrutura dados_extras.funcef (schema auto) quando presente
    dados_extras = dados.get("dados_extras", {})
    funcef_extras = dados_extras.get("funcef", {}) if isinstance(dados_extras, dict) else {}

    print("DEBUG DADOS_EXTRAS.FUNCEF keys:", list(funcef_extras.keys()) if isinstance(funcef_extras, dict) else "ausente")

    # Extrair contribuição do mês corrente (referência para data, obs, competência)
    contrib = dados.get("contribuicao_mes_corrente")
    if not contrib:
        contrib = dados.get("contribuicao_mes")  # retrocompatibilidade
    if not contrib:
        contrib = {}

    try:
        # DATA — lê de contrib, deriva do competencia_referencia se ausente
        data_str = _normalizar_data(contrib.get("data_ultimo_dia") or contrib.get("data") or "")
        if not data_str or data_str == "None":
            competencia = (
                contrib.get("competencia")
                or dados.get("documento", {}).get("competencia_referencia", "")
            )
            if competencia and len(competencia) == 7:
                import calendar
                ano, mes = int(competencia[:4]), int(competencia[5:7])
                ultimo_dia = calendar.monthrange(ano, mes)[1]
                data_str = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

        if not data_str or data_str == "None":
            log.warning("FUNCEF: não foi possível determinar a data do evento")
            return []

        # LINHAS INDIVIDUAIS — busca em múltiplos locais possíveis do JSON
        # O Python soma; a IA nunca calcula totais.
        def _encontrar_linhas():
            # 1. contribuicao_mes_corrente.linhas_competencia  (schema v3, lugar canônico)
            linhas = contrib.get("linhas_competencia")
            if linhas:
                return linhas, "contribuicao_mes_corrente.linhas_competencia"
            # 2. dados_extras.funcef.linhas_competencia
            linhas = funcef_extras.get("linhas_competencia") if isinstance(funcef_extras, dict) else None
            if linhas:
                return linhas, "dados_extras.funcef.linhas_competencia"
            # 3. dados_extras.funcef.validacao.linhas_somadas
            fv = funcef_extras.get("validacao", {}) if isinstance(funcef_extras, dict) else {}
            linhas = fv.get("linhas_somadas") if isinstance(fv, dict) else None
            if linhas:
                return linhas, "dados_extras.funcef.validacao.linhas_somadas"
            campos_contrib = list(contrib.keys()) if contrib else []
            campos_extras = list(funcef_extras.keys()) if isinstance(funcef_extras, dict) else []
            raise ValueError(
                f"linhas_competencia não encontrado no JSON. "
                f"contribuicao_mes_corrente: {campos_contrib} | "
                f"dados_extras.funcef: {campos_extras}"
            )

        linhas, linhas_fonte = _encontrar_linhas()
        log.info(f"FUNCEF: linhas_competencia encontradas ({linhas_fonte}): {len(linhas)} linha(s)")
        print(f"DEBUG LINHAS ({linhas_fonte}): {linhas}")

        # Somas calculadas pelo Python — nunca pela IA
        valor_liquido = round(sum(float(l.get("credito_subconta", 0)) for l in linhas), 2)
        qtd_cotas = round(sum(float(l.get("cotas", 0)) for l in linhas), 2)
        valor_bruto = round(sum(float(l.get("valor_contribuicao", 0)) for l in linhas), 2) or valor_liquido

        # Validações de sanidade
        if valor_liquido < 100 or valor_liquido > 50000:
            raise ValueError(f"Valor suspeito após soma Python: R${valor_liquido:.2f}")
        if qtd_cotas <= 0:
            raise ValueError(f"Cotas inválidas após soma Python: {qtd_cotas}")

        log.info(f"FUNCEF: soma Python — valor={valor_liquido} qtd={qtd_cotas} bruto={valor_bruto}")
        print(f"DEBUG SOMA PYTHON: valor={valor_liquido} qtd={qtd_cotas} bruto={valor_bruto}")

        # PRECO POR COTA — calcula diretamente dos totais (mais confiável que cota_historico)
        if qtd_cotas and qtd_cotas > 0:
            preco_cota = round(valor_liquido / qtd_cotas, 10)
        elif validacao and validacao.get("cota_historico"):
            preco_cota = float(validacao["cota_historico"])
        else:
            preco_cota = None

        competencia = (
            contrib.get("competencia")
            or dados.get("documento", {}).get("competencia_referencia", "")
        )
        obs_contrib = contrib.get("obs") or f"Contribuição FUNCEF {competencia} (participante + patrocinadora)"

        # HISTORICO E SALDO — lê de dados_extras.funcef ou top-level
        historico_cotas = (
            funcef_extras.get("historico_cotas_mensais")
            or dados.get("historico_cotas_mensais", [])
        )
        saldo = (
            funcef_extras.get("saldo_atual")
            or dados.get("saldo_atual")
        )

        print(f"DEBUG EVENTO FINAL: data={data_str} qtd={qtd_cotas} valor={valor_liquido} preco={preco_cota} bruto={valor_bruto}")

        evento = {
            "data": data_str,
            "ativo": "FUNCEF",
            "tipo": "CONTRIBUICAO",
            "qtd": qtd_cotas,
            "preco": preco_cota,
            "valor": valor_liquido,
            "obs": obs_contrib,
            "hash": calcular_hash_evento(data_str, "FUNCEF", "CONTRIBUICAO", qtd_cotas, valor_liquido),
            # Metadados passados para o endpoint /confirmar (não gravados como campos do evento)
            "_funcef_historico_cotas": historico_cotas,
            "_funcef_saldo": saldo,
            "_funcef_validacao": validacao,
            "_funcef_valor_bruto": valor_bruto,
            "_funcef_competencia": competencia,
        }

        log.info(
            f"FUNCEF: competência={competencia} | bruto=R${valor_bruto:.2f} | "
            f"líquido=R${valor_liquido:.2f} | cotas={qtd_cotas} | cota={preco_cota}"
        )
        return [evento]

    except Exception as e:
        log.error(f"FUNCEF: erro ao parsear contribuição: {e} — dados: {contrib}")
        raise ValueError(f"FUNCEF: não foi possível parsear a contribuição: {e}")


def extrair_eventos(
    arquivo_bytes: bytes,
    nome_arquivo: str,
    tipo_documento: str,
) -> tuple[list[dict], float, dict]:
    """
    Extrai eventos de um arquivo.

    Returns:
        (lista_de_eventos, custo_usd, meta)
        meta = {"tipo_identificado": str, "confianca": str, "justificativa": str}
        Para tipo manual (não "auto"), tipo_identificado == tipo_documento.
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

    if tipo_documento == "auto":
        eventos, meta = _parsear_resposta_auto(texto_resposta)
    elif tipo_documento == "funcef":
        eventos = _parsear_resposta_funcef(texto_resposta)
        meta = {"tipo_identificado": "funcef", "confianca": None, "justificativa": None}
    else:
        eventos = _parsear_resposta_claude(texto_resposta)
        meta = {"tipo_identificado": tipo_documento, "confianca": None, "justificativa": None}

    # Sempre inclui a resposta bruta no meta para auditoria e debug no dry_run
    meta["raw_claude_response"] = texto_resposta

    # DEBUG — confirma que meta foi populado corretamente
    print("DEBUG META KEYS:", list(meta.keys()))
    print("DEBUG RAW_CLAUDE_RESPONSE (primeiros 200):", meta.get("raw_claude_response", "AUSENTE")[:200])

    log.info(f"  → {len(eventos)} eventos | tipo={meta['tipo_identificado']} | custo=${custo:.5f}")
    return eventos, custo, meta
