"""
engine/varredura_feed.py — Motor de varredura da Sala de Comando ("Orquestra").

Roda 1x/dia (cron pré-abertura de mercado B3) e grava em `observacoes_feed`
só fatos fundamentados (tool/tabela real, nunca texto livre do modelo),
pertinentes (afetam posição, tese ativa ou banda IPS) e novos (o usuário
ainda não viu). Função de backend sob o mesmo processo do maestro — não é
um agente/instrumentista novo (mantém D2).

As 7 categorias de sinal:
  ALERTA           — tabela alertas + verificar_alertas
  TESE             — tabela teses, transição ATIVA → INVALIDADA
  IPS              — _calc_blocos_ips (sala_de_comando), desvio de banda
  TECNICO          — analise_tecnica, mudança de rating -1/0/+1
  FUNDAMENTALISTA  — analise_fundamentalista, cruzamento de zona de valuation
  NOTICIA          — noticias_rss (Noticia), notícia nova por posição
  MACRO            — regime_mercado + impacto_macro via matriz_sensibilidade

Categorias ALERTA/TESE/IPS/TECNICO/FUNDAMENTALISTA/MACRO são "edge-triggered":
a varredura guarda a última classificação conhecida por (categoria, chave) em
`varredura_estado` e só grava um item novo quando a classificação MUDA para
um estado de sinal (ex.: rating técnico virou "compra", banda IPS saiu de
"OK"). Isso evita repetir o mesmo fato todo dia enquanto a condição persiste
e satisfaz "marcar como visto remove permanentemente" — a próxima aparição
exige uma transição nova de verdade, não a mesma condição contínua.

NOTICIA é diferente: não é uma máquina de estados (cada notícia é um fato
discreto), então a deduplicação usa a própria `observacoes_feed` — uma
notícia (por id da tabela `noticias`, já deduplicada na ingestão) só entra
uma vez, nunca mais.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .constantes import COTIZADO_PUBLICO
from ..db.models import Alerta, Noticia, ObservacaoFeed, Tese, VarreduraEstado

log = logging.getLogger("varredura_feed")

_JANELA_NOTICIA_DIAS = 2

_MACRO_EIXOS = {
    # eixo: (indicador, {classificacao_sinal: variacao}, classificacao_neutra)
    "juros":    ("SELIC_META", {"subindo": "ALTA", "caindo": "QUEDA"}, "estavel"),
    "inflacao": ("IPCA",       {"acelerando": "ALTA", "desacelerando": "QUEDA"}, "controlada"),
    "cambio":   ("USD_BRL",    {"depreciacao": "ALTA", "apreciacao": "QUEDA"}, "estavel"),
}


# ─── Helpers de estado / emissão ────────────────────────────────────────────

def _transicionou(db: Session, categoria: str, chave: str, estado_atual: str, sinais: set[str]) -> bool:
    """Compara `estado_atual` com o último valor gravado para (categoria, chave)
    e sempre atualiza o registro. Retorna True só quando havia estado anterior
    diferente do atual E o atual é um estado de sinal (não neutro)."""
    row = (
        db.query(VarreduraEstado)
        .filter(VarreduraEstado.categoria == categoria, VarreduraEstado.chave == chave)
        .first()
    )
    anterior = row.valor if row else None
    agora = datetime.utcnow()
    if row is None:
        db.add(VarreduraEstado(categoria=categoria, chave=chave, valor=estado_atual, atualizado_em=agora))
    elif row.valor != estado_atual:
        row.valor = estado_atual
        row.atualizado_em = agora
    return anterior is not None and anterior != estado_atual and estado_atual in sinais


def _emitir(
    db: Session,
    categoria: str,
    conteudo: str,
    ativo: str | None = None,
    referencia_id: int | None = None,
    fundamentos: dict | None = None,
) -> None:
    db.add(ObservacaoFeed(
        categoria=categoria,
        ativo=ativo,
        referencia_id=referencia_id,
        conteudo=conteudo,
        fundamentos_json=json.dumps(fundamentos, default=str) if fundamentos is not None else None,
        criado_em=datetime.utcnow(),
        visualizado_em=None,
    ))


def _tickers_rv_gerida(estado: dict) -> list[str]:
    """Tickers em posição (qtd>0), Carteira Gerida, cotizados publicamente —
    universo elegível a técnico/fundamentalista/notícia (RENDA_FIXA/FUNCEF
    não têm série de preço nem múltiplos comparáveis)."""
    posicoes = estado.get("posicoes", {})
    ativos = estado.get("ativos", {})
    out = []
    for tkr, pos in posicoes.items():
        if pos.qtd <= 1e-9:
            continue
        info = ativos.get(tkr, {})
        if info.get("composite") != "Gerida":
            continue
        if info.get("familia") not in COTIZADO_PUBLICO:
            continue
        out.append(tkr)
    return out


# ─── Categoria 1: Alerta disparado ──────────────────────────────────────────

def _varrer_alertas(db: Session) -> int:
    from ..mcp.tools.portfolio import fn_verificar_alertas

    n = 0
    try:
        res = fn_verificar_alertas()
    except Exception:
        log.exception("varrer_alertas: falha em verificar_alertas")
        return 0

    disparados_por_id = {h["alerta_id"]: h for h in res.get("disparados", [])}
    todos_ids = [row.id for row in db.query(Alerta.id).filter(Alerta.ativo_bool == 1).all()]
    for alerta_id in todos_ids:
        hit = disparados_por_id.get(alerta_id)
        estado_atual = "disparado" if hit else "ok"
        if _transicionou(db, "ALERTA", f"alerta:{alerta_id}", estado_atual, {"disparado"}):
            ativo_ticker = hit["ativo"] if hit["tipo"] in ("RSI", "preco") else None
            _emitir(
                db, "ALERTA", hit["mensagem"],
                ativo=ativo_ticker, referencia_id=alerta_id, fundamentos=hit,
            )
            n += 1
    return n


# ─── Categoria 2: Tese invalidada ───────────────────────────────────────────

def _varrer_teses(db: Session) -> int:
    n = 0
    for t in db.query(Tese).all():
        if _transicionou(db, "TESE", f"tese:{t.id}", t.status, {"INVALIDADA"}):
            criterio = t.criterio_invalidacao or "critério de invalidação atingido"
            _emitir(
                db, "TESE",
                f"Tese de {t.ticker} invalidada — {criterio}",
                ativo=t.ticker, referencia_id=t.id, fundamentos=t.to_dict(),
            )
            n += 1
    return n


# ─── Categoria 3: Desvio de banda IPS ───────────────────────────────────────

_BLOCO_LABEL = {
    "SWING_TRADE": "Swing Trade", "GROWTH": "Growth", "DEFENSIVOS": "Defensivos",
    "RENDA_FIXA": "Renda Fixa", "FORA_IPS": "Fora IPS",
}


def _varrer_ips(db: Session) -> int:
    from ..api.routers.sala_de_comando import _build_kpis, _calc_blocos_ips

    n = 0
    try:
        kpis = _build_kpis()
        if not kpis.get("engine_ok"):
            return 0
        blocos = _calc_blocos_ips(kpis.get("patrimonio_gerida", 0))
    except Exception:
        log.exception("varrer_ips: falha ao calcular blocos IPS")
        return 0

    for b in blocos:
        if _transicionou(db, "IPS", f"ips:{b['bloco']}", b["status"], {"ABAIXO", "ACIMA"}):
            label = _BLOCO_LABEL.get(b["bloco"], b["bloco"])
            direcao = "acima" if b["status"] == "ACIMA" else "abaixo"
            pct_real = round(b["pct_real"] * 100, 1)
            pct_min = round(b["banda_min"] * 100, 1)
            pct_max = round(b["banda_max"] * 100, 1)
            _emitir(
                db, "IPS",
                f"Bloco {label} {direcao} da banda IPS: {pct_real}% "
                f"(banda {pct_min}–{pct_max}%)",
                ativo=None, referencia_id=None, fundamentos=b,
            )
            n += 1
    return n


# ─── Categoria 4: Gatilho técnico ───────────────────────────────────────────

def _varrer_tecnico(db: Session, tickers: list[str]) -> int:
    from ..mcp.tools.portfolio import fn_analise_tecnica

    n = 0
    for tkr in tickers:
        try:
            res = fn_analise_tecnica(tkr)
        except Exception:
            log.warning("varrer_tecnico: falha em %s", tkr, exc_info=True)
            continue
        if not res or res.get("erro"):
            continue
        rating_texto = res.get("rating_texto")
        if not rating_texto:
            continue
        if _transicionou(db, "TECNICO", f"tecnico:{tkr}", rating_texto, {"compra", "venda"}):
            rating = res.get("rating_geral")
            sinais = res.get("sinais") or []
            detalhe = f" — {sinais[0]}" if sinais else ""
            _emitir(
                db, "TECNICO",
                f"{tkr}: sistema técnico mudou para sinal de {rating_texto} "
                f"(rating {rating:+.2f}){detalhe}",
                ativo=tkr, referencia_id=None, fundamentos=res,
            )
            n += 1
    return n


# ─── Categoria 5: Gatilho fundamentalista ───────────────────────────────────

def _varrer_fundamentalista(db: Session, tickers: list[str]) -> int:
    from ..mcp.tools.portfolio import fn_analise_fundamentalista

    n = 0
    for tkr in tickers:
        try:
            res = fn_analise_fundamentalista(tkr)
        except Exception:
            log.warning("varrer_fundamentalista: falha em %s", tkr, exc_info=True)
            continue
        if not res or res.get("erro"):
            continue
        for linha in res.get("dimensoes", {}).get("valuation", []):
            posicao = linha.get("posicao")
            if posicao is None:
                continue
            indicador = linha["indicador"]
            chave = f"fund:{tkr}:{indicador}"
            if _transicionou(db, "FUNDAMENTALISTA", chave, posicao, {"acima da média", "abaixo da média"}):
                _emitir(
                    db, "FUNDAMENTALISTA",
                    f"{tkr}: {indicador} ficou {posicao} do setor "
                    f"(atual {linha.get('valor_atual')}, média setor {linha.get('media_setor')})",
                    ativo=tkr, referencia_id=None,
                    fundamentos={"ticker": tkr, **linha},
                )
                n += 1
    return n


# ─── Categoria 6: Notícia relevante ──────────────────────────────────────────

def _varrer_noticias(db: Session, tickers: list[str]) -> int:
    if not tickers:
        return 0
    corte = datetime.utcnow() - timedelta(days=_JANELA_NOTICIA_DIAS)
    n = 0
    rows = (
        db.query(Noticia)
        .filter(
            Noticia.ticker.in_(tickers),
            (Noticia.publicado_em >= corte)
            | (Noticia.publicado_em.is_(None) & (Noticia.coletado_em >= corte)),
        )
        .all()
    )
    for r in rows:
        ja_existe = (
            db.query(ObservacaoFeed.id)
            .filter(ObservacaoFeed.categoria == "NOTICIA", ObservacaoFeed.referencia_id == r.id)
            .first()
        )
        if ja_existe:
            continue
        fonte = f" ({r.fonte})" if r.fonte else ""
        _emitir(
            db, "NOTICIA",
            f"{r.ticker}: \"{r.titulo}\"{fonte}",
            ativo=r.ticker, referencia_id=r.id,
            fundamentos={"titulo": r.titulo, "fonte": r.fonte, "url": r.url,
                         "publicado_em": r.publicado_em},
        )
        n += 1
    return n


# ─── Categoria 7: Fato macro relevante ──────────────────────────────────────

def _varrer_macro(db: Session) -> int:
    from ..mcp.tools.portfolio import fn_impacto_macro, fn_regime_mercado

    n = 0
    try:
        regime = fn_regime_mercado()
    except Exception:
        log.exception("varrer_macro: falha em regime_mercado")
        return 0

    _EIXO_PARA_CHAVE_REGIME = {"juros": "juros", "inflacao": "inflacao", "cambio": "cambio"}
    for eixo, (indicador, mapa_variacao, neutro) in _MACRO_EIXOS.items():
        bloco = regime.get(eixo, {})
        classificacao = bloco.get("classificacao")
        if not classificacao:
            continue
        sinais = set(mapa_variacao.keys())
        if not _transicionou(db, "MACRO", f"macro:{eixo}", classificacao, sinais):
            continue
        variacao = mapa_variacao[classificacao]
        try:
            impacto = fn_impacto_macro(indicador=indicador, variacao=variacao)
        except Exception:
            log.warning("varrer_macro: falha em impacto_macro(%s,%s)", indicador, variacao, exc_info=True)
            continue
        ativos_afetados = impacto.get("ativos_carteira_afetados") or []
        if not ativos_afetados:
            continue  # regime mudou, mas nenhuma posição afetada — ausência de sinal é válida
        tickers_afetados = [a["ticker"] for a in ativos_afetados]
        _emitir(
            db, "MACRO",
            f"Regime macro: {eixo} mudou para \"{classificacao}\" — afeta "
            f"{', '.join(tickers_afetados)}",
            ativo=None, referencia_id=None,
            fundamentos={"eixo": eixo, "classificacao": classificacao, **impacto},
        )
        n += 1
    return n


# ─── Orquestrador ────────────────────────────────────────────────────────────

def rodar_varredura(db: Session) -> dict[str, int]:
    """Roda as 7 categorias e grava fatos novos em `observacoes_feed`.

    Chamado 1x/dia pelo cron pré-abertura de mercado (scripts/cron_runner.py).
    Cada categoria é isolada em try/except — falha em uma (ex.: yfinance fora
    do ar) não impede as demais de rodar.
    """
    from ..api import cache as engine_cache

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    estado = engine_cache.get_estado() if engine_cache.esta_calculado() else {}
    tickers = _tickers_rv_gerida(estado) if estado else []

    resultado: dict[str, int] = {}
    categorias: list[tuple[str, callable]] = [
        ("ALERTA", lambda: _varrer_alertas(db)),
        ("TESE", lambda: _varrer_teses(db)),
        ("IPS", lambda: _varrer_ips(db)),
        ("TECNICO", lambda: _varrer_tecnico(db, tickers)),
        ("FUNDAMENTALISTA", lambda: _varrer_fundamentalista(db, tickers)),
        ("NOTICIA", lambda: _varrer_noticias(db, tickers)),
        ("MACRO", lambda: _varrer_macro(db)),
    ]
    for nome, fn in categorias:
        try:
            resultado[nome] = fn()
        except Exception:
            log.exception("rodar_varredura: categoria %s falhou", nome)
            resultado[nome] = 0
        db.commit()

    log.info("rodar_varredura: %s", resultado)
    return resultado
