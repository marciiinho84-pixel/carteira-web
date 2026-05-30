"""
engine/memoria_extrator.py — Extrai memórias de longo prazo das conversas.

Usa Claude Haiku 4.5 (modelo mais barato — só extração).
Gating: conversa precisa ter ≥4 mensagens e não ter sido extraída nas últimas 2h.
Tudo via HTTP contra a própria API — evita lock de SQLite cross-process.
Falhas silenciosas: nunca propaga exceção (extração é best-effort).
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

log = logging.getLogger("engine.memoria")

API_BASE = "http://localhost:8000/api/v1"
MODEL_EXTRATOR = "claude-haiku-4-5"
MIN_MSGS = 4
TTL_EXTRACAO = timedelta(hours=2)
MAX_MSGS_CONTEXTO = 10
MAX_MEMORIAS_POR_EXTRACAO = 5
TIMEOUT_API = 30
JANELA_MSGS = 20       # mensagens recentes preservadas na janela deslizante
LIMIAR_RESUMO = 24     # dispara sumarização quando há mais que isso de mensagens livres

SYSTEM_SUMARIZADOR = (
    "Você é um sumarizador de conversas financeiras.\n"
    "Resuma em tópicos concisos os principais pontos discutidos.\n"
    "Foque em: decisões tomadas, análises realizadas, estratégias mencionadas "
    "e contexto relevante para continuação da conversa.\n"
    "Máximo 300 tokens. Use bullet points (• )."
)

SYSTEM_PROMPT = (
    "Você é um extrator de memórias de conversas financeiras.\n"
    "Analise a conversa e extraia fatos relevantes sobre o investidor: "
    "estratégias declaradas, preferências, decisões tomadas, metas "
    "mencionadas, aversões a risco.\n\n"
    "REGRAS:\n"
    "- Extraia apenas informações duráveis e relevantes\n"
    "- Ignore dados temporários (\"hoje o mercado caiu\")\n"
    "- Ignore perguntas factuais sem insight pessoal\n"
    f"- Máximo {MAX_MEMORIAS_POR_EXTRACAO} itens por extração\n"
    "- Se não houver nada relevante: retorne []\n\n"
    "Retorne SOMENTE JSON válido, sem markdown:\n"
    '[\n'
    '  {"tipo": "estrategia|preferencia|decisao|meta|fato",\n'
    '   "conteudo": "descrição em 1-2 frases"}\n'
    ']'
)


def _get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def _carregar_conversa(conversa_id: int) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/conversas/{conversa_id}", timeout=TIMEOUT_API)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"Extrator: falha ao buscar conversa {conversa_id}: {e}")
        return None


def _carregar_mensagens(conversa_id: int) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/conversas/{conversa_id}/mensagens", timeout=TIMEOUT_API)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        log.warning(f"Extrator: falha ao buscar mensagens {conversa_id}: {e}")
        return []


def _marcar_extracao(conversa_id: int) -> None:
    """Atualiza ultima_extracao via UPDATE direto no DB (não há endpoint dedicado)."""
    try:
        from carteira_clean_web.backend.db.session import get_session
        from carteira_clean_web.backend.db.models import Conversa
        s = get_session()
        try:
            c = s.get(Conversa, conversa_id)
            if c:
                c.ultima_extracao = datetime.utcnow()
                s.commit()
        finally:
            s.close()
    except Exception as e:
        log.warning(f"Extrator: falha ao marcar extracao {conversa_id}: {e}")


def _deve_extrair(conv: dict, mensagens: list[dict]) -> bool:
    if len(mensagens) < MIN_MSGS:
        return False
    ult = conv.get("ultima_extracao")
    if not ult:
        return True
    try:
        ult_dt = datetime.fromisoformat(ult)
        return (datetime.utcnow() - ult_dt) > TTL_EXTRACAO
    except Exception:
        return True


def _chamar_haiku(api_key: str, mensagens_texto: str) -> list[dict]:
    try:
        import anthropic
    except ImportError:
        log.warning("Extrator: pacote anthropic indisponível")
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=MODEL_EXTRATOR,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": mensagens_texto}],
        )
        texto = ""
        for block in resp.content:
            if hasattr(block, "text"):
                texto += block.text
        texto = texto.strip()
        # Remover envoltura markdown se vier
        if texto.startswith("```"):
            linhas = texto.split("\n")
            texto = "\n".join(linhas[1:-1] if linhas[-1].startswith("```") else linhas[1:])
        dados = json.loads(texto)
        if not isinstance(dados, list):
            return []
        return dados[:MAX_MEMORIAS_POR_EXTRACAO]
    except json.JSONDecodeError as e:
        log.info(f"Extrator: JSON inválido retornado pelo Haiku ({e}) — ignorando")
        return []
    except Exception as e:
        log.warning(f"Extrator: erro na chamada Haiku: {e}")
        return []


def _salvar_memoria(item: dict, conversa_id: int) -> bool:
    tipo = (item.get("tipo") or "").strip().lower()
    conteudo = (item.get("conteudo") or "").strip()
    if tipo not in {"estrategia", "preferencia", "decisao", "meta", "fato"}:
        return False
    if not conteudo:
        return False
    try:
        r = requests.post(
            f"{API_BASE}/memorias",
            json={"tipo": tipo, "conteudo": conteudo,
                  "conversa_id": conversa_id, "fonte": "extraida"},
            timeout=TIMEOUT_API,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning(f"Extrator: falha ao salvar memoria: {e}")
        return False


def extrair_memorias(conversa_id: int) -> list[dict]:
    """
    Carrega a conversa, verifica gating, chama Haiku, salva memórias.
    Retorna a lista de itens salvos (vazia se não extraiu).
    Nunca propaga exceção — falhas viram log + return [].
    """
    try:
        conv = _carregar_conversa(conversa_id)
        if not conv:
            return []
        mensagens = _carregar_mensagens(conversa_id)
        if not _deve_extrair(conv, mensagens):
            return []

        api_key = _get_api_key()
        if not api_key:
            log.warning("Extrator: ANTHROPIC_API_KEY não encontrada")
            return []

        # Texto enviado ao Haiku: últimas N mensagens em formato legível
        contexto = mensagens[-MAX_MSGS_CONTEXTO:]
        linhas = [f"[{m['role'].upper()}] {m['content']}" for m in contexto]
        texto = "\n\n".join(linhas)

        itens = _chamar_haiku(api_key, texto)
        # Marca a extração mesmo que vazia (rate-limit por tempo)
        _marcar_extracao(conversa_id)

        salvas = []
        for item in itens:
            if _salvar_memoria(item, conversa_id):
                salvas.append(item)

        log.info(f"Extrator: conversa {conversa_id} → {len(salvas)} memórias salvas")
        return salvas
    except Exception as e:
        log.warning(f"Extrator: erro inesperado em conversa {conversa_id}: {e}")
        return []


def extrair_em_background(conversa_id: int) -> None:
    """Wrapper para uso em threading.Thread(target=...)."""
    extrair_memorias(conversa_id)


# ── Sumarização de histórico (janela deslizante) ──────────────────

def _carregar_todas_mensagens(conversa_id: int) -> list[dict]:
    """Carrega TODAS as mensagens da conversa via DB direto (não há limite de 30)."""
    try:
        from carteira_clean_web.backend.db.session import get_session
        from carteira_clean_web.backend.db.models import Mensagem
        s = get_session()
        try:
            msgs = (
                s.query(Mensagem)
                .filter(Mensagem.conversa_id == conversa_id)
                .order_by(Mensagem.id.asc())
                .all()
            )
            return [m.to_dict() for m in msgs]
        finally:
            s.close()
    except Exception as e:
        log.warning(f"Sumarizador: erro ao carregar msgs {conversa_id}: {e}")
        return []


def _marcar_mensagens_resumidas(ids: list[int]) -> None:
    if not ids:
        return
    try:
        from carteira_clean_web.backend.db.session import get_session
        from carteira_clean_web.backend.db.models import Mensagem
        s = get_session()
        try:
            s.query(Mensagem).filter(Mensagem.id.in_(ids)).update(
                {"incluida_no_resumo": 1}, synchronize_session=False
            )
            s.commit()
        finally:
            s.close()
    except Exception as e:
        log.warning(f"Sumarizador: erro ao marcar mensagens: {e}")


def _chamar_haiku_resumo(api_key: str, conteudo: str) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=MODEL_EXTRATOR,
            max_tokens=300,
            system=SYSTEM_SUMARIZADOR,
            messages=[{"role": "user", "content": conteudo}],
        )
        return "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    except Exception as e:
        log.warning(f"Sumarizador: erro Haiku: {e}")
        return None


def sumarizar_historico(conversa_id: int) -> bool:
    """
    Sumariza mensagens antigas quando há >JANELA_MSGS mensagens livres.
    - Preserva as últimas JANELA_MSGS (20) sem sumarizar.
    - Atualiza resumo_historico na conversa (incorporando resumo anterior).
    - Marca mensagens antigas como incluida_no_resumo=1.
    Retorna True se sumarizou, False se não havia nada a fazer.
    Nunca propaga exceção — falhas viram log + return False.
    """
    try:
        conv = _carregar_conversa(conversa_id)
        if not conv:
            return False

        todas = _carregar_todas_mensagens(conversa_id)
        msgs_livres = [m for m in todas if not m.get("incluida_no_resumo")]

        if len(msgs_livres) <= JANELA_MSGS:
            return False  # nada a sumarizar

        a_sumarizar = msgs_livres[:-JANELA_MSGS]

        api_key = _get_api_key()
        if not api_key:
            log.warning("Sumarizador: ANTHROPIC_API_KEY não encontrada")
            return False

        # Texto das mensagens a sumarizar (truncado por mensagem)
        linhas = [
            f"[{m['role'].upper()}] {(m['content'] or '')[:500]}"
            for m in a_sumarizar
        ]
        texto_msgs = "\n\n".join(linhas)

        # Incorporar resumo anterior se existir
        resumo_anterior = conv.get("resumo_historico") or ""
        if resumo_anterior:
            conteudo = (
                f"Resumo anterior da conversa:\n{resumo_anterior}\n\n"
                f"Novas mensagens para integrar ao resumo:\n{texto_msgs}"
            )
        else:
            conteudo = texto_msgs

        resumo = _chamar_haiku_resumo(api_key, conteudo)
        if not resumo:
            return False

        # Salvar resumo via endpoint da própria API
        r = requests.patch(
            f"{API_BASE}/conversas/{conversa_id}/resumo",
            json={"resumo": resumo},
            timeout=TIMEOUT_API,
        )
        r.raise_for_status()

        # Marcar mensagens antigas como sumarizadas
        ids = [m["id"] for m in a_sumarizar]
        _marcar_mensagens_resumidas(ids)

        log.info(f"Sumarizador: conversa {conversa_id} → {len(ids)} msgs → resumo {len(resumo)} chars")
        return True

    except Exception as e:
        log.warning(f"Sumarizador: erro inesperado em conversa {conversa_id}: {e}")
        return False
